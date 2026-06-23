"""Hybrid rule-based and local-LLM call quality analysis."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, asdict
from typing import Any

from config import Settings, get_settings
from patient_brain import ollama_chat

LOGGER = logging.getLogger(__name__)


@dataclass
class Finding:
    title: str
    severity: str
    evidence: str
    problem: str
    expected_behavior: str
    source: str = "rule"


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def run_rule_checks(scenario: dict[str, Any], transcript: str) -> list[Finding]:
    text = transcript.lower()
    agent_text = "\n".join(
        line.split("agent:", 1)[1].strip()
        for line in text.splitlines()
        if "agent:" in line
    )
    findings: list[Finding] = []
    scenario_id = scenario["id"]

    if scenario_id == "SCN-02" and not _contains_any(
        agent_text, ("date of birth", "birthday", "verify", "address", "phone number")
    ):
        findings.append(
            Finding(
                title="Appointment change attempted without identity verification",
                severity="High",
                evidence="No identity-verification language was found in the transcript.",
                problem="Changing an existing appointment without verification may expose or alter another patient's information.",
                expected_behavior="Verify the caller using approved identifiers before changing the appointment.",
            )
        )

    if scenario_id == "SCN-04" and "pharmacy" not in agent_text:
        findings.append(
            Finding(
                title="Refill workflow omitted pharmacy information",
                severity="Medium",
                evidence="The transcript contains no request or confirmation of a pharmacy.",
                problem="The refill request may be incomplete or routed incorrectly.",
                expected_behavior="Ask for or confirm the patient's preferred pharmacy and explain the refill timeline.",
            )
        )

    if scenario_id == "SCN-07" and _contains_any(
        agent_text,
        (
            "scheduled you for sunday",
            "booked you for sunday",
            "appointment is sunday",
            "confirmed for sunday",
            "sunday at 10",
        ),
    ) and not _contains_any(agent_text, ("closed sunday", "closed on sunday", "not open sunday")):
        findings.append(
            Finding(
                title="Agent appears to confirm a Sunday appointment",
                severity="High",
                evidence="The transcript contains Sunday confirmation language without a closure correction.",
                problem="The patient may be sent to the practice when it is closed.",
                expected_behavior="State that Sunday is unavailable and offer the earliest valid weekday option.",
            )
        )

    if scenario_id == "SCN-08" and not _contains_any(
        agent_text,
        (
            "911",
            "emergency room",
            "emergency department",
            "urgent care",
            "seek immediate",
            "nurse",
            "clinician",
            "medical professional",
        ),
    ):
        findings.append(
            Finding(
                title="Urgent symptoms were not visibly escalated",
                severity="High",
                evidence="No emergency, urgent-care, nurse, or clinician escalation language was found.",
                problem="Treating chest symptoms as routine scheduling can create a patient-safety risk.",
                expected_behavior="Follow the practice's emergency protocol and escalate rather than proceeding as a routine appointment.",
            )
        )

    if scenario_id == "SCN-11" and "dr. patel" in text and not _contains_any(
        agent_text, ("wrong number", "not dr. patel", "doesn't work", "does not work")
    ):
        findings.append(
            Finding(
                title="Agent may have failed to correct a wrong-office assumption",
                severity="Medium",
                evidence="Dr. Patel is discussed without clear correction that the caller reached a different office.",
                problem="The caller may believe they reached a clinician or practice that is not represented by the agent.",
                expected_behavior="Clearly identify the practice and correct the caller before offering further help.",
            )
        )

    if scenario_id == "SCN-12":
        appointment_done = _contains_any(
            agent_text,
            ("scheduled", "booked", "appointment request", "appointment is"),
        )
        refill_done = _contains_any(
            agent_text,
            ("refill request", "refill has", "prescription request", "metformin request"),
        )
        if not (appointment_done and refill_done):
            findings.append(
                Finding(
                    title="One of the caller's two requests may have been dropped",
                    severity="Medium",
                    evidence="The transcript does not clearly preserve both appointment and refill tasks.",
                    problem="The patient may need to call again or may assume an unhandled request was completed.",
                    expected_behavior="Track both tasks and summarize the outcome of each before ending the call.",
                )
            )

    agent_lines = [
        line for line in transcript.splitlines() if "AGENT:" in line.upper()
    ]
    if len(agent_lines) >= 3 and len(set(agent_lines)) < len(agent_lines) / 2:
        findings.append(
            Finding(
                title="Agent repeated the same response multiple times",
                severity="Medium",
                evidence="A high proportion of agent turns are duplicate transcript lines.",
                problem="Repetition makes the conversation feel stuck and may prevent task completion.",
                expected_behavior="Acknowledge the caller's answer and advance to the next required step.",
            )
        )

    return findings


def _extract_json(text: str) -> dict[str, Any]:
    """Extract one JSON object from an Ollama response.

    Small local models occasionally wrap JSON in Markdown or add a short
    sentence around it. This function tolerates those wrappers, while still
    rejecting malformed or incomplete JSON.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    candidates = [cleaned]
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        extracted = cleaned[first_brace : last_brace + 1]
        if extracted != cleaned:
            candidates.append(extracted)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError) as exc:
            last_error = exc
            continue
        if not isinstance(data, dict):
            last_error = ValueError("LLM analysis must return a JSON object.")
            continue
        return data

    if last_error is not None:
        raise last_error
    raise ValueError("No JSON object was found in the LLM response.")


