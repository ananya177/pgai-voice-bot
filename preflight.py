"""Configuration checks that do not place a phone call."""

from __future__ import annotations

import os
import shutil

from config import OFFICIAL_TEST_NUMBER, get_settings
from patient_brain import check_ollama


def line(ok: bool, message: str) -> None:
    symbol = "PASS" if ok else "FAIL"
    print(f"[{symbol}] {message}")


def main() -> int:
    settings = get_settings()
    failures = 0

    target_ok = settings.target_number == OFFICIAL_TEST_NUMBER
    line(target_ok, "Target number is locked to the official PGAI test line.")
    failures += 0 if target_ok else 1

    number_ok = bool(settings.vonage_number)
    line(number_ok, "VONAGE_NUMBER is configured.")
    failures += 0 if number_ok else 1

    app_ok = bool(settings.vonage_application_id)
    line(app_ok, "VONAGE_APPLICATION_ID is configured.")
    failures += 0 if app_ok else 1

    key_ok = settings.vonage_private_key_path.exists()
    line(key_ok, f"Private key exists at {settings.vonage_private_key_path}.")
    failures += 0 if key_ok else 1

    skip_tunnel = os.getenv("SKIP_TUNNEL", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if skip_tunnel:
        tunnel_ok = settings.base_url.startswith("https://")
        line(tunnel_ok, "SKIP_TUNNEL uses a public HTTPS BASE_URL.")
    else:
        tunnel_ok = shutil.which("cloudflared") is not None
        line(tunnel_ok, "cloudflared is installed.")
    failures += 0 if tunnel_ok else 1

    ollama_ok, ollama_message = check_ollama(settings)
    line(ollama_ok, ollama_message)
    failures += 0 if ollama_ok or not settings.require_ollama else 1

    print(f"\nTTS provider: {settings.tts_provider}")
    print(f"Recording enabled: {settings.recording_enabled}")
    print(f"Calls directory: {settings.calls_dir.resolve()}")

    if failures:
        print(f"\nPreflight found {failures} blocking issue(s). No call was placed.")
        return 1
    print("\nPreflight passed. You are ready to start the server and run one test call.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
