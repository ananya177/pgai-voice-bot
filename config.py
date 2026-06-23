"""Application configuration and safety validation."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OFFICIAL_TEST_NUMBER = "18054398008"


def normalize_phone(value: str | None) -> str:
    """Return only decimal digits from a phone number."""
    return re.sub(r"\D", "", value or "")


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    port: int
    base_url: str
    calls_dir: Path
    target_number: str
    vonage_number: str
    vonage_application_id: str
    vonage_private_key_path: Path
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: int
    require_ollama: bool
    tts_provider: str
    max_turns: int
    max_silence_retries: int
    end_on_silence_seconds: int
    recording_enabled: bool
    split_recording: bool
    run_llm_bug_analysis: bool
    server_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            port=int(os.getenv("PORT", "5000")),
            base_url=os.getenv("BASE_URL", "http://localhost:5000").rstrip("/"),
            calls_dir=Path(os.getenv("CALLS_DIR", "calls")),
            target_number=normalize_phone(
                os.getenv("TARGET_PHONE_NUMBER", OFFICIAL_TEST_NUMBER)
            ),
            vonage_number=normalize_phone(os.getenv("VONAGE_NUMBER")),
            vonage_application_id=os.getenv("VONAGE_APPLICATION_ID", "").strip(),
            vonage_private_key_path=Path(
                os.getenv("VONAGE_PRIVATE_KEY_PATH", "private.key")
            ),
            ollama_base_url=os.getenv(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            ).rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "gemma3:4b").strip(),
            ollama_timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")),
            require_ollama=env_bool("REQUIRE_OLLAMA", True),
            tts_provider=os.getenv("TTS_PROVIDER", "gtts").strip().lower(),
            max_turns=int(os.getenv("MAX_TURNS", "20")),
            max_silence_retries=int(os.getenv("MAX_SILENCE_RETRIES", "2")),
            end_on_silence_seconds=int(os.getenv("END_ON_SILENCE_SECONDS", "2")),
            recording_enabled=env_bool("ENABLE_RECORDING", True),
            split_recording=env_bool("ENABLE_SPLIT_RECORDING", True),
            run_llm_bug_analysis=env_bool("ENABLE_LLM_BUG_ANALYSIS", True),
            server_url=os.getenv("SERVER_URL", "http://localhost:5000").rstrip("/"),
        )

    def ensure_directories(self) -> None:
        self.calls_dir.mkdir(parents=True, exist_ok=True)

    def validate_target_number(self) -> None:
        """Hard fail if the configured number is not the official challenge number."""
        if self.target_number != OFFICIAL_TEST_NUMBER:
            raise ValueError(
                "Safety check failed: this project may call only the official "
                f"assessment number +{OFFICIAL_TEST_NUMBER}."
            )

    def validate_for_real_call(self) -> list[str]:
        """Return a list of missing or invalid real-call settings."""
        errors: list[str] = []
        try:
            self.validate_target_number()
        except ValueError as exc:
            errors.append(str(exc))

        if not self.vonage_number:
            errors.append("VONAGE_NUMBER is missing.")
        if not self.vonage_application_id:
            errors.append("VONAGE_APPLICATION_ID is missing.")
        if not self.vonage_private_key_path.exists():
            errors.append(
                f"Vonage private key not found: {self.vonage_private_key_path}"
            )
        if not self.base_url.startswith("https://"):
            errors.append(
                "BASE_URL must be a public HTTPS URL for Vonage webhooks. "
                "Start the project with start.py or set BASE_URL manually."
            )
        if self.tts_provider not in {"gtts", "vonage"}:
            errors.append("TTS_PROVIDER must be either 'gtts' or 'vonage'.")
        return errors


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings.from_env()
    settings.ensure_directories()
    return settings


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
