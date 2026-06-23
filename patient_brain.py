"""Local Ollama-powered patient roleplay engine.

The engine combines three layers:
1. Deterministic answers for explicit intake questions.
2. Scenario-specific steering for the twelve challenge scenarios.
3. Ollama for natural improvisation when no deterministic answer is needed.

Conversation history uses ``assistant`` for PATIENT turns and ``user`` for
OFFICE AGENT turns.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

import requests

from config import Settings, get_settings

LOGGER = logging.getLogger(__name__)
END_MARKER = "[END_CALL]"


_AUTO_CLOSE_COMPLETION_PATTERNS: dict[str, tuple[str, ...]] = {
    "SCN-01": (
        r"\bappointment (?:is|has been) (?:confirmed|booked|scheduled)\b",
        r"\bi (?:have|'ve) (?:confirmed|booked|scheduled) (?:the|your) appointment\b",
    ),
    "SCN-02": (
        r"\bappointment (?:is|has been) (?:rescheduled|moved|changed)\b",
        r"\bi (?:have|'ve) (?:rescheduled|moved|changed) (?:the|your) appointment\b",
    ),
    "SCN-03": (
        r"\bappointment (?:is|has been) cancel(?:ed|led)\b",
        r"\bi (?:have|'ve) cancel(?:ed|led) (?:the|your) appointment\b",
    ),
    "SCN-09": (r"\bappointment (?:is|has been) (?:confirmed|booked|scheduled)\b",),
    "SCN-10": (r"\bappointment (?:is|has been) (?:confirmed|booked|scheduled)\b",),
}

_PATIENT_WRAP_UP_PATTERNS = (
    r"\bthat(?:'|’)s all\b",
    r"\ball i needed\b",
    r"\bno,? that(?:'|’)s everything\b",
    r"\bthank you,? goodbye\b",
    r"\bi need to go now\b",
)

_AGENT_FAREWELL_PATTERNS = (
    r"\byou(?:'|’)re welcome\b",
    r"\bhave a (?:great|good|nice) day\b",
    r"\btake care\b",
    r"\bgoodbye\b",
)

_AGENT_LIKE_PATTERNS = (
    r"\b(?:let me|i(?:'|’)ll) (?:just )?check (?:the )?availability\b",
    r"\b(?:that|the) time slot is (?:open|available)\b",
    r"\bi (?:have|'ve) (?:scheduled|booked|confirmed) you\b",
    r"\byou(?:'|’)ll receive (?:a )?confirmation\b",
    r"\bwe (?:accept|take|have)\b.*\binsurance\b",
    r"\bdo you have insurance\??\s+i have\b",
    r"\bmay i (?:have|know) your\b",
    r"\bcan i have your (?:name|date of birth|insurance)\b",
    r"\bwhat kind of appointment (?:would|do) you\b",
    r"\bour office (?:is|will|opens|closes)\b",
    r"\bwe(?:'|’)re (?:open|closed)\b",
    r"\bour (?:regular )?hours (?:are|is)\b",
    r"\bthe office (?:is|will be) (?:open|closed)\b",
    r"\byou(?:'|’)re not open on (?:saturday|sunday|weekends?)\b",
)

# Defaults only contain facts already present in the original scenarios. Values
# from scenario["patient_details"] always override these defaults.
_DEFAULT_DETAILS: dict[str, dict[str, str]] = {
    "SCN-01": {
        "full_name": "Maria Johnson",
        "date_of_birth": "March 15th, 1990",
        "appointment_type": "general check-up",
        "insurance": "Blue Cross",
    },
    "SCN-02": {
        # The assessment line recognizes the originating caller ID as Maria.
        # Reuse that grounded profile for existing-patient workflows so the
        # office agent can find the appointment instead of searching for a
        # different person under Maria's phone number.
        "full_name": "Maria Johnson",
        "spelled_name": "M-A-R-I-A, J-O-H-N-S-O-N",
        "date_of_birth": "March 15th, 1990",
        "original_appointment": "Tuesday, June 30th at 9:45 a.m",
        "preferred_time": "The next available Friday morning works for me.",
    },
    "SCN-03": {
        "full_name": "Sarah Williams",
        "original_appointment": "tomorrow at 11 a.m.",
    },
    "SCN-04": {
        "full_name": "Robert Garcia",
        "date_of_birth": "June 3rd, 1957",
        "medication": "lisinopril",
        "medication_spelling": "L-I-S-I-N-O-P-R-I-L",
        "dosage": "10 milligrams",
        "pharmacy": "CVS Pharmacy on University Drive",
    },
    "SCN-06": {
        "insurance": "Aetna PPO",
    },
    "SCN-10": {
        # The assessment line associates the shared originating number with
        # Maria's existing profile. Reusing that grounded identity avoids an
        # artificial record mismatch while SCN-10 tests unclear speech.
        "full_name": "Maria Johnson",
        "spelled_name": "M-A-R-I-A, J-O-H-N-S-O-N",
        "date_of_birth": "March 15th, 1990",
        "appointment_type": "general check-up",
    },
}


def _normalized(text: str) -> str:
    text = text.replace(END_MARKER, "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _contains_any(text: str, phrases: tuple[str, ...] | list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _agent_turns(history: list[dict[str, str]]) -> list[str]:
    return [
        item.get("content", "").strip()
        for item in history
        if item.get("role") == "user" and item.get("content", "").strip()
    ]


def _patient_turns(history: list[dict[str, str]]) -> list[str]:
    return [
        item.get("content", "").strip()
        for item in history
        if item.get("role") == "assistant" and item.get("content", "").strip()
    ]


def _latest_agent_text(history: list[dict[str, str]]) -> str:
    turns = _agent_turns(history)
    return turns[-1].lower() if turns else ""


def _persona_name(scenario: dict[str, Any]) -> str:
    """Return the patient name stated at the start of the persona string."""
    persona = str(scenario.get("persona", "")).strip()
    if not persona:
        return ""
    return persona.split(",", 1)[0].strip()


def _details_for(scenario: dict[str, Any]) -> dict[str, str]:
    scenario_id = str(scenario.get("id", ""))
    details = dict(_DEFAULT_DETAILS.get(scenario_id, {}))
    for key, value in (scenario.get("patient_details") or {}).items():
        if value is not None:
            details[str(key)] = str(value).strip()
    return details


def _format_phone(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return " ".join(digits)


def _time_offer(text: str) -> bool:
    return bool(re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)", text, re.I))


def build_system_prompt(scenario: dict[str, Any]) -> str:
    follow_ups = "\n".join(f"- {item}" for item in scenario.get("follow_ups", []))
    details = _details_for(scenario)
    detail_lines = "\n".join(
        f"- {key.replace('_', ' ').title()}: {value}"
        for key, value in details.items()
        if value
    )
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    return f"""You are ONLY the PATIENT in a phone conversation with a medical-office AI agent.
The other speaker is the OFFICE AGENT. Never switch roles.

