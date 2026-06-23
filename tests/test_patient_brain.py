from patient_brain import (
    clean_response,
    direct_patient_answer,
    fallback_patient_response,
    is_repetitive_patient_response,
    looks_like_office_agent,
    office_agent_has_closed,
    patient_has_wrapped_up,
    should_end_call,
)
from scenarios import SCENARIOS


def test_end_call_marker() -> None:
    text = "Thanks, goodbye. [END_CALL]"
    assert should_end_call(text)
    assert clean_response(text) == "Thanks, goodbye."


def test_clean_response_removes_patient_prefix() -> None:
    assert clean_response("PATIENT: Tuesday morning works for me.") == (
        "Tuesday morning works for me."
    )


def test_fallback_uses_follow_up() -> None:
    scenario = SCENARIOS[0]
    history = [{"role": "assistant", "content": scenario["opening"]}]
    response = fallback_patient_response(scenario, history)
    assert response == scenario["follow_ups"][0]


def test_detects_office_agent_role_drift() -> None:
    bad_lines = [
        "Let me check availability for Tuesday at 9:30.",
        "Perfect, that time slot is open.",
        "I have scheduled you for Tuesday.",
        "You'll receive a confirmation text shortly.",
        "We accept Blue Cross insurance.",
        "Do you have insurance? I have Blue Cross.",
        "OFFICE AGENT: May I have your date of birth?",
    ]
    assert all(looks_like_office_agent(line) for line in bad_lines)


def test_allows_normal_patient_language() -> None:
    good_lines = [
        "Tuesday morning works best for me.",
        "I have Blue Cross insurance.",
        "Could you confirm the date and time?",
        "Is the office open on Saturday?",
    ]
    assert not any(looks_like_office_agent(line) for line in good_lines)


def test_detects_office_agent_closing_cues() -> None:
    history = [
        {"role": "assistant", "content": "Tuesday at 9:30 works for me."},
        {
            "role": "user",
            "content": (
                "Your appointment is confirmed for Tuesday at 9:30. "
                "Is there anything else I can help with?"
            ),
        },
    ]
    assert office_agent_has_closed(SCENARIOS[0], history)


def test_does_not_close_on_booking_question() -> None:
    history = [
        {"role": "user", "content": "I have Tuesday at 9:30 available. Would you like me to book it?"}
    ]
    assert not office_agent_has_closed(SCENARIOS[0], history)


def test_greeting_thank_you_for_calling_is_not_a_close() -> None:
    history = [
        {"role": "assistant", "content": "Hi, I would like an appointment."},
        {
            "role": "user",
            "content": (
                "Thank you for calling Pivot Point Orthopedics. Would you like "
                "to create a demo patient profile? I need your first and last name."
            ),
        },
    ]
    assert not office_agent_has_closed(SCENARIOS[0], history)


def test_multi_request_does_not_auto_close_after_only_appointment() -> None:
    scenario = next(item for item in SCENARIOS if item["id"] == "SCN-12")
    history = [
        {"role": "user", "content": "What day works for the appointment?"},
        {"role": "assistant", "content": "Next Tuesday works."},
        {
            "role": "user",
            "content": "Your appointment is confirmed. Is there anything else?",
        },
    ]
    assert not office_agent_has_closed(scenario, history)


def test_detects_repeated_patient_question() -> None:
    history = [
        {"role": "assistant", "content": "Quick question — are you open weekends?"},
        {"role": "user", "content": "We are closed on Saturdays."},
        {"role": "assistant", "content": "What about Saturday?"},
        {"role": "user", "content": "The clinic is closed on Saturdays."},
    ]
    assert is_repetitive_patient_response("What about Saturday?", history)


def test_fallback_uses_next_unused_follow_up() -> None:
    scenario = next(item for item in SCENARIOS if item["id"] == "SCN-05")
    history = [
        {"role": "assistant", "content": scenario["opening"]},
        {"role": "user", "content": "We are closed on Saturdays."},
        {"role": "assistant", "content": "What about Saturday?"},
        {"role": "user", "content": "The clinic is closed on Saturdays."},
    ]
    assert fallback_patient_response(scenario, history) == (
        "What time do you open and close Monday through Friday?"
    )


def test_short_polite_phrase_is_not_overblocked() -> None:
    history = [{"role": "assistant", "content": "Thank you."}]
    assert not is_repetitive_patient_response("Thank you.", history)
