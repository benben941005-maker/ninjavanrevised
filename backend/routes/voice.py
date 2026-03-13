"""
Voice Transcription Route
Uses OpenAI Whisper to convert driver speech to text
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import openai
import os
import tempfile

router = APIRouter()
client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


class TranscriptionResult(BaseModel):
    text: str
    language: str
    duration_seconds: Optional[float] = None


@router.post("/transcribe", response_model=TranscriptionResult)
async def transcribe_voice(
    file: UploadFile = File(...),
    language: Optional[str] = None
):
    """
    Transcribe driver voice recording using OpenAI Whisper.
    Supports: mp3, mp4, wav, webm, m4a
    Supported languages: en, zh, ms, ta (Singapore's main languages)
    """
    try:
        audio_data = await file.read()

        with tempfile.NamedTemporaryFile(
            suffix=f".{file.filename.split('.')[-1] if file.filename else 'webm'}",
            delete=False
        ) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            params = {
                "model": "whisper-1",
                "file": audio_file,
                "response_format": "verbose_json"
            }
            if language:
                params["language"] = language

            transcript = client.audio.transcriptions.create(**params)

        # Clean up temp file
        os.unlink(tmp_path)

        return TranscriptionResult(
            text=transcript.text,
            language=getattr(transcript, "language", "en"),
            duration_seconds=getattr(transcript, "duration", None)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")


@router.post("/transcribe-blob")
async def transcribe_voice_blob(payload: dict):
    """
    Transcribe base64-encoded audio from browser MediaRecorder API
    Used for WebM audio recorded directly in the browser
    """
    try:
        import base64

        audio_b64 = payload.get("audio")
        if not audio_b64:
            raise HTTPException(status_code=400, detail="No audio data provided")

        # Strip data URL prefix
        if "," in audio_b64:
            audio_b64 = audio_b64.split(",")[1]

        audio_bytes = base64.b64decode(audio_b64)

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="json"
            )

        os.unlink(tmp_path)

        return {"text": transcript.text, "language": "auto-detected"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")
