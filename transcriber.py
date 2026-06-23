"""Build reliable speaker-labeled transcripts from captured conversation turns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def format_timestamp(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


def build_transcript_text(turns: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for turn in turns:
        timestamp = format_timestamp(float(turn.get("timestamp", 0)))
        speaker = str(turn.get("speaker", "UNKNOWN")).upper()
        text = str(turn.get("text", "")).strip()
        confidence = turn.get("confidence")
        suffix = ""
        if confidence is not None:
            try:
                suffix = f" [ASR confidence: {float(confidence):.2f}]"
            except (TypeError, ValueError):
                pass
        lines.append(f"[{timestamp}] {speaker}: {text}{suffix}")
    return "\n".join(lines)


def save_transcript(
    turns: list[dict[str, Any]],
    call_id: str,
    output_dir: str | Path = "calls",
) -> tuple[str, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    transcript_text = build_transcript_text(turns)
    transcript_path = directory / f"transcript-{call_id}.txt"
    transcript_path.write_text(
        f"Call ID: {call_id}\n{'=' * 72}\n{transcript_text}\n{'=' * 72}\n",
        encoding="utf-8",
    )
    turns_path = directory / f"turns-{call_id}.json"
    turns_path.write_text(json.dumps(turns, indent=2), encoding="utf-8")
    return transcript_text, transcript_path
