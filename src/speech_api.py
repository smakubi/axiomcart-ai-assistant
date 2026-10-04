"""Lightweight voice functions: no graph/model initialization on the speech path."""

from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.config import speech_api_key
from src.voice import transcription_session_config

MAX_AUDIO_BYTES = 10 * 1024 * 1024
TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
SPEECH_MODEL = "gpt-4o-mini-tts"
SPEECH_VOICE = "marin"
SPEECH_CHUNK_BYTES = 4_096
SPEECH_SAMPLE_RATE = 24_000

router = APIRouter()


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)


def resolve_speech_key(learner_key: str | None) -> str:
    api_key = (learner_key or speech_api_key() or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Voice requires an OpenAI key in Settings or OPENAI_API_KEY on the server.",
        )
    return api_key


@router.post("/api/voice/session")
async def transcription_session(
    learner_key: Annotated[str | None, Header(alias="X-OpenAI-API-Key")] = None,
) -> JSONResponse:
    """Mint a short-lived transcription-only token; never return the server key."""
    client = AsyncOpenAI(api_key=resolve_speech_key(learner_key), timeout=20, max_retries=0)
    try:
        secret = await client.realtime.client_secrets.create(
            session=transcription_session_config(),
            expires_after={"anchor": "created_at", "seconds": 60},
        )
        return JSONResponse(
            {"value": secret.value, "expires_at": secret.expires_at},
            headers={"Cache-Control": "no-store"},
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Live transcription could not connect. Try again or use the keyboard.",
        ) from error
    finally:
        await client.close()


@router.post("/api/voice/transcribe")
async def transcribe_audio(
    audio: Annotated[UploadFile, File()],
    learner_key: Annotated[str | None, Header(alias="X-OpenAI-API-Key")] = None,
) -> dict:
    started_at = perf_counter()
    contents = await audio.read(MAX_AUDIO_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Record some audio first.")
    if len(contents) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Keep recordings under 10 MB.")

    client = AsyncOpenAI(api_key=resolve_speech_key(learner_key), timeout=20, max_retries=0)
    try:
        transcription = await client.audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=(audio.filename or "recording.webm", contents, audio.content_type or "audio/webm"),
            language="en",
        )
    finally:
        await client.close()
    return {
        "text": transcription.text.strip(),
        "latency_ms": round((perf_counter() - started_at) * 1000),
    }


async def speech_audio(text: str, api_key: str) -> AsyncIterator[bytes]:
    """Stream natural speech bytes as OpenAI produces them."""
    client = AsyncOpenAI(api_key=api_key, timeout=20, max_retries=0)
    try:
        async with client.audio.speech.with_streaming_response.create(
            model=SPEECH_MODEL,
            voice=SPEECH_VOICE,
            input=text,
            instructions=(
                "Speak with a warm, natural, confident retail-assistant voice. "
                "Use conversational pacing and avoid an announcer-like delivery."
            ),
            response_format="pcm",
            stream_format="audio",
        ) as response:
            async for chunk in response.iter_bytes(chunk_size=SPEECH_CHUNK_BYTES):
                yield chunk
    finally:
        await client.close()


@router.post("/api/voice/speak")
async def speak_text(
    request: SpeechRequest,
    learner_key: Annotated[str | None, Header(alias="X-OpenAI-API-Key")] = None,
) -> StreamingResponse:
    api_key = resolve_speech_key(learner_key)
    return StreamingResponse(
        speech_audio(request.text, api_key),
        media_type="audio/pcm",
        headers={
            "Cache-Control": "no-store",
            "X-Speech-Model": SPEECH_MODEL,
            "X-Speech-Voice": SPEECH_VOICE,
            "X-Audio-Sample-Rate": str(SPEECH_SAMPLE_RATE),
            "X-Accel-Buffering": "no",
        },
    )


app = FastAPI(title="AxiomCart Voice API")
app.include_router(router)
