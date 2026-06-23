from __future__ import annotations

from pathlib import Path

import app as app_module
from app import create_app
from state_store import CallStateStore


class FakeVoiceClient:
    def create_call(self, answer_url: str, event_url: str) -> dict:
        assert answer_url.startswith("https://")
        assert event_url.startswith("https://")
        return {"uuid": "fake-call-uuid"}

    def download_recording(self, recording_url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"fake-mp3")
        return destination


def test_health_and_scenarios(settings) -> None:
    flask_app = create_app(settings, CallStateStore(), FakeVoiceClient())
    client = flask_app.test_client()
    assert client.get("/health").status_code == 200
    response = client.get("/scenarios")
    assert response.status_code == 200
    assert len(response.get_json()) >= 10


def test_make_call_and_answer_ncco(settings) -> None:
    flask_app = create_app(settings, CallStateStore(), FakeVoiceClient())
    client = flask_app.test_client()
    response = client.post("/make-call", json={"scenario_id": "SCN-01"})
    assert response.status_code == 200
    call_id = response.get_json()["call_id"]

    answer = client.get(f"/voice-answer/{call_id}")
    assert answer.status_code == 200
    ncco = answer.get_json()
    assert ncco[0]["action"] == "record"
    assert ncco[0]["split"] == "conversation"
    assert ncco[1]["action"] == "talk"
    assert ncco[2]["action"] == "input"


def test_agent_turn_returns_patient_reply(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "get_patient_response",
        lambda scenario, history, settings=None: "Tuesday morning works for me.",
    )
    store = CallStateStore()
    flask_app = create_app(settings, store, FakeVoiceClient())
    client = flask_app.test_client()
    response = client.post("/make-call", json={"scenario_id": "SCN-01"})
    call_id = response.get_json()["call_id"]

    turn = client.post(
        f"/agent-spoke/{call_id}",
        json={"speech": {"results": [{"text": "What day works?", "confidence": 0.95}]}},
    )
    assert turn.status_code == 200
    ncco = turn.get_json()
    assert ncco[0]["action"] == "talk"
    assert "Tuesday morning" in ncco[0]["text"]
    assert ncco[1]["action"] == "input"


def test_unknown_scenario_is_rejected(settings) -> None:
    flask_app = create_app(settings, CallStateStore(), FakeVoiceClient())
    client = flask_app.test_client()
    response = client.post("/make-call", json={"scenario_id": "SCN-99"})
    assert response.status_code == 400


def test_barge_in_scenario_enables_interruption(settings) -> None:
    flask_app = create_app(settings, CallStateStore(), FakeVoiceClient())
    client = flask_app.test_client()
    response = client.post("/make-call", json={"scenario_id": "SCN-09"})
    call_id = response.get_json()["call_id"]
    ncco = client.get(f"/voice-answer/{call_id}").get_json()
    assert ncco[1]["bargeIn"] is True
    assert ncco[2]["action"] == "input"


def test_late_agent_webhook_does_not_generate_patient_turn(settings, monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Patient model should not run after call completion")

    monkeypatch.setattr(app_module, "get_patient_response", fail_if_called)
    store = CallStateStore()
    flask_app = create_app(settings, store, FakeVoiceClient())
    client = flask_app.test_client()
    response = client.post("/make-call", json={"scenario_id": "SCN-05"})
    call_id = response.get_json()["call_id"]
    state = store.get(call_id)
    assert state is not None
    state["status"] = "completed"

    turn = client.post(
        f"/agent-spoke/{call_id}",
        json={"speech": {"results": [{"text": "You're welcome. Have a great day.", "confidence": 0.99}]}},
    )
    assert turn.status_code == 200
    assert turn.get_json() == []
    assert state["turns"][-1]["speaker"] == "AGENT"
    assert "great day" in state["turns"][-1]["text"]