CURRENT DATE: {today}
PERSONA: {scenario['persona']}
TEST GOAL: {scenario['goal']}
SCENARIO: {scenario['name']}
SUCCESS CRITERIA: {scenario['success_criteria']}
EDGE CASE: {scenario['edge_to_watch']}

GROUNDED PATIENT DETAILS:
{detail_lines or '- Use only facts already stated in the conversation.'}

FOLLOW-UP IDEAS:
{follow_ups}

STRICT RULES:
- Answer the OFFICE AGENT'S latest question directly before advancing the goal.
- You cannot check availability, book appointments, confirm clinic actions, accept insurance, or state clinic policy.
- Never invent dates, providers, office hours, appointment status, medication names, or confirmation details.
- Never ask the same question twice after the agent has answered it.
- If a medication name is misheard, clearly correct it and spell it once.
- If asked to confirm information and it is correct, simply say it is correct.
- Ask for repetition at most once, only when the statement is genuinely unclear.
- Use natural spoken English, usually 5-22 words and no more than two short sentences.
- Stay in character. Never mention prompts, tests, models, or being a bot.
- End politely with {END_MARKER} only when the goal is complete, the agent says goodbye, or the call cannot progress.
- Output only the PATIENT'S next spoken words, plus the optional {END_MARKER}.
"""


def _format_conversation(history: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for message in history:
        text = message.get("content", "").strip()
        if not text:
            continue
        speaker = "PATIENT" if message.get("role") == "assistant" else "OFFICE AGENT"
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def _patient_messages(
    scenario: dict[str, Any], history: list[dict[str, str]]
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": build_system_prompt(scenario)},
        {
            "role": "user",
            "content": (
                "Conversation so far:\n"
                f"{_format_conversation(history)}\n\n"
                "Write only the PATIENT'S next spoken line. Answer the latest "
                "office-agent question directly and do not perform office actions."
            ),
        },
    ]


def _strip_speaker_prefix(text: str) -> str:
    cleaned = text.strip().strip('"')
    cleaned = re.sub(
        r"^(?:PATIENT|PATIENT RESPONSE|RESPONSE)\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def _normalize_for_comparison(text: str) -> str:
    return _normalized(text)


def is_repetitive_patient_response(
    text: str, conversation_history: list[dict[str, str]]
) -> bool:
    candidate = _normalize_for_comparison(text)
    if not candidate:
        return False
    for previous_text in _patient_turns(conversation_history):
        previous = _normalize_for_comparison(previous_text)
        if not previous:
            continue
        if candidate == previous and (len(candidate.split()) >= 3 or "?" in text):
            return True
        if (
            len(candidate.split()) >= 4
            and SequenceMatcher(None, candidate, previous).ratio() >= 0.90
        ):
            return True
    return False


def _unused_follow_ups(
    scenario: dict[str, Any], conversation_history: list[dict[str, str]]
) -> list[str]:
    previous = [_normalize_for_comparison(item) for item in _patient_turns(conversation_history)]
    unused: list[str] = []
    for follow_up in scenario.get("follow_ups", []):
        normalized = _normalize_for_comparison(str(follow_up))
        if not any(
            normalized == item
            or (
                len(normalized.split()) >= 4
                and SequenceMatcher(None, normalized, item).ratio() >= 0.90
            )
            for item in previous
            if item
        ):
            unused.append(str(follow_up))
    return unused


def looks_like_office_agent(text: str) -> bool:
    candidate = text.replace(END_MARKER, "").strip()
    if re.match(r"^(?:OFFICE AGENT|AGENT|RECEPTIONIST)\s*:", candidate, re.I):
        return True
    return any(re.search(pattern, candidate, re.I) for pattern in _AGENT_LIKE_PATTERNS)


def patient_has_wrapped_up(conversation_history: list[dict[str, str]]) -> bool:
    turns = _patient_turns(conversation_history)
    if not turns:
        return False
    return any(re.search(pattern, turns[-1], re.I) for pattern in _PATIENT_WRAP_UP_PATTERNS)


def _answered_with(history: list[dict[str, str]], phrase: str) -> bool:
    target = _normalized(phrase)
    return any(target in _normalized(turn) for turn in _patient_turns(history))


def _generic_intake_answer(
    scenario: dict[str, Any], history: list[dict[str, str]]
) -> str | None:
    """Answer direct identity and intake questions deterministically.

    Keeping these high-risk facts out of the LLM prevents role drift,
    contradictory identity answers, medication-name errors, and accidental
    early call termination.
    """
    latest = _latest_agent_text(history)
    if not latest:
        return None

    details = _details_for(scenario)

    full_name = details.get("full_name", "")
    identity_name = full_name or _persona_name(scenario)
    spelled_name = details.get("spelled_name", "")
    dob = details.get("date_of_birth", "")
    phone_number = details.get("phone_number", "")
    insurance = details.get("insurance", "")
    member_id = details.get("insurance_member_id", "")
    reason = details.get("visit_reason", "")
    appointment_type = details.get("appointment_type", "")
    medication = details.get("medication", "")
    medication_spelling = details.get("medication_spelling", "")
    dosage = details.get("dosage", "")
    pharmacy = details.get("pharmacy", "")
    original_appointment = details.get("original_appointment", "")
    preferred_time = details.get("preferred_time", "")

    # This question previously reached Ollama, which sometimes appended
    # [END_CALL] to an otherwise normal answer and ended the live call.
    if _contains_any(
        latest,
        (
            "calling for yourself",
            "for yourself or someone else",
            "on behalf of someone else",
            "calling for someone else",
            "is this for you or someone else",
        ),
    ):
        return "I’m calling for myself."

    if _contains_any(
        latest,
        (
            "spell your first and last name",
            "spell your full name",
            "spell your name",
            "could you spell",
            "how do you spell",
        ),
    ) and full_name:
        if not spelled_name:
            spelled_name = ", ".join(
                "-".join(character.upper() for character in part)
                for part in full_name.split()
            )
        return f"It’s spelled {spelled_name}."

    if "am i speaking with" in latest and identity_name:
        first_name = identity_name.split()[0].lower()
        if identity_name.lower() in latest or first_name in latest:
            return f"Yes, this is {identity_name}."
        return f"No, this is {identity_name}."

    if _contains_any(
        latest,
        (
            "your first and last name",
            "your full name",
            "what is your name",
            "what's your name",
            "may i have your name",
            "can i have your name",
        ),
    ) and identity_name:
        return f"My name is {identity_name}."

    # A confirmation such as "I have your phone number and date of birth; is
    # that correct?" must be answered with yes/no before the broader phone or
    # date-of-birth detectors run. Otherwise the patient repeats the phone
    # number instead of confirming it.
    explicit_confirmation = _contains_any(
        latest,
        (
            "is that correct",
            "is this correct",
            "is all of that correct",
            "did i get that right",
            "have i got that right",
        ),
    )
    # Telephone ASR sometimes truncates a confirmation at "is that". Treat it
    # as a confirmation only when the agent is clearly summarizing grounded
    # identity fields; this avoids matching unrelated uses of "is that".
    truncated_summary_confirmation = (
        _contains_any(latest, ("i have your", "just to confirm", "i have you as"))
        and _contains_any(latest, ("phone number", "date of birth", "your name"))
        and _contains_any(latest, ("is that", "correct", "right"))
    )
    confirmation_question = explicit_confirmation or truncated_summary_confirmation
    if confirmation_question:
        normalized_latest = _normalized(latest)
        grounded_match = False

        if full_name and _normalized(full_name) in normalized_latest:
            grounded_match = True
        if dob and _normalized(dob) in normalized_latest:
            grounded_match = True
        if medication and medication.lower() in latest:
            grounded_match = True

        configured_number = phone_number or get_settings().vonage_number
        configured_digits = re.sub(r"\D", "", configured_number or "")
        if len(configured_digits) == 11 and configured_digits.startswith("1"):
            configured_digits = configured_digits[1:]
        latest_digits = re.sub(r"\D", "", latest)
        if configured_digits and configured_digits in latest_digits:
            grounded_match = True

        if grounded_match:
            return "Yes, that’s correct."

    # Prefer the phone-number answer when the agent offers a choice between
    # phone lookup and repeating the name/date of birth. The previous ordering
    # matched "date of birth" first and caused the patient to ignore the phone
    # request, which added several unnecessary turns.
    phone_question = _contains_any(
        latest,
        (
            "phone number",
            "number you have on file",
            "number on file",
            "look up your record",
            "lookup your record",
            "best number to reach you",
            "callback number",
        ),
    )
    if phone_question:
        number = phone_number or get_settings().vonage_number
        if number:
            return f"Please use {_format_phone(number)}."
        return "Please confirm me using my name and date of birth."

    dob_question = _contains_any(latest, ("date of birth", "birth date", "birthday"))
    if dob_question and dob:
        if (
            _contains_any(latest, ("is that correct", "is this correct", "confirm"))
            and _normalized(dob) in _normalized(latest)
        ):
            return "Yes, that’s correct."
        return f"My date of birth is {dob}."

    if "insurance" in latest and insurance:
        if "member id" in latest or "policy number" in latest:
            if member_id:
                return f"My member ID is {member_id}."
            return "I don’t have the member ID handy. Can you check using my name and date of birth?"
        return f"I have {insurance}."

    if "pharmacy" in latest and pharmacy:
        return f"Please send it to {pharmacy}."

    if medication:
        medication_question = _contains_any(
            latest,
            (
                "what medication",
                "which medication",
                "name of the medication",
                "request a refill for",
                "you mentioned",
                "is the medication",
                "are you requesting",
                "medicine name",
                "prescription name",
            ),
        )
        medication_context = medication_question or _contains_any(
            latest, ("milligram", "milligrams", " mg")
        )
        medication_missing = medication.lower() not in latest
        if medication_context and medication_missing:
            spelling = f", spelled {medication_spelling}" if medication_spelling else ""
            dose = f", {dosage}" if dosage else ""
            return f"No, the medication is {medication}{spelling}{dose}."
        if medication_question:
            dose = f", {dosage}" if dosage else ""
            return f"It’s {medication}{dose}."

    if reason and _contains_any(
        latest,
        (
            "reason for your visit",
            "reason for the visit",
            "what brings you in",
            "what are you being seen for",
            "routine checkup",
            "routine office visit",
            "follow-up or another reason",
            "something urgent",
        ),
    ):
        return f"It’s {reason}."

    if appointment_type and _contains_any(
        latest,
        ("type of appointment", "kind of appointment", "type of visit", "what type"),
    ):
        article = "an" if appointment_type[:1].lower() in "aeiou" else "a"
        return f"It’s {article} {appointment_type}."

    if original_appointment and _contains_any(
        latest,
        (
            "original appointment",
            "current appointment",
            "when is your appointment",
            "what time was",
        ),
    ):
        return f"The original appointment is {original_appointment}."

    if preferred_time and _contains_any(
        latest,
        ("what day", "what time", "when would", "when works", "availability"),
    ):
        return preferred_time

    return None

def _scenario_steering(
    scenario: dict[str, Any], history: list[dict[str, str]]
) -> str | None:
    scenario_id = str(scenario.get("id", ""))
    latest = _latest_agent_text(history)
    patient_text = " ".join(_patient_turns(history)).lower()
    agent_text = " ".join(_agent_turns(history)).lower()
    details = _details_for(scenario)

    if not latest:
        return None

    if _contains_any(
        latest,
        (
            "one moment",
            "please hold",
            "looking up",
            "checking your information",
            "connecting you",
            "transferring you",
            "please wait",
            "stay on the line",
        ),
    ):
        return "Okay, I’ll wait."

    if scenario_id == "SCN-01":
        if _contains_any(latest, ("how may i help", "what can i help", "how can i help")):
            return "I’d like to schedule a new-patient general check-up next Tuesday morning."
        if _contains_any(latest, ("what day", "what time", "when works", "availability")):
            return "Tuesday morning works best, around 9 or 10 a.m."
        if _time_offer(latest) and _contains_any(latest, ("available", "opening", "offer", "slot")):
            return "That time works for me. Please book it."

    elif scenario_id == "SCN-02":
        original = details.get(
            "original_appointment", "the existing appointment on my account"
        )
        preferred = details.get(
            "preferred_time", "The next available Friday morning works for me."
        )

        if _contains_any(
            latest,
            (
                "how may i help",
                "what can i help",
                "how can i help",
                "what are you calling about",
                "what would you like help with",
                "you are all set how can i help",
                "you're all set how can i help",
            ),
        ):
            return (
                "I need to reschedule my existing appointment. "
                "The next available Friday morning works for me."
            )

        if _contains_any(
            latest,
            (
                "which appointment",
                "current appointment",
                "original appointment",
                "when is your appointment",
                "what time was",
                "appointment you want to move",
            ),
        ):
            return f"The appointment I want to move is {original}."

        if _contains_any(
            latest,
            (
                "what day",
                "what time",
                "when works",
                "what date",
                "preferred day",
                "preferred time",
                "when would you like",
            ),
        ):
            return preferred

        if _time_offer(latest) and "friday" in latest and _contains_any(
            latest,
            ("available", "opening", "offer", "slot", "appointment"),
        ):
            return "That Friday time works for me. Please reschedule it."

        if _contains_any(
            latest,
            (
                "can't access your record",
                "cannot access your record",
                "unable to access your record",
                "can't find your record",
                "cannot find your record",
                "support team follows up",
                "support team will follow up",
                "document this for our team",
            ),
        ):
            return (
                "Okay. Please have the support team contact me about "
                "rescheduling my existing appointment."
            )

    elif scenario_id == "SCN-03":
        if _contains_any(latest, ("reschedule", "another appointment", "different day")):
            return "No, I don’t need to reschedule right now. Please just cancel it."
        if _contains_any(latest, ("which appointment", "when is", "appointment time")):
            return "It’s tomorrow at 11 a.m."

    elif scenario_id == "SCN-04":
        medication = details.get("medication", "lisinopril")
        dosage = details.get("dosage", "10 milligrams")

        # After identity verification the office bot often restarts with a
        # generic help question. Keep this deterministic so Ollama cannot add
        # an early END_CALL marker or omit the refill request.
        if _contains_any(
            latest,
            (
                "how can i help",
                "how may i help",
                "what can i help",
                "what are you calling about",
                "what do you need help with",
                "what would you like help with",
                "you are all set how can i help",
                "you're all set how can i help",
            ),
        ):
            return f"I need a refill for {medication}, {dosage}, please."

        refill_completed = _contains_any(
            latest,
            (
                "refill request has been submitted",
                "refill request is submitted",
                "refill request was submitted",
                "sent the refill request",
                "logged the refill request",
                "refill request has been received",
            ),
        )
        # Recognize both numeric and spoken timelines, for example:
        # "2 business days", "two business days", "24 to 48 hours",
        # "within one day", or "up to three business days".
        timeline_number = (
            r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|twenty[- ]four|forty[- ]eight)"
        )
        timeline_given = bool(
            re.search(
                rf"\b(?:(?:within|in|up to)\s+)?{timeline_number}"
                rf"(?:\s*(?:-|to)\s*{timeline_number})?\s+"
                rf"(?:business\s+)?(?:hour|hours|day|days)\b",
                latest,
                re.I,
            )
        ) or _contains_any(
            latest,
            (
                "later today",
                "by tomorrow",
                "contact you when",
                "contact you once",
                "when it is ready",
            ),
        )

        if refill_completed and timeline_given:
            return f"Okay, thank you. That’s all I needed. Goodbye. {END_MARKER}"
        if refill_completed and "how long" not in patient_text:
            return "How long will the refill request take?"
        if _contains_any(latest, ("anything else", "what else can i help", "is there anything else")):
            if "pharmacy" not in patient_text:
                return f"Please send it to {details.get('pharmacy', 'my usual pharmacy')}."
            if "how long" not in patient_text:
                return "How long will the refill request take?"
        if timeline_given and "refill" in agent_text:
            return f"Okay, thank you. That’s all I needed. Goodbye. {END_MARKER}"

    elif scenario_id == "SCN-05":
        # Keep the patient from answering their own office-hours question.
        if _contains_any(
            latest,
            (
                "how can i help",
                "how may i help",
                "what can i help",
                "what would you like help with",
                "what are you calling about",
            ),
        ):
            return (
                "I’m calling to ask about your office hours and whether "
                "you’re open on weekends."
            )

        weekday_hours_answered = bool(
            re.search(
                r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)",
                agent_text,
                re.I,
            )
        ) and _contains_any(
            agent_text,
            (
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "weekday",
            ),
        )

        saturday_answered = "saturday" in agent_text and _contains_any(
            agent_text,
            ("open", "closed", "not open", "hours", "no appointments"),
        )
        sunday_answered = "sunday" in agent_text and _contains_any(
            agent_text,
            ("open", "closed", "not open", "hours", "no appointments"),
        )
        weekend_answered = (
            ("weekend" in agent_text and _contains_any(agent_text, ("open", "closed", "not open")))
            or saturday_answered
            or sunday_answered
        )
        after_hours_answered = _contains_any(
            agent_text,
            (
                "after-hours",
                "after hours",
                "call 911",
                "emergency room",
                "leave a message",
                "on-call",
                "on call",
            ),
        )

        if weekend_answered and not weekday_hours_answered:
            if not saturday_answered:
                return (
                    "What are your Monday through Friday hours, and are "
                    "you open on Saturday?"
                )
            return "What time do you open and close Monday through Friday?"

        if weekday_hours_answered and not weekend_answered:
            return "Are you open on Saturday or Sunday?"

        if weekday_hours_answered and weekend_answered and not after_hours_answered:
            if "after-hours" not in patient_text and "after hours" not in patient_text:
                return "Is there an after-hours line for urgent issues?"

        if after_hours_answered:
            return "Thank you, that’s all I needed."

    elif scenario_id == "SCN-06":
        if _contains_any(latest, ("what insurance", "which insurance", "insurance plan")):
            return "I have Aetna PPO."
        if "aetna ppo" in agent_text and "aetna hmo" not in patient_text:
            return "Would Aetna HMO be handled differently?"
        if "aetna hmo" in agent_text and "member id" not in patient_text:
            return "Do you need my member ID to verify it?"

    elif scenario_id == "SCN-07":
        reschedule_mode = _contains_any(
            (str(scenario.get("goal", "")) + " " + str(scenario.get("opening", ""))).lower(),
            ("reschedule", "move it", "move my", "existing appointment"),
        )
        if _contains_any(latest, ("already have", "already booked", "existing appointment")) or (
            "reschedule" in latest and _contains_any(latest, ("cancel", "appointment", "team member"))
        ):
            if reschedule_mode:
                return "Yes, I’d like to reschedule my existing appointment to this Sunday at 10 a.m."
            return "I don’t already have an appointment. I’m trying to schedule a new consultation."
        if _contains_any(latest, ("how may i help", "what can i help", "what would you like")):
            if reschedule_mode:
                return "I’d like to move my existing appointment to this Sunday at 10 a.m."
            return "I’d like an appointment this Sunday at 10 a.m. Is that available?"
        sunday_closed = "sunday" in latest and _contains_any(
            latest, ("closed", "not open", "unavailable", "no appointments")
        )
        if sunday_closed:
            return "What’s the earliest Monday morning appointment available?"
        if "monday" in latest and _time_offer(latest) and _contains_any(
            latest, ("available", "opening", "offer", "slot", "appointment")
        ):
            return "The earliest Monday morning time works for me. Please book it."

    elif scenario_id == "SCN-08":
        if _contains_any(latest, ("how severe", "describe", "what does it feel like")):
            return "It’s not severe, but it feels like pressure in my chest."
        if _contains_any(latest, ("age", "history", "heart problems")):
            return "I’m 45 and I don’t have a history of heart problems."
        if _contains_any(latest, ("911", "emergency room", "seek emergency", "urgent care")):
            return f"Okay, I understand. I’ll seek urgent medical care now. Goodbye. {END_MARKER}"
        if _contains_any(latest, ("schedule", "appointment")) and not _contains_any(latest, ("urgent", "emergency")):
            return "Before scheduling, should I go to urgent care instead?"

    elif scenario_id == "SCN-09":
        for follow_up in _unused_follow_ups(scenario, history):
            return follow_up

    elif scenario_id == "SCN-10":
        if _contains_any(
            latest,
            (
                "how can i help",
                "how may i help",
                "what can i help",
                "what are you calling about",
                "what would you like help with",
                "you are all set how can i help",
                "you're all set how can i help",
            ),
        ):
            return "Um, I’d like to make a new appointment for a general check-up."

        if _contains_any(
            latest,
            (
                "new appointment or reschedule",
                "new appointment or an existing",
                "schedule a new appointment",
                "reschedule an existing",
                "another appointment",
            ),
        ):
            return "A separate new appointment, please."

        if _contains_any(
            latest,
            (
                "what kind",
                "reason",
                "type of appointment",
                "type of visit",
                "what are you being seen for",
            ),
        ):
            return "Like, for a general check-up, I guess."

        if _contains_any(
            latest,
            (
                "what day",
                "what time",
                "when works",
                "when would you like",
                "preferred day",
                "preferred time",
                "what is your availability",
            ),
        ):
            vague_timing_already_used = _contains_any(
                patient_text,
                (
                    "whenever you have an opening",
                    "whenever is fine",
                    "any time is fine",
                ),
            )
            if vague_timing_already_used:
                return "Wednesday afternoon would work for me."
            return "I’m not sure—whenever you have an opening is fine."

        if _time_offer(latest) and _contains_any(
            latest,
            ("available", "opening", "offer", "slot", "appointment"),
        ):
            return "Yes, that works for me. Please book it."

    elif scenario_id == "SCN-11":
        if _contains_any(latest, ("not dr. patel", "isn't dr. patel", "wrong number", "different clinic")):
            if "doctors available" not in patient_text:
                return "I’m sorry, I may have the wrong office. Do you have any doctors accepting new patients?"
        if _contains_any(latest, ("yes", "accepting new patients", "can help you schedule")) and "doctors available" in patient_text:
            return "In that case, I’d like to ask about making a new-patient appointment."

    elif scenario_id == "SCN-12":
        appointment_done = bool(re.search(r"appointment .*?(?:confirmed|booked|scheduled)", agent_text))
        refill_done = bool(re.search(r"refill .*?(?:submitted|sent|logged|received)", agent_text))
        if _contains_any(latest, ("what day", "what time", "when works")):
            return "For the appointment, any day next week works."
        if _contains_any(latest, ("what medication", "which medication", "dose", "dosage")):
            return "For the refill, it’s metformin, 500 milligrams twice daily."
        if appointment_done and not refill_done:
            return "Thank you. I also still need the metformin refill handled."
        if refill_done and not appointment_done:
            return "Thank you. I also still need to schedule the appointment."
        if appointment_done and refill_done:
            return f"That covers both requests. Thank you. Goodbye. {END_MARKER}"

    return None


def direct_patient_answer(
    scenario: dict[str, Any], conversation_history: list[dict[str, str]]
) -> str | None:
    """Return a grounded deterministic answer when the agent asks directly."""
    answer = _generic_intake_answer(scenario, conversation_history)
    if answer:
        return answer
    return _scenario_steering(scenario, conversation_history)


def office_agent_has_closed(
    scenario: dict[str, Any], conversation_history: list[dict[str, str]]
) -> bool:
    agent_turns = _agent_turns(conversation_history)
    if not agent_turns:
        return False
    latest_agent = agent_turns[-1].lower()

    if patient_has_wrapped_up(conversation_history) and any(
        re.search(pattern, latest_agent, re.I) for pattern in _AGENT_FAREWELL_PATTERNS
    ):
        return True

    patterns = _AUTO_CLOSE_COMPLETION_PATTERNS.get(str(scenario.get("id", "")), ())
    return any(re.search(pattern, latest_agent, re.I) for pattern in patterns)



def _agent_explicitly_ended(history: list[dict[str, str]]) -> bool:
    """Return True when the latest office-agent turn is a clear farewell."""
    latest = _latest_agent_text(history)
    if not latest:
        return False
    return any(re.search(pattern, latest, re.I) for pattern in _AGENT_FAREWELL_PATTERNS)


def remove_premature_end_marker(
    scenario: dict[str, Any],
    conversation_history: list[dict[str, str]],
    response: str,
) -> str:
    """Strip an LLM-generated end marker unless the office ended the call.

    Scenario-specific deterministic responses may still intentionally return
    ``[END_CALL]`` after a refill timeline, emergency escalation, or completed
    multi-request workflow. This guard applies only to free-form Ollama output.
    """
    if END_MARKER not in response:
        return response

    if office_agent_has_closed(scenario, conversation_history) or _agent_explicitly_ended(
        conversation_history
    ):
        return response

    LOGGER.warning(
        "Removed premature END_CALL marker from patient response: %s", response
    )
    cleaned = response.replace(END_MARKER, "").strip()
    return cleaned or "Okay, thank you."

def ollama_chat(
    messages: list[dict[str, str]],
    *,
    settings: Settings | None = None,
    temperature: float = 0.65,
    max_tokens: int = 120,
    json_mode: bool = False,
) -> str:
    cfg = settings or get_settings()
    payload: dict[str, Any] = {
        "model": cfg.ollama_model,
        "messages": messages,
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if json_mode:
        payload["format"] = "json"

    response = requests.post(
        f"{cfg.ollama_base_url}/api/chat",
        json=payload,
        timeout=cfg.ollama_timeout_seconds,
    )
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "").strip()
    if not content:
        raise RuntimeError("Ollama returned an empty response.")
    return content


def check_ollama(settings: Settings | None = None) -> tuple[bool, str]:
    cfg = settings or get_settings()
    try:
        response = requests.get(
            f"{cfg.ollama_base_url}/api/tags",
            timeout=min(cfg.ollama_timeout_seconds, 5),
        )
        response.raise_for_status()
        models = {item.get("name", "") for item in response.json().get("models", [])}
        if cfg.ollama_model in models or any(
            name.split(":")[0] == cfg.ollama_model.split(":")[0] for name in models
        ):
            return True, f"Ollama is ready with model {cfg.ollama_model}."
        return False, (
            f"Ollama is running, but {cfg.ollama_model} is not installed. "
            f"Run: ollama pull {cfg.ollama_model}"
        )
    except requests.RequestException as exc:
        return False, f"Ollama is unavailable at {cfg.ollama_base_url}: {exc}"


def get_patient_response(
    scenario: dict[str, Any],
    conversation_history: list[dict[str, str]],
    *,
    settings: Settings | None = None,
) -> str:
    cfg = settings or get_settings()

    if office_agent_has_closed(scenario, conversation_history):
        if patient_has_wrapped_up(conversation_history):
            return f"Goodbye. {END_MARKER}"
        return f"No, that’s everything. Thank you. Goodbye. {END_MARKER}"

    direct_answer = direct_patient_answer(scenario, conversation_history)
    if direct_answer:
        return direct_answer

    messages = _patient_messages(scenario, conversation_history)
    try:
        first_draft = _strip_speaker_prefix(
            ollama_chat(messages, settings=cfg, temperature=0.35)
        )
        first_draft = remove_premature_end_marker(
            scenario, conversation_history, first_draft
        )
        role_drift = looks_like_office_agent(first_draft)
        repetitive = is_repetitive_patient_response(first_draft, conversation_history)
        if not role_drift and not repetitive:
            return first_draft

        reasons: list[str] = []
        if role_drift:
            reasons.append("acted as the OFFICE AGENT")
        if repetitive:
            reasons.append("repeated an earlier patient line")
        LOGGER.warning("Rejected patient draft (%s): %s", ", ".join(reasons), first_draft)

        remaining = _unused_follow_ups(scenario, conversation_history)
        retry_messages = [
            messages[0],
            {
                "role": "user",
                "content": (
                    f"{messages[1]['content']}\n\n"
                    f"Rejected draft: {first_draft}\n"
                    f"Reason: {', '.join(reasons)}.\n"
                    "Write a different short PATIENT-only response. Answer the latest "
                    "agent question directly. Do not repeat an earlier patient line.\n"
                    "Unused follow-ups:\n- "
                    + ("\n- ".join(remaining) if remaining else "None")
                ),
            },
        ]
        retry = _strip_speaker_prefix(
            ollama_chat(retry_messages, settings=cfg, temperature=0.10)
        )
        retry = remove_premature_end_marker(
            scenario, conversation_history, retry
        )
        if not looks_like_office_agent(retry) and not is_repetitive_patient_response(
            retry, conversation_history
        ):
            return retry

        LOGGER.warning("Retry invalid; using safe fallback: %s", retry)
        return fallback_patient_response(scenario, conversation_history)
    except Exception as exc:
        LOGGER.exception("Patient LLM failed: %s", exc)
        if cfg.require_ollama:
            raise RuntimeError(
                "The local patient model is unavailable. Start Ollama and pull "
                f"the configured model ({cfg.ollama_model})."
            ) from exc
        return fallback_patient_response(scenario, conversation_history)


def fallback_patient_response(
    scenario: dict[str, Any], conversation_history: list[dict[str, str]]
) -> str:
    if office_agent_has_closed(scenario, conversation_history):
        if patient_has_wrapped_up(conversation_history):
            return f"Goodbye. {END_MARKER}"
        return f"No, that’s everything. Thank you. Goodbye. {END_MARKER}"

    direct = direct_patient_answer(scenario, conversation_history)
    if direct:
        return direct

    latest_agent = _latest_agent_text(conversation_history)
    if _contains_any(latest_agent, ("goodbye", "have a good", "have a great")):
        return f"Thank you. Goodbye. {END_MARKER}"

    remaining = _unused_follow_ups(scenario, conversation_history)
    if remaining:
        return remaining[0]

    if "appointment" in str(scenario.get("goal", "")).lower():
        return "Could you please confirm the appointment date and time?"
    return f"Thank you, that’s all I needed. {END_MARKER}"


def should_end_call(patient_response: str) -> bool:
    return END_MARKER in patient_response


def clean_response(patient_response: str) -> str:
    cleaned = _strip_speaker_prefix(patient_response.replace(END_MARKER, "").strip())
    return cleaned or "Thank you. Goodbye."
