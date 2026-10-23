"""Loopback-only WebSocket and WebRTC adapters for the same Python voice engine."""

import asyncio
import base64
import contextlib
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from fractions import Fraction
from pathlib import Path

import av
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import AudioStreamTrack, MediaStreamError
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from live_core import FRAME_BYTES, DemoBackend, LiveSession, OpenAIBackend, SpeechVAD
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

WEB = Path(__file__).with_name("web")


class WebSocketSink:
    def __init__(self, socket):
        self.socket = socket
        self.epoch = self.seq = 0
        self.waiting = {}
        self.lock = asyncio.Lock()

    async def event(self, event):
        async with self.lock:
            await self.socket.send_json(event)

    async def reset(self, epoch):
        self.epoch = epoch
        for future in self.waiting.values():
            if not future.done():
                future.set_result(None)
        self.waiting.clear()
        await self.event({"type": "reset", "epoch": epoch})

    def ack(self, seq):
        future = self.waiting.pop(seq, None)
        if future is not None and not future.done():
            future.set_result(None)

    async def write(self, epoch, pcm):
        if epoch != self.epoch:
            return
        self.seq += 1
        seq = self.seq
        future = asyncio.get_running_loop().create_future()
        self.waiting[seq] = future
        try:
            await self.event(
                {"type": "audio", "epoch": epoch, "seq": seq, "pcm": base64.b64encode(pcm).decode()}
            )
            # Bound output to five 20 ms chunks; input receive runs independently.
            if len(self.waiting) >= 5:
                oldest = next(iter(self.waiting.values()))
                await asyncio.wait_for(asyncio.shield(oldest), timeout=5)
        except BaseException:
            self.waiting.pop(seq, None)
            raise

    async def drain(self, epoch):
        if self.waiting:
            await asyncio.wait_for(asyncio.gather(*list(self.waiting.values())), timeout=5)


class ReplyTrack(AudioStreamTrack):
    def __init__(self, sink):
        super().__init__()
        self.sink = sink
        self.pts = 0
        self.next_at = None

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError
        now = time.monotonic()
        if self.next_at is None or now - self.next_at > 0.1:
            self.next_at = now
        await asyncio.sleep(max(0, self.next_at - now))
        self.next_at += 0.02
        pcm = bytes(FRAME_BYTES)
        if not self.sink.started and (self.sink.queue.qsize() >= 6 or self.sink.flushing):
            self.sink.started = True
        if self.sink.started and self.sink.queue.empty() and not self.sink.flushing:
            self.sink.started = False
            self.sink.underruns += 1
        while self.sink.started and not self.sink.queue.empty():
            epoch, data = self.sink.queue.get_nowait()
            if epoch == self.sink.epoch:
                pcm = data
                self.sink.until = time.monotonic() + 0.1
                break
        frame = av.AudioFrame(format="s16", layout="mono", samples=480)
        frame.planes[0].update(pcm)
        frame.sample_rate = 24000
        frame.pts, frame.time_base = self.pts, Fraction(1, 24000)
        self.pts += 480
        return frame


class RTCSink:
    def __init__(self):
        self.epoch = 0
        self.queue = asyncio.Queue(maxsize=25)
        self.channel = None
        self.until = 0
        self.track = ReplyTrack(self)
        self.started = self.flushing = False
        self.underruns = 0

    async def event(self, event):
        if self.channel and self.channel.readyState == "open":
            self.channel.send(json.dumps(event))

    async def reset(self, epoch):
        self.epoch = epoch
        while not self.queue.empty():
            self.queue.get_nowait()
        self.until = 0
        self.started = self.flushing = False
        self.underruns = 0
        await self.event({"type": "reset", "epoch": epoch})

    async def write(self, epoch, pcm):
        if epoch == self.epoch:
            await asyncio.wait_for(self.queue.put((epoch, pcm)), timeout=5)

    async def drain(self, epoch):
        self.flushing = True
        while epoch == self.epoch:
            if self.queue.empty() and time.monotonic() >= self.until:
                if self.underruns:
                    await self.event(
                        {"type": "playback_gaps", "text": f"{self.underruns} buffer refill(s)"}
                    )
                return
            await asyncio.sleep(0.01)

    async def close(self):
        self.track.stop()
        await self.reset(self.epoch + 1)


def same_origin(headers):
    # These exercises spend the server's key, so reject other websites' requests.
    origin = headers.get("origin", "")
    host = headers.get("host", "")
    return host.split(":")[0] in ("localhost", "127.0.0.1") and origin == f"http://{host}"


class Offer(BaseModel):
    sdp: str = Field(min_length=1, max_length=64000)
    type: str = "offer"
    barge_in: bool = True


