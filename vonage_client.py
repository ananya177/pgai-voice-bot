"""Minimal Vonage Voice API client using JWT authentication."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import jwt
import requests

from config import Settings

VOICE_API_URL = "https://api.nexmo.com/v1/calls"
ALLOWED_RECORDING_HOST_SUFFIXES = (".nexmo.com", ".vonage.com")


class VonageVoiceClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def generate_jwt(self) -> str:
        private_key = self.settings.vonage_private_key_path.read_text(
            encoding="utf-8"
        )
        now = int(time.time())
        payload = {
            "application_id": self.settings.vonage_application_id,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "exp": now + 3600,
        }
        return jwt.encode(payload, private_key, algorithm="RS256")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.generate_jwt()}",
            "Content-Type": "application/json",
        }

    def create_call(self, answer_url: str, event_url: str) -> dict:
        self.settings.validate_target_number()
        payload = {
            "to": [{"type": "phone", "number": self.settings.target_number}],
            "from": {"type": "phone", "number": self.settings.vonage_number},
            "answer_url": [answer_url],
            "answer_method": "GET",
            "event_url": [event_url],
            "event_method": "POST",
        }
        response = self.session.post(
            VOICE_API_URL,
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(
                f"Vonage create-call failed ({response.status_code}): {response.text}"
            )
        return response.json()

    def download_recording(self, recording_url: str, destination: Path) -> Path:
        parsed = urlparse(recording_url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not hostname.endswith(
            ALLOWED_RECORDING_HOST_SUFFIXES
        ):
            raise ValueError("Refusing to download a recording from an untrusted URL.")

        response = self.session.get(
            recording_url,
            headers={"Authorization": f"Bearer {self.generate_jwt()}"},
            timeout=120,
        )
        response.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        return destination
