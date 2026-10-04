"""Vercel entrypoint for transcription-only session credentials."""

from src.speech_api import app

__all__ = ["app"]
