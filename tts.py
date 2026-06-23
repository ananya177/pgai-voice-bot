"""Text-to-speech helpers for patient audio."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from gtts import gTTS


VOICE_PROFILES = {
    "us": {"lang": "en", "tld": "com"},
    "uk": {"lang": "en", "tld": "co.uk"},
    "au": {"lang": "en", "tld": "com.au"},
}


def prepare_for_speech(text: str) -> str:
    """Make common medical and scheduling text sound less robotic."""
    replacements = {
        "mg": " milligrams",
        "DOB": "date of birth",
        "PPO": "P P O",
        "HMO": "H M O",
        "911": "nine one one",
    }
    prepared = text
    for old, new in replacements.items():
        prepared = re.sub(rf"\b{re.escape(old)}\b", new, prepared, flags=re.IGNORECASE)
    prepared = re.sub(r"\s+", " ", prepared).strip()
    return prepared


def text_to_speech(
    text: str,
    voice_profile: str = "us",
    output_dir: str | os.PathLike[str] = "calls",
) -> Path:
    """Create an MP3 with gTTS and return its path."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    profile = VOICE_PROFILES.get(voice_profile, VOICE_PROFILES["us"])
    filename = output_path / f"tts-{uuid.uuid4().hex[:10]}.mp3"
    gTTS(
        text=prepare_for_speech(text),
        lang=profile["lang"],
        tld=profile["tld"],
        slow=False,
    ).save(str(filename))
    return filename


def get_voice_profile_for_persona(persona: str) -> str:
    """Use a consistent US voice unless a persona explicitly states an accent."""
    lower = persona.lower()
    if "british" in lower or "uk accent" in lower:
        return "uk"
    if "australian" in lower:
        return "au"
    return "us"