def create_app(offline=False, threshold=0.025, silence_ms=700):
    peers = {}

    @asynccontextmanager
    async def lifespan(app):
        yield
        await asyncio.gather(*(close() for close in list(peers.values())), return_exceptions=True)

    app = FastAPI(lifespan=lifespan)

    def resources(sink, barge_in):
        if not offline and not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(503, "Set OPENAI_API_KEY or start with --offline.")
        client = None if offline else AsyncOpenAI(timeout=30, max_retries=0)
        backend = DemoBackend() if offline else OpenAIBackend(client)
        session = LiveSession(
            backend,
            sink,
            barge_in=barge_in,
            threshold=threshold,
            silence_ms=silence_ms,
            speech_detector=None if offline else SpeechVAD(),
            confirm_ms=120 if offline else 240,
            interrupt_ms=120 if offline else 500,
        )
        return client, session

    @app.get("/")
    async def index():
        return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/{asset}")
    async def asset(asset: str):
        if asset not in ("client.js", "audio-worklet.js", "audio-utils.mjs"):
            raise HTTPException(404)
        return FileResponse(
            WEB / asset, media_type="application/javascript", headers={"Cache-Control": "no-store"}
        )

    @app.websocket("/ws")
    async def websocket(socket: WebSocket):
        if not same_origin(socket.headers):
            await socket.close(code=1008)
            return
        if len(peers) >= 4:
            await socket.close(code=1013)
            return
        await socket.accept()
        sink = WebSocketSink(socket)
        client = session = None
        ident = uuid.uuid4().hex

        async def shutdown():
            with contextlib.suppress(Exception):
                await socket.close()

        peers[ident] = shutdown
        try:
            client, session = resources(sink, socket.query_params.get("barge_in", "1") == "1")
            await sink.event(
                {
                    "type": "ready",
                    "offline": offline,
                    "rate": 24000,
                    "text": "WebSocket PCM; bounded playback window",
                }
            )
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                message = await asyncio.wait_for(socket.receive(), timeout=30)
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    pcm = message["bytes"]
                    if len(pcm) != FRAME_BYTES:
                        await sink.event({"type": "error", "text": "Expected 960-byte PCM frame."})
                        break
                    await session.feed(pcm)
                elif message.get("text") is not None:
                    if len(message["text"]) > 256:
                        break
                    event = json.loads(message["text"])
                    if event.get("type") == "played" and type(event.get("seq")) is int:
                        sink.ack(event["seq"])
                    elif event.get("type") == "stop_reply":
                        await session.invalidate()
                    else:
                        break
        except (TimeoutError, WebSocketDisconnect, ValueError):
            pass
        except Exception:
            with contextlib.suppress(Exception):
                await sink.event({"type": "error", "text": "Session failed; check configuration."})
        finally:
            # Disconnect must not prevent cancellation or client cleanup.
            if session:
                with contextlib.suppress(Exception):
                    await session.close()
            if client:
                await client.close()
            peers.pop(ident, None)
            with contextlib.suppress(Exception):
                await socket.close()

    @app.post("/offer")
    async def offer(request: Request, body: Offer):
        if not same_origin(request.headers):
            raise HTTPException(403, "Use the page served by this local server.")
        if body.type != "offer":
            raise HTTPException(400, "Expected SDP offer.")
        if len(peers) >= 4:
            raise HTTPException(503, "Close another workshop connection first.")
        # No STUN/TURN service: intentionally localhost/same-machine demonstration.
        pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        sink = RTCSink()
        client, session = resources(sink, body.barge_in)
        ident = uuid.uuid4().hex
        tasks = set()
        closed = False

        async def close():
            nonlocal closed
            if closed:
                return
            closed = True
            peers.pop(ident, None)
            for task in list(tasks):
                if task is not asyncio.current_task():
                    task.cancel()
            await session.close()
            await sink.close()
            await pc.close()
            if client:
                await client.close()
            others = [task for task in tasks if task is not asyncio.current_task()]
            await asyncio.gather(*others, return_exceptions=True)

        peers[ident] = close
        pc.addTrack(sink.track)

        async def consume(track):
            resampler = av.AudioResampler(format="s16", layout="mono", rate=24000, frame_size=480)
            try:
                while True:
                    frame = await asyncio.wait_for(track.recv(), timeout=30)
                    for chunk in resampler.resample(frame):
                        await session.feed(chunk.to_ndarray().tobytes())
            except (TimeoutError, MediaStreamError):
                pass
            finally:
                await close()

        def spawn(coro):
            task = asyncio.create_task(coro)
            tasks.add(task)
            task.add_done_callback(tasks.discard)

        @pc.on("track")
        def on_track(track):
            if track.kind == "audio":
                spawn(consume(track))

        @pc.on("datachannel")
        def on_channel(channel):
            sink.channel = channel

            @channel.on("open")
            def on_open():
                channel.send(
                    json.dumps(
                        {
                            "type": "ready",
                            "offline": offline,
                            "text": "WebRTC media; 120 ms startup buffer",
                        }
                    )
                )

            @channel.on("message")
            def on_message(message):
                if message == "stop_reply":
                    spawn(session.invalidate())

        @pc.on("connectionstatechange")
        async def connection_changed():
            if pc.connectionState in ("closed", "failed"):
                await close()

        async def expire():
            await asyncio.sleep(600)
            await close()

        spawn(expire())
        try:
            await pc.setRemoteDescription(RTCSessionDescription(sdp=body.sdp, type="offer"))
            await pc.setLocalDescription(await pc.createAnswer())
        except Exception as error:
            await close()
            raise HTTPException(400, "WebRTC negotiation failed.") from error
        return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type, "id": ident}

    @app.delete("/session/{ident}")
    async def stop_session(ident: str, request: Request):
        if not same_origin(request.headers):
            raise HTTPException(403)
        close = peers.get(ident)
        if close:
            await close()
        return {"closed": True}

    return app


def serve(args):
    import uvicorn

    # Validate shared audio settings before accepting sessions.
    from live_core import TurnCapture

    TurnCapture(threshold=args.threshold, silence_ms=args.silence_ms)
    if not args.offline and not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY in .env or use --offline.")
    print(f"Open http://127.0.0.1:{args.port}; headphones recommended. Ctrl+C to stop.")
    uvicorn.run(
        create_app(args.offline, args.threshold, args.silence_ms),
        host="127.0.0.1",
        port=args.port,
        ws_max_size=65536,
    )
