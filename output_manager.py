"""Persist transcripts, QA findings, metadata, and the master report."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from bug_analyzer import analyze_transcript, findings_as_dicts, findings_to_markdown
from config import Settings
from transcriber import save_transcript

_MASTER_REPORT_LOCK = threading.Lock()


def write_metadata(state: dict[str, Any], settings: Settings) -> Path:
    call_id = state["call_id"]
    scenario = state["scenario"]
    metadata = {
        "call_id": call_id,
        "call_uuid": state.get("call_uuid"),
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "status": state.get("status"),
        "started_at": state.get("started_at"),
        "ended_at": state.get("ended_at"),
        "recording_path": state.get("recording_path"),
        "recording_uuid": state.get("recording_uuid"),
        "recording_size_bytes": state.get("recording_size_bytes"),
        "turn_count": len(state.get("turns", [])),
        "errors": state.get("errors", []),
    }
    metadata_path = settings.calls_dir / f"metadata-{call_id}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata_path


def write_call_outputs(state: dict[str, Any], settings: Settings) -> dict[str, str]:
    call_id = state["call_id"]
    scenario = state["scenario"]
    turns = state.get("turns", [])
    transcript, transcript_path = save_transcript(turns, call_id, settings.calls_dir)

    findings = analyze_transcript(scenario, transcript, settings=settings)
    report_text = findings_to_markdown(call_id, scenario, findings)
    report_path = settings.calls_dir / f"bugs-{call_id}.md"
    report_path.write_text(report_text, encoding="utf-8")

    findings_path = settings.calls_dir / f"findings-{call_id}.json"
    findings_path.write_text(
        json.dumps(findings_as_dicts(findings), indent=2), encoding="utf-8"
    )

    metadata_path = write_metadata(state, settings)

    master_path = settings.calls_dir / "BUG_REPORT.md"
    with _MASTER_REPORT_LOCK:
        heading = f"\n\n---\n\n{report_text}\n"
        with master_path.open("a", encoding="utf-8") as handle:
            handle.write(heading)

    return {
        "transcript": str(transcript_path),
        "bug_report": str(report_path),
        "findings": str(findings_path),
        "metadata": str(metadata_path),
    }
