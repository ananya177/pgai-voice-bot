#!/usr/bin/env python3
"""Preflight a PGAI challenge repository before final submission.

Usage:
    python prepare_submission.py
    python prepare_submission.py --calls-dir calls --selected selected_calls.txt

The script does not judge conversational quality. It checks that manually selected
call IDs have paired evidence and generates CALL_MANIFEST.md/CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TIMESTAMP_RE = re.compile(r"\[(\d{2}):(\d{2})\]")
SCENARIO_RE = re.compile(r"^(SCN-\d{2})-")
REQUIRED_REPO_FILES = (
    "README.md",
    "ARCHITECTURE.md",
    "BUG_REPORT.md",
    ".env.example",
)
SECRET_NAMES = {".env", "private.key", "private.pem", "vonage.key"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


@dataclass
class CallEvidence:
    call_id: str
    scenario_id: str
    transcript: Path | None
    recording: Path | None
    bug_report: Path | None
    findings: Path | None
    metadata: Path | None
    transcript_seconds: int | None
    audio_seconds: float | None
    patient_turns: int
    agent_turns: int


def read_selected(path: Path) -> list[str]:
    if not path.exists():
        return []
    result: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            result.append(line)
    return result


def last_transcript_time(path: Path | None) -> tuple[int | None, int, int]:
    if path is None or not path.exists():
        return None, 0, 0
    text = path.read_text(encoding="utf-8", errors="replace")
    times = [(int(m.group(1)) * 60 + int(m.group(2))) for m in TIMESTAMP_RE.finditer(text)]
    patient_turns = len(re.findall(r"\]\s+PATIENT:", text))
    agent_turns = len(re.findall(r"\]\s+AGENT:", text))
    return (max(times) if times else None), patient_turns, agent_turns


def duration_with_ffprobe(path: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return None


def duration_with_afinfo(path: Path) -> float | None:
    if not shutil.which("afinfo"):
        return None
    completed = subprocess.run(
        ["afinfo", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"estimated duration:\s*([\d.]+)\s*sec", completed.stdout)
    return float(match.group(1)) if match else None


def audio_duration(path: Path | None) -> float | None:
    if path is None or not path.exists():
        return None
    return duration_with_ffprobe(path) or duration_with_afinfo(path)


def find_recording(calls_dir: Path, call_id: str) -> Path | None:
    for suffix in ("mp3", "ogg", "wav", "m4a"):
        candidate = calls_dir / f"recording-{call_id}.{suffix}"
        if candidate.exists():
            return candidate
    return None


def build_evidence(calls_dir: Path, call_id: str) -> CallEvidence:
    scenario_match = SCENARIO_RE.match(call_id)
    scenario_id = scenario_match.group(1) if scenario_match else "UNKNOWN"
    transcript = calls_dir / f"transcript-{call_id}.txt"
    bug_report = calls_dir / f"bugs-{call_id}.md"
    findings = calls_dir / f"findings-{call_id}.json"
    metadata = calls_dir / f"metadata-{call_id}.json"
    transcript = transcript if transcript.exists() else None
    bug_report = bug_report if bug_report.exists() else None
    findings = findings if findings.exists() else None
    metadata = metadata if metadata.exists() else None
    recording = find_recording(calls_dir, call_id)
    transcript_seconds, patient_turns, agent_turns = last_transcript_time(transcript)
    return CallEvidence(
        call_id=call_id,
        scenario_id=scenario_id,
        transcript=transcript,
        recording=recording,
        bug_report=bug_report,
        findings=findings,
        metadata=metadata,
        transcript_seconds=transcript_seconds,
        audio_seconds=audio_duration(recording),
        patient_turns=patient_turns,
        agent_turns=agent_turns,
    )


def fmt_seconds(value: float | int | None) -> str:
    if value is None:
        return "unknown"
    seconds = int(round(value))
    return f"{seconds // 60}:{seconds % 60:02d}"


def file_link(path: Path | None) -> str:
    return str(path).replace("\\", "/") if path else "MISSING"


def generate_manifest(evidence: list[CallEvidence], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "CALL_MANIFEST.csv"
    md_path = out_dir / "CALL_MANIFEST.md"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scenario",
                "call_id",
                "audio_duration",
                "transcript_last_timestamp",
                "patient_turns",
                "agent_turns",
                "recording",
                "transcript",
                "bug_report",
                "metadata",
                "review_status",
            ]
        )
        for item in evidence:
            writer.writerow(
                [
                    item.scenario_id,
                    item.call_id,
                    fmt_seconds(item.audio_seconds),
                    fmt_seconds(item.transcript_seconds),
                    item.patient_turns,
                    item.agent_turns,
                    file_link(item.recording),
                    file_link(item.transcript),
                    file_link(item.bug_report),
                    file_link(item.metadata),
                    "MANUALLY APPROVED",
                ]
            )

    lines = [
        "# Final Call Manifest",
        "",
        "Every row below must be manually reviewed against the recording.",
        "",
        "| Scenario | Call ID | Audio | Transcript time | Turns P/A | Recording | Transcript | Report |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]
    for item in evidence:
        lines.append(
            "| {scenario} | `{call}` | {audio} | {transcript_time} | {p}/{a} | `{recording}` | `{transcript}` | `{report}` |".format(
                scenario=item.scenario_id,
                call=item.call_id,
                audio=fmt_seconds(item.audio_seconds),
                transcript_time=fmt_seconds(item.transcript_seconds),
                p=item.patient_turns,
                a=item.agent_turns,
                recording=file_link(item.recording),
                transcript=file_link(item.transcript),
                report=file_link(item.bug_report),
            )
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tracked_files() -> list[str]:
    if not Path(".git").exists() or not shutil.which("git"):
        return []
    completed = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=False
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def secret_warnings() -> list[str]:
    warnings: list[str] = []
    for tracked in tracked_files():
        path = Path(tracked)
        if path.name in SECRET_NAMES or path.suffix.lower() in SECRET_SUFFIXES:
            warnings.append(f"Tracked secret-like file: {tracked}")
    return warnings


def metadata_warning(item: CallEvidence) -> list[str]:
    warnings: list[str] = []
    if not item.metadata:
        return warnings
    try:
        data = json.loads(item.metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        warnings.append(f"{item.call_id}: metadata JSON cannot be parsed")
        return warnings
    status = str(data.get("status", "")).lower()
    if status and status not in {"completed", "done", "finished"}:
        warnings.append(f"{item.call_id}: metadata status is {status!r}")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calls-dir", type=Path, default=Path("calls"))
    parser.add_argument("--selected", type=Path, default=Path("selected_calls.txt"))
    parser.add_argument("--output-dir", type=Path, default=Path("submission"))
    args = parser.parse_args()

    selected = read_selected(args.selected)
    blockers: list[str] = []
    warnings: list[str] = []

    if len(selected) < 10:
        blockers.append(
            f"Only {len(selected)} call IDs are selected; the challenge requires at least 10."
        )
    if len(selected) != len(set(selected)):
        blockers.append("selected_calls.txt contains duplicate call IDs.")

    evidence = [build_evidence(args.calls_dir, call_id) for call_id in selected]
    for item in evidence:
        if not item.recording:
            blockers.append(f"{item.call_id}: missing MP3/OGG recording")
        if not item.transcript:
            blockers.append(f"{item.call_id}: missing transcript")
        if item.transcript_seconds is not None and item.transcript_seconds < 55:
            warnings.append(
                f"{item.call_id}: transcript ends at {fmt_seconds(item.transcript_seconds)}; manually confirm this is a full call."
            )
        if item.agent_turns < 3 or item.patient_turns < 3:
            warnings.append(
                f"{item.call_id}: only {item.patient_turns} patient and {item.agent_turns} agent turns."
            )
        warnings.extend(metadata_warning(item))

    for required in REQUIRED_REPO_FILES:
        if not Path(required).exists():
            blockers.append(f"Missing required repository file: {required}")

    warnings.extend(secret_warnings())
    generate_manifest(evidence, args.output_dir)

    print(f"Selected calls: {len(selected)}")
    print(f"Manifest: {args.output_dir / 'CALL_MANIFEST.md'}")
    print(f"CSV: {args.output_dir / 'CALL_MANIFEST.csv'}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  - {warning}")

    if blockers:
        print("\nSubmission blockers:")
        for blocker in blockers:
            print(f"  - {blocker}")
        return 1

    print("\nNo structural blockers found. Manual audio and bug verification is still required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
