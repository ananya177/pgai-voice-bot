from __future__ import annotations

from pathlib import Path

import pytest

from config import OFFICIAL_TEST_NUMBER, Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    key_path = tmp_path / "private.key"
    key_path.write_text("test-key", encoding="utf-8")
    return Settings(
        port=5000,
        base_url="https://example.trycloudflare.com",
        calls_dir=tmp_path / "calls",
        target_number=OFFICIAL_TEST_NUMBER,
        vonage_number="15551234567",
        vonage_application_id="test-application-id",
        vonage_private_key_path=key_path,
        ollama_base_url="http://localhost:11434",
        ollama_model="gemma3:4b",
        ollama_timeout_seconds=1,
        require_ollama=False,
        tts_provider="vonage",
        max_turns=20,
        max_silence_retries=2,
        end_on_silence_seconds=2,
        recording_enabled=True,
        split_recording=True,
        run_llm_bug_analysis=False,
        server_url="http://localhost:5000",
    )
