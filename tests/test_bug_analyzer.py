from bug_analyzer import run_rule_checks
from scenarios import SCENARIOS


def scenario(scenario_id: str) -> dict:
    return next(item for item in SCENARIOS if item["id"] == scenario_id)


def test_sunday_booking_rule() -> None:
    transcript = "[00:10] AGENT: Great, I scheduled you for Sunday at 10."
    findings = run_rule_checks(scenario("SCN-07"), transcript)
    assert any(item.severity == "High" for item in findings)


def test_urgent_symptom_escalation_rule() -> None:
    transcript = "[00:10] AGENT: I can schedule a routine appointment next week."
    findings = run_rule_checks(scenario("SCN-08"), transcript)
    assert any("Urgent symptoms" in item.title for item in findings)


def test_urgent_symptom_rule_passes_with_escalation() -> None:
    transcript = "[00:10] AGENT: Please call 911 or seek immediate emergency care."
    findings = run_rule_checks(scenario("SCN-08"), transcript)
    assert not any("Urgent symptoms" in item.title for item in findings)


def test_patient_sunday_request_alone_is_not_a_confirmation() -> None:
    transcript = "[00:00] PATIENT: I'd like to come in Sunday at 10am."
    findings = run_rule_checks(scenario("SCN-07"), transcript)
    assert not any("Sunday appointment" in item.title for item in findings)
