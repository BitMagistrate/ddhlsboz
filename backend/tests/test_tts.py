"""Тесты Yandex SpeechKit TTS адаптера и mock-фоллбэка."""

from __future__ import annotations

import pytest

from app import tts


@pytest.fixture(autouse=True)
def _reset_tts_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YANDEX_SPEECHKIT_API_KEY", raising=False)
    monkeypatch.setenv("CHITAI_TTS_PROVIDER", "mock")
    tts.reset_cache()
    yield
    tts.reset_cache()


@pytest.mark.asyncio
async def test_synth_mock_returns_wav() -> None:
    out = await tts.synth("Привет, ЧитАИ.")
    assert out.provider == "mock"
    assert out.mime == "audio/wav"
    assert out.audio_bytes.startswith(b"RIFF")
    assert "WAVE" in out.audio_bytes[:12].decode("ascii", errors="ignore")
    assert out.duration_s > 0


@pytest.mark.asyncio
async def test_synth_caches_by_voice_and_text() -> None:
    a = await tts.synth("Один и тот же текст", voice="ermil")
    b = await tts.synth("Один и тот же текст", voice="ermil")
    assert a is b  # тот же объект из кэша


@pytest.mark.asyncio
async def test_synth_different_voice_breaks_cache() -> None:
    a = await tts.synth("одинаковый текст", voice="ermil")
    b = await tts.synth("одинаковый текст", voice="alena")
    assert a is not b


@pytest.mark.asyncio
async def test_synth_unknown_voice_falls_back_to_default() -> None:
    out = await tts.synth("Текст", voice="not_a_voice")
    assert out.voice == "ermil"


@pytest.mark.asyncio
async def test_synth_empty_text_raises() -> None:
    with pytest.raises(ValueError):
        await tts.synth("   ")


def test_to_dict_excludes_audio_payload() -> None:
    res = tts.TtsResult(
        audio_bytes=b"\x00" * 100,
        mime="audio/wav",
        duration_s=1.234,
        provider="mock",
        voice="ermil",
        model="x",
    )
    payload = res.to_dict()
    assert payload == {
        "audio_size_bytes": 100,
        "mime": "audio/wav",
        "duration_s": 1.23,
        "provider": "mock",
        "voice": "ermil",
        "model": "x",
    }


@pytest.mark.asyncio
async def test_cache_evicts_oldest_when_full() -> None:
    cache = tts._Cache(capacity=2)
    cache.put("a", tts.TtsResult(b"a", "x", 0.1, "mock", "ermil", "m"))
    cache.put("b", tts.TtsResult(b"b", "x", 0.1, "mock", "ermil", "m"))
    cache.put("c", tts.TtsResult(b"c", "x", 0.1, "mock", "ermil", "m"))
    assert cache.get("a") is None
    assert cache.get("b") is not None
    assert cache.get("c") is not None
