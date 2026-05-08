"""
Адаптер Yandex SpeechKit TTS (закрывает C1 из master TODO).

Контракт:
    synth(text, *, voice="ermil", emotion="neutral") -> TtsResult
        (audio_bytes, mime, duration_estimate_s, provider, voice, model)

Поведение:
* Если ENV YANDEX_SPEECHKIT_API_KEY не задан или provider=mock — возвращаем
  detеrminистический mock (короткий PCM WAV и заглушка-бипер). Это позволяет
  пройти CI и offline-демо без расхода квоты.
* Если ключ задан — обращаемся к https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize
  через httpx. Сырьё MP3 возвращается как есть.

Здесь же — лёгкий кэш по (voice, hash(text)) на ходу, чтобы повторные TTS
для одного маршрута не уносили квоту.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import struct
import wave
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TtsResult:
    audio_bytes: bytes
    mime: str
    duration_s: float
    provider: str
    voice: str
    model: str

    def to_dict(self) -> dict:
        return {
            "audio_size_bytes": len(self.audio_bytes),
            "mime": self.mime,
            "duration_s": round(self.duration_s, 2),
            "provider": self.provider,
            "voice": self.voice,
            "model": self.model,
        }


_VALID_VOICES = {"ermil", "alena", "filipp", "jane", "omazh", "zahar"}


def _mock_wav(duration_s: float = 0.6, freq_hz: int = 540, sr: int = 16000) -> bytes:
    """Детерминированный синусоидальный «бип», узнаваемый человеком."""
    n_samples = max(1, int(duration_s * sr))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        # Простая синусоида, без зависимостей от numpy/scipy.
        import math

        amp = 14000
        frames = bytearray()
        for i in range(n_samples):
            sample = int(amp * math.sin(2 * math.pi * freq_hz * (i / sr)))
            frames += struct.pack("<h", sample)
        w.writeframes(bytes(frames))
    return buf.getvalue()


class _Cache:
    def __init__(self, capacity: int = 64) -> None:
        self.capacity = capacity
        self._order: list[str] = []
        self._data: dict[str, TtsResult] = {}

    def key(self, voice: str, text: str) -> str:
        return f"{voice}::{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"

    def get(self, k: str) -> TtsResult | None:
        return self._data.get(k)

    def put(self, k: str, v: TtsResult) -> None:
        if k in self._data:
            self._order.remove(k)
        self._order.append(k)
        self._data[k] = v
        if len(self._order) > self.capacity:
            old = self._order.pop(0)
            self._data.pop(old, None)


_CACHE = _Cache()


def reset_cache() -> None:
    global _CACHE
    _CACHE = _Cache()


async def synth(
    text: str,
    *,
    voice: str = "ermil",
    emotion: str = "neutral",
    timeout_s: float = 8.0,
) -> TtsResult:
    if not text or not text.strip():
        raise ValueError("empty text")
    text = text.strip()
    if voice not in _VALID_VOICES:
        voice = "ermil"

    cache_key = _CACHE.key(voice, text)
    hit = _CACHE.get(cache_key)
    if hit is not None:
        return hit

    api_key = os.environ.get("YANDEX_SPEECHKIT_API_KEY", "").strip()
    folder_id = os.environ.get("YANDEX_GPT_FOLDER_ID", "").strip()
    provider_pref = os.environ.get("CHITAI_TTS_PROVIDER", "auto").lower()

    if not api_key or provider_pref == "mock":
        # Оценка длительности: ~14 символов в секунду для русской речи.
        est = max(0.6, min(20.0, len(text) / 14.0))
        result = TtsResult(
            audio_bytes=_mock_wav(duration_s=est),
            mime="audio/wav",
            duration_s=est,
            provider="mock",
            voice=voice,
            model="mock-pcm-wav-1.0",
        )
        _CACHE.put(cache_key, result)
        return result

    headers = {"Authorization": f"Api-Key {api_key}"}
    data = {
        "text": text,
        "voice": voice,
        "emotion": emotion,
        "format": "mp3",
        "lang": "ru-RU",
    }
    if folder_id:
        data["folderId"] = folder_id

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(
                "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize",
                headers=headers,
                data=data,
            )
            r.raise_for_status()
            mp3 = r.content
            est = max(0.6, len(text) / 14.0)
            result = TtsResult(
                audio_bytes=mp3,
                mime="audio/mpeg",
                duration_s=est,
                provider="yandex",
                voice=voice,
                model="yandex-tts-v1",
            )
            _CACHE.put(cache_key, result)
            return result
    except httpx.HTTPError as exc:
        logger.warning("yandex tts failed, falling back to mock: %s", exc)
        est = max(0.6, len(text) / 14.0)
        result = TtsResult(
            audio_bytes=_mock_wav(duration_s=est),
            mime="audio/wav",
            duration_s=est,
            provider="mock-fallback",
            voice=voice,
            model="mock-pcm-wav-1.0",
        )
        _CACHE.put(cache_key, result)
        return result