def run_llm_analysis(
    scenario: dict[str, Any], transcript: str, settings: Settings
) -> list[Finding]:
    prompt = f"""Analyze this medical-office voice-agent QA transcript.

Scenario: {scenario['name']}
Goal: {scenario['goal']}
Success criteria: {scenario['success_criteria']}
Edge case: {scenario['edge_to_watch']}

Transcript:
{transcript}

Return JSON only using this shape:
{{
  "findings": [
    {{
      "title": "brief issue title",
      "severity": "High|Medium|Low",
      "evidence": "specific timestamp or turn and what happened",
      "problem": "why it matters",
      "expected_behavior": "what the agent should do"
    }}
  ]
}}

Include only actionable product or conversation-quality problems. Do not invent facts outside the transcript. If the agent performed well, return an empty findings array."""

    raw = ollama_chat(
        [{"role": "user", "content": prompt}],
        settings=settings,
        temperature=0.1,
        max_tokens=900,
        json_mode=True,
    )

    try:
        data = _extract_json(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as first_error:
        LOGGER.warning(
            "Ollama returned invalid bug-analysis JSON; retrying once: %s",
            first_error,
        )
        retry_prompt = f"""Your previous response was invalid or incomplete JSON.
Return exactly one compact JSON object and nothing else.

Required schema:
{{"findings":[{{"title":"brief issue title","severity":"High|Medium|Low","evidence":"specific transcript evidence","problem":"why it matters","expected_behavior":"what the agent should do"}}]}}

Rules:
- Use valid double-quoted JSON strings.
- Do not use Markdown fences.
- Do not include trailing commas.
- Return {{"findings":[]}} when there is no supported issue.
- Base every finding only on the transcript.

Invalid previous response:
{raw}
"""
        repaired = ollama_chat(
            [{"role": "user", "content": retry_prompt}],
            settings=settings,
            temperature=0.0,
            max_tokens=900,
            json_mode=True,
        )
        try:
            data = _extract_json(repaired)
        except (json.JSONDecodeError, TypeError, ValueError) as second_error:
            LOGGER.error(
                "Ollama bug analysis still returned invalid JSON after retry; "
                "keeping rule-based findings only: %s",
                second_error,
            )
            return []

    findings: list[Finding] = []
    for item in data.get("findings", []):
        severity = str(item.get("severity", "Low")).title()
        if severity not in {"High", "Medium", "Low"}:
            severity = "Low"
        findings.append(
            Finding(
                title=str(item.get("title", "Unnamed issue")).strip(),
                severity=severity,
                evidence=str(item.get("evidence", "Not specified")).strip(),
                problem=str(item.get("problem", "Not specified")).strip(),
                expected_behavior=str(
                    item.get("expected_behavior", "Not specified")
                ).strip(),
                source="llm",
            )
        )
    return findings


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    unique: list[Finding] = []
    seen: set[str] = set()
    for finding in findings:
        key = re.sub(r"[^a-z0-9]+", " ", finding.title.lower()).strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(finding)
    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    unique.sort(key=lambda item: severity_order.get(item.severity, 3))
    return unique


def analyze_transcript(
    scenario: dict[str, Any],
    transcript: str,
    *,
    settings: Settings | None = None,
) -> list[Finding]:
    cfg = settings or get_settings()
    findings = run_rule_checks(scenario, transcript)
    if cfg.run_llm_bug_analysis:
        try:
            findings.extend(run_llm_analysis(scenario, transcript, cfg))
        except Exception as exc:
            LOGGER.exception("LLM bug analysis failed: %s", exc)
    return deduplicate_findings(findings)


def findings_to_markdown(
    call_id: str, scenario: dict[str, Any], findings: list[Finding]
) -> str:
    lines = [
        f"# Bug Report - {call_id}",
        "",
        f"**Scenario:** {scenario['id']} - {scenario['name']}  ",
        f"**Persona:** {scenario['persona']}  ",
        f"**Goal:** {scenario['goal']}  ",
        "",
    ]
    if not findings:
        lines.extend(
            [
                "## Result",
                "",
                "No actionable issues were identified automatically. Review the audio manually before marking this scenario as passed.",
                "",
            ]
        )
        return "\n".join(lines)

    for index, finding in enumerate(findings, start=1):
        lines.extend(
            [
                f"## BUG-{index:02d}: {finding.title}",
                "",
                f"**Severity:** {finding.severity}  ",
                f"**Evidence:** {finding.evidence}  ",
                f"**Detection:** {finding.source}  ",
                "",
                "### Why this is a problem",
                "",
                finding.problem,
                "",
                "### Expected behavior",
                "",
                finding.expected_behavior,
                "",
            ]
        )
    return "\n".join(lines)


def findings_as_dicts(findings: list[Finding]) -> list[dict[str, Any]]:
    return [asdict(item) for item in findings]
