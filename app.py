"""Flask application for the PGAI automated patient voice bot."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from flask import Flask, Response, jsonify, request, send_from_directory

from config import Settings, get_settings
from output_manager import write_call_outputs, write_metadata
from patient_brain import (
    check_ollama,
    clean_response,
    get_patient_response,
    should_end_call,
)
from scenarios import SCENARIOS
from state_store import CallStateStore
from tts import get_voice_profile_for_persona, text_to_speech
from vonage_client import VonageVoiceClient

LOGGER = logging.getLogger(__name__)
TERMINAL_STATUSES = {"completed", "failed", "unanswered", "rejected", "busy", "timeout"}
FINALIZATION_GRACE_SECONDS = 5.0


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_scenario(scenario_id: str | None, scenario_index: int | None) -> dict[str, Any]:
    if scenario_id:
        for scenario in SCENARIOS:
            if scenario["id"].upper() == scenario_id.upper():
                return scenario
        raise KeyError(f"Unknown scenario ID: {scenario_id}")
    index = 0 if scenario_index is None else int(scenario_index)
    if index < 0 or index >= len(SCENARIOS):
        raise IndexError(f"Scenario index must be between 0 and {len(SCENARIOS) - 1}.")
    return SCENARIOS[index]


def parse_speech_payload(data: dict[str, Any]) -> tuple[str, float | None]:
    speech = data.get("speech") or {}
    results = speech.get("results") or []
    if not results:
        return "", None
    first = results[0] or {}
    text = str(first.get("text", "")).strip()
    confidence = first.get("confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_value = None
    return text, confidence_value


def create_app(
    settings: Settings | None = None,
    store: CallStateStore | None = None,
    voice_client: VonageVoiceClient | None = None,
) -> Flask:
    cfg = settings or get_settings()
    cfg.ensure_directories()
    call_store = store or CallStateStore()
    client = voice_client or VonageVoiceClient(cfg)

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.extensions["settings"] = cfg
    app.extensions["call_store"] = call_store
    app.extensions["voice_client"] = client

    def public_url(path: str) -> str:
        return f"{cfg.base_url}/{path.lstrip('/')}"

    def build_listen_action(call_id: str) -> dict[str, Any]:
        return {
            "action": "input",
            "type": ["speech"],
            "speech": {
                "endOnSilence": cfg.end_on_silence_seconds,
                # The target agent can take more than the Vonage default wait
                # time to begin speaking after a patient turn. A longer start
                # timeout prevents false "No speech recognized" callbacks.
                "startTimeout": int(
                    os.getenv("SPEECH_START_TIMEOUT_SECONDS", "20")
                ),
                "maxDuration": int(
                    os.getenv("SPEECH_MAX_DURATION_SECONDS", "45")
                ),
                "language": "en-US",
                "sensitivity": 50,
            },
            "eventUrl": [public_url(f"agent-spoke/{call_id}")],
            "eventMethod": "POST",
        }

    def build_speech_action(
        text: str, state: dict[str, Any], *, allow_barge_in: bool = False
    ) -> dict[str, Any]:
        if cfg.tts_provider == "gtts":
            try:
                audio_path = text_to_speech(
                    text,
                    state.get("voice_profile", "us"),
                    cfg.calls_dir,
                )
                state.setdefault("temporary_audio", []).append(str(audio_path))
                return {
                    "action": "stream",
                    "streamUrl": [public_url(f"audio/{audio_path.name}")],
                    "bargeIn": allow_barge_in,
                }
            except Exception as exc:
                LOGGER.exception("gTTS failed; using Vonage TTS: %s", exc)
                state.setdefault("errors", []).append(f"gTTS fallback: {exc}")
        return {
            "action": "talk",
            "text": text,
            "language": "en-US",
            "bargeIn": allow_barge_in,
        }

    def build_record_action(call_id: str) -> dict[str, Any]:
        action: dict[str, Any] = {
            "action": "record",
            "eventUrl": [public_url(f"recording-ready/{call_id}")],
            "eventMethod": "POST",
            "format": "mp3",
            "beepStart": False,
        }
        if cfg.split_recording:
            action.update({"split": "conversation", "channels": 2})
        return action

    def finalize_outputs(call_id: str) -> None:
        if not call_store.mark_finalized(call_id):
            return
        state = call_store.get(call_id)
        if state is None:
            return
        try:
            output_paths = write_call_outputs(state, cfg)
            state["output_paths"] = output_paths
            LOGGER.info("Saved outputs for %s: %s", call_id, output_paths)
        except Exception as exc:
            LOGGER.exception("Failed to finalize outputs for %s: %s", call_id, exc)
            state.setdefault("errors", []).append(f"Output finalization failed: {exc}")

    def finalize_in_background(call_id: str) -> None:
        def worker() -> None:
            # Vonage/Cloudflare can deliver the final speech webhook a few
            # seconds after the terminal call event. Give it a short window so
            # the transcript captures that final agent utterance.
            time.sleep(FINALIZATION_GRACE_SECONDS)
            finalize_outputs(call_id)

        threading.Thread(
            target=worker,
            daemon=True,
            name=f"finalize-{call_id}",
        ).start()

    def download_recording_in_background(call_id: str, payload: dict[str, Any]) -> None:
        def worker() -> None:
            state = call_store.get(call_id)
            if state is None:
                return
            recording_url = str(payload.get("recording_url", "")).strip()
            if not recording_url:
                state.setdefault("errors", []).append(
                    "Recording webhook did not contain recording_url."
                )
                return
            destination = cfg.calls_dir / f"recording-{call_id}.mp3"
            last_error: Exception | None = None
            for attempt in range(1, 4):
                try:
                    client.download_recording(recording_url, destination)
                    state["recording_path"] = str(destination)
                    state["recording_uuid"] = payload.get("recording_uuid")
                    state["recording_size_bytes"] = destination.stat().st_size
                    write_metadata(state, cfg)
                    LOGGER.info("Saved recording for %s to %s", call_id, destination)
                    return
                except Exception as exc:
                    last_error = exc
                    LOGGER.warning(
                        "Recording download attempt %s failed for %s: %s",
                        attempt,
                        call_id,
                        exc,
                    )
                    time.sleep(attempt * 2)
            state.setdefault("errors", []).append(
                f"Recording download failed after retries: {last_error}"
            )

        threading.Thread(
            target=worker,
            daemon=True,
            name=f"recording-{call_id}",
        ).start()

    @app.get("/health")
    def health() -> Response:
        payload: dict[str, Any] = {
            "status": "ok",
            "calls_in_memory": call_store.count_unique_calls(),
            "target_locked": True,
            "recording_enabled": cfg.recording_enabled,
            "tts_provider": cfg.tts_provider,
            "ollama_model": cfg.ollama_model,
        }
        if request.args.get("deep") == "1":
            ollama_ok, ollama_message = check_ollama(cfg)
            payload["ollama"] = {"ok": ollama_ok, "message": ollama_message}
            payload["real_call_errors"] = cfg.validate_for_real_call()
        return jsonify(payload)

    @app.get("/scenarios")
    def scenarios() -> Response:
        return jsonify(
            [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "persona": item["persona"],
                    "goal": item["goal"],
                }
                for item in SCENARIOS
            ]
        )

    @app.get("/audio/<path:filename>")
    def serve_audio(filename: str) -> Response:
        if Path(filename).name != filename:
            return jsonify({"error": "Invalid filename"}), 400
        return send_from_directory(
            cfg.calls_dir.resolve(),
            filename,
            mimetype="audio/mpeg",
            max_age=0,
        )

    @app.post("/make-call")
    def make_call() -> Response:
        errors = cfg.validate_for_real_call()
        if errors:
            return jsonify({"status": "configuration_error", "errors": errors}), 400

        if cfg.require_ollama:
            ollama_ok, ollama_message = check_ollama(cfg)
            if not ollama_ok:
                return jsonify(
                    {"status": "ollama_error", "message": ollama_message}
                ), 503

        data = request.get_json(silent=True) or {}
        try:
            scenario = get_scenario(data.get("scenario_id"), data.get("scenario_index"))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            return jsonify({"status": "invalid_scenario", "message": str(exc)}), 400

        call_id = f"{scenario['id']}-{uuid.uuid4().hex[:8]}"
        state: dict[str, Any] = {
            "call_id": call_id,
            "scenario": scenario,
            "voice_profile": get_voice_profile_for_persona(scenario["persona"]),
            "turns": [
                {
                    "speaker": "PATIENT",
                    "text": scenario["opening"],
                    "timestamp": 0.0,
                }
            ],
            "conversation_history": [
                {"role": "assistant", "content": scenario["opening"]}
            ],
            "started_monotonic": time.monotonic(),
            "started_at": utc_now_iso(),
            "status": "initiating",
            "silence_count": 0,
            "outputs_finalized": False,
            "errors": [],
        }
        call_store.create(call_id, state)

        try:
            result = client.create_call(
                answer_url=public_url(f"voice-answer/{call_id}"),
                event_url=public_url(f"call-event/{call_id}"),
            )
            call_uuid = result.get("uuid")
            if not call_uuid:
                raise RuntimeError(f"Vonage response did not include a call UUID: {result}")
            state["call_uuid"] = call_uuid
            state["status"] = "calling"
            call_store.alias(str(call_uuid), call_id)
            return jsonify(
                {
                    "status": "calling",
                    "call_id": call_id,
                    "call_uuid": call_uuid,
                    "scenario": scenario["name"],
                }
            )
        except Exception as exc:
            state["status"] = "failed"
            state["ended_at"] = utc_now_iso()
            state["errors"].append(f"Call creation failed: {exc}")
            finalize_in_background(call_id)
            LOGGER.exception("Unable to create call %s", call_id)
            return jsonify({"status": "error", "message": str(exc)}), 502

    @app.get("/voice-answer/<call_id>")
    def voice_answer(call_id: str) -> Response:
        state = call_store.get(call_id)
        if state is None:
            return jsonify([{"action": "talk", "text": "Goodbye."}]), 404
        state["status"] = "answered"
        ncco: list[dict[str, Any]] = []
        if cfg.recording_enabled:
            ncco.append(build_record_action(call_id))
        ncco.append(
            build_speech_action(
                state["scenario"]["opening"],
                state,
                allow_barge_in=bool(state["scenario"].get("allow_barge_in")),
            )
        )
        ncco.append(build_listen_action(call_id))
        return jsonify(ncco)

    @app.post("/agent-spoke/<call_id>")
    def agent_spoke(call_id: str) -> Response:
        state = call_store.get(call_id)
        if state is None:
            return jsonify([{"action": "talk", "text": "Goodbye."}]), 404

        # A retried webhook can arrive after the output files have already
        # been finalized. Ignore it rather than reopening a finished call.
        if state.get("outputs_finalized"):
            LOGGER.info("[%s] Ignored speech webhook after finalization", call_id)
            return jsonify([])

        data = request.get_json(silent=True) or {}
        agent_text, confidence = parse_speech_payload(data)
        elapsed = time.monotonic() - state["started_monotonic"]
        terminal_callback = (
            str(state.get("status", "")).lower() in TERMINAL_STATUSES
            or state.get("status") == "ending"
        )

        if agent_text:
            state["silence_count"] = 0
            call_store.append_turn(
                call_id,
                {
                    "speaker": "AGENT",
                    "text": agent_text,
                    "timestamp": elapsed,
                    "confidence": confidence,
                },
            )
            call_store.append_history(
                call_id, {"role": "user", "content": agent_text}
            )
            LOGGER.info("[%s] AGENT: %s", call_id, agent_text)
        else:
            state["silence_count"] = int(state.get("silence_count", 0)) + 1
            call_store.append_turn(
                call_id,
                {
                    "speaker": "AGENT",
                    "text": "[No speech recognized]",
                    "timestamp": elapsed,
                    "confidence": confidence,
                },
            )

        if terminal_callback:
            LOGGER.info(
                "[%s] Captured late speech webhook without generating another patient turn",
                call_id,
            )
            return jsonify([])

        recognized_agent_turns = sum(
            1
            for turn in state.get("turns", [])
            if turn.get("speaker") == "AGENT"
            and turn.get("text") != "[No speech recognized]"
        )

        # Recover from silence before applying the safety limit. Previously a
        # single silent callback at 20 total transcript rows ended the call,
        # even though the refill had not been submitted. MAX_TURNS now limits
        # recognized office-agent turns rather than counting both speakers.
        if not agent_text:
            if state["silence_count"] > cfg.max_silence_retries:
                patient_reply = "I still can't hear anything, so I'll call back later. Goodbye. [END_CALL]"
            else:
                patient_reply = "Hello? I didn't hear a response. Could you say that again?"
        elif recognized_agent_turns >= cfg.max_turns:
            patient_reply = "Thank you for your help. I need to go now. Goodbye. [END_CALL]"
        else:
            try:
                patient_reply = get_patient_response(
                    state["scenario"],
                    list(state["conversation_history"]),
                    settings=cfg,
                )
            except Exception as exc:
                LOGGER.exception("Patient response failed for %s: %s", call_id, exc)
                state["errors"].append(f"Patient model failed: {exc}")
                patient_reply = "I'm sorry, I need to call back another time. Goodbye. [END_CALL]"

        end_call = should_end_call(patient_reply)
        clean_reply = clean_response(patient_reply)
        patient_elapsed = time.monotonic() - state["started_monotonic"]
        call_store.append_turn(
            call_id,
            {
                "speaker": "PATIENT",
                "text": clean_reply,
                "timestamp": patient_elapsed,
            },
        )
        call_store.append_history(
            call_id, {"role": "assistant", "content": clean_reply}
        )
        LOGGER.info(
            "[%s] PATIENT: %s | end_call=%s",
            call_id,
            clean_reply,
            end_call,
        )

        actions = [
            build_speech_action(
                clean_reply,
                state,
                allow_barge_in=(
                    bool(state["scenario"].get("allow_barge_in")) and not end_call
                ),
            )
        ]
        if end_call:
            state["status"] = "ending"
        else:
            actions.append(build_listen_action(call_id))
        return jsonify(actions)

    @app.post("/call-event/<call_id>")
    def call_event(call_id: str) -> Response:
        data = request.get_json(silent=True) or {}
        status = str(data.get("status", "unknown")).lower()
        state = call_store.get(call_id)
        if state is not None:
            state["status"] = status
            state.setdefault("events", []).append(data)
            if status in TERMINAL_STATUSES:
                state["ended_at"] = utc_now_iso()
                finalize_in_background(call_id)
        LOGGER.info("[%s] Vonage event: %s", call_id, status)
        return jsonify({"status": "ok"})

    @app.post("/recording-ready/<call_id>")
    def recording_ready(call_id: str) -> Response:
        state = call_store.get(call_id)
        if state is None:
            return jsonify({"status": "unknown_call"}), 404
        payload = request.get_json(silent=True) or {}
        state["recording_webhook"] = payload
        download_recording_in_background(call_id, payload)
        return jsonify({"status": "accepted"}), 202

    @app.get("/call-status/<call_id>")
    def call_status(call_id: str) -> Response:
        state = call_store.snapshot(call_id)
        if state is None:
            return jsonify({"status": "not_found"}), 404
        public_state = {
            "call_id": state.get("call_id"),
            "call_uuid": state.get("call_uuid"),
            "scenario": state.get("scenario", {}).get("name"),
            "status": state.get("status"),
            "turn_count": len(state.get("turns", [])),
            "recording_path": state.get("recording_path"),
            "output_paths": state.get("output_paths"),
            "errors": state.get("errors", []),
        }
        return jsonify(public_state)

    @app.post("/run-all")
    def run_all() -> Response:
        data = request.get_json(silent=True) or {}
        delay_seconds = max(30, int(data.get("delay_seconds", 120)))

        def worker() -> None:
            for index, scenario in enumerate(SCENARIOS):
                try:
                    response = requests.post(
                        f"http://127.0.0.1:{cfg.port}/make-call",
                        json={"scenario_id": scenario["id"]},
                        timeout=30,
                    )
                    LOGGER.info(
                        "Run-all %s/%s %s: %s",
                        index + 1,
                        len(SCENARIOS),
                        response.status_code,
                        response.text,
                    )
                except Exception as exc:
                    LOGGER.exception("Run-all failed on %s: %s", scenario["id"], exc)
                if index < len(SCENARIOS) - 1:
                    time.sleep(delay_seconds)

        threading.Thread(target=worker, daemon=True, name="run-all").start()
        return jsonify(
            {
                "status": "queued",
                "total": len(SCENARIOS),
                "delay_seconds": delay_seconds,
            }
        )

    return app


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
app = create_app()


if __name__ == "__main__":
    active_settings = app.extensions["settings"]
    app.run(
        host="0.0.0.0",
        port=active_settings.port,
        debug=False,
        use_reloader=False,
    )
