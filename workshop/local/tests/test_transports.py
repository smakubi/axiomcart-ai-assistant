import asyncio

import pytest

pytest.importorskip("aiortc", reason="Install requirements-live.txt for transport tests")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402
from transport_server import create_app  # noqa: E402

ORIGIN = {"origin": "http://localhost:8765"}


def test_transport_page_and_cross_origin_protection():
    with TestClient(create_app(offline=True), base_url="http://localhost:8765") as client:
        assert client.get("/").status_code == 200
        assert client.get("/client.js").status_code == 200
        assert (
            client.post(
                "/offer",
                headers={"origin": "https://other.example"},
                json={"type": "offer", "sdp": "x"},
            ).status_code
            == 403
        )
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "ws://localhost:8765/ws", headers={"origin": "https://other.example"}
            ),
        ):
            pass


def test_websocket_frame_validation_and_disconnect():
    with (
        TestClient(create_app(offline=True), base_url="http://localhost:8765") as client,
        client.websocket_connect("ws://localhost:8765/ws", headers=ORIGIN) as ws,
    ):
        assert ws.receive_json()["type"] == "ready"
        ws.send_bytes(b"x")
        assert ws.receive_json()["type"] == "error"


@pytest.mark.asyncio
async def test_rtc_track_discards_old_epoch_and_sends_clocked_pcm():
    from transport_server import RTCSink

    sink = RTCSink()
    await sink.reset(1)
    await sink.write(0, bytes([1, 0]) * 480)
    frame = await sink.track.recv()
    assert not frame.to_ndarray().any()
    await sink.write(1, bytes([2, 0]) * 480)
    frame = await sink.track.recv()
    assert not frame.to_ndarray().any()  # Short replies wait for drain/flush.
    sink.flushing = True
    frame = await sink.track.recv()
    assert (frame.to_ndarray() == 2).all()
    assert frame.pts == 960
    await sink.close()


@pytest.mark.asyncio
async def test_websocket_ack_controls_backpressure_and_reset():
    from transport_server import WebSocketSink

    class Socket:
        def __init__(self):
            self.messages = []

        async def send_json(self, msg):
            self.messages.append(msg)

    socket = Socket()
    sink = WebSocketSink(socket)
    for _ in range(4):
        await sink.write(0, bytes(960))
    task = asyncio.create_task(sink.write(0, bytes(960)))
    await asyncio.sleep(0)
    assert not task.done()
    sink.ack(socket.messages[0]["seq"])
    await task
    task = asyncio.create_task(sink.write(0, bytes(960)))
    await asyncio.sleep(0)
    await sink.reset(1)
    await task
    assert not sink.waiting


@pytest.mark.asyncio
async def test_real_webrtc_offer_media_and_barge_in():
    """Two real local aiortc peers, synthetic microphone, no API or physical devices."""
    import json
    from fractions import Fraction

    import av
    import httpx
    import numpy as np
    from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
    from aiortc.mediastreams import AudioStreamTrack

    class Microphone(AudioStreamTrack):
        def __init__(self):
            super().__init__()
            self.loud = False
            self.pts = 0

        async def recv(self):
            await asyncio.sleep(0.02)
            t = (np.arange(960) + self.pts) / 48000
            values = np.sin(2 * np.pi * 220 * t) * (9000 if self.loud else 0)
            values = values.astype("int16").reshape(1, -1)
            frame = av.AudioFrame.from_ndarray(values, format="s16", layout="mono")
            frame.sample_rate = 48000
            frame.time_base = Fraction(1, 48000)
            frame.pts = self.pts
            self.pts += 960
            return frame

    app = create_app(offline=True, silence_ms=200)
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    microphone = Microphone()
    pc.addTrack(microphone)
    channel = pc.createDataChannel("events")
    interrupted, sounding = asyncio.Event(), asyncio.Event()
    consumers = []

    @channel.on("message")
    def message(raw):
        event = json.loads(raw)
        if event["type"] == "speech_start" and event["interrupted"]:
            interrupted.set()

    @pc.on("track")
    def track(track):
        async def read():
            try:
                while True:
                    frame = await track.recv()
                    if np.abs(frame.to_ndarray().astype("int32")).max() > 500:
                        sounding.set()
            except Exception:
                pass

        consumers.append(asyncio.create_task(read()))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8765", headers=ORIGIN
    ) as http:
        ident = None
        try:
            await pc.setLocalDescription(await pc.createOffer())
            response = await http.post(
                "/offer", json={"sdp": pc.localDescription.sdp, "type": "offer", "barge_in": True}
            )
            assert response.status_code == 200, response.text
            answer = response.json()
            ident = answer["id"]
            await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type="answer"))
            async with asyncio.timeout(10):
                while channel.readyState != "open":
                    await asyncio.sleep(0.02)
                microphone.loud = True
                await asyncio.sleep(0.3)
                microphone.loud = False
                await sounding.wait()
                microphone.loud = True
                await interrupted.wait()
        finally:
            if ident:
                result = await http.delete(f"/session/{ident}")
                assert result.status_code == 200
            await pc.close()
            for task in consumers:
                task.cancel()
            await asyncio.gather(*consumers, return_exceptions=True)


def test_websocket_audio_and_voice_interruption_end_to_end():
    import numpy as np

    speech = np.full(480, 9000, dtype="<i2").tobytes()
    with (
        TestClient(
            create_app(offline=True, silence_ms=200), base_url="http://localhost:8765"
        ) as client,
        client.websocket_connect("ws://localhost:8765/ws", headers=ORIGIN) as ws,
    ):
        assert ws.receive_json()["type"] == "ready"
        for frame in [speech] * 6 + [bytes(960)] * 10:
            ws.send_bytes(frame)
        while True:
            event = ws.receive_json()
            if event["type"] == "audio":
                old_epoch = event["epoch"]
                assert len(event["pcm"]) == 1280
                break
        for _ in range(6):
            ws.send_bytes(speech)
        for _ in range(20):
            event = ws.receive_json()
            if event["type"] == "speech_start" and event["interrupted"]:
                assert event["epoch"] > old_epoch
                break
        else:
            pytest.fail("No interruption event received")
