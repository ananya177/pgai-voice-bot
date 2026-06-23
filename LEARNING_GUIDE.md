# Learning Guide

Build and understand the system in layers. Do not begin with ten real calls.

## Stage 1: Python foundations

Learn dictionaries, lists, functions, modules, exceptions, file I/O, type hints, environment variables, and basic threads. Read `scenarios.py`, then print every scenario's ID, goal, and opening line.

Milestone: `python run_calls.py --list` works and you can explain the shape of one scenario dictionary.

## Stage 2: HTTP and Flask

Learn GET, POST, JSON, status codes, localhost, public URLs, and webhooks. Read the `/health`, `/scenarios`, and `/make-call` routes in `app.py`.

Milestone: start Flask and retrieve `/health` with a browser or `curl`.

## Stage 3: Local conversational AI

Install Ollama, pull `gemma3:4b`, and read `patient_brain.py`. Study the system prompt, message roles, temperature, token limit, timeout, and end marker.

Milestone: `python simulate.py --scenario SCN-01` completes a coherent text conversation.

Experiments:

1. Remove the short-response rule and observe how telephone replies become too long.
2. Increase temperature and observe inconsistency.
3. Add an unexpected agent question and verify the patient remains in character.
4. Test the same scenario five times and compare variability.

## Stage 4: Text-to-speech

Read `tts.py`. Learn the difference between generated MP3 audio and provider-side TTS. Observe how medication units, acronyms, and emergency numbers are normalized before speech generation.

Milestone: call `text_to_speech()` from a Python shell and play the resulting MP3.

## Stage 5: Vonage call control

Learn E.164 phone numbers, JWT authentication, answer URLs, event URLs, NCCO actions, `stream`, `talk`, `input`, and `record`. Read `vonage_client.py` and the `voice_answer` route.

Milestone: draw the request sequence from `/make-call` through `/agent-spoke` without looking at the diagram.

## Stage 6: State and turn-taking

Read `state_store.py` and the `agent_spoke` route. Understand why every call needs separate history, timestamps, silence count, status, and a maximum-turn limit.

Milestone: explain what happens when no speech is recognized twice and what happens when the turn limit is reached.

## Stage 7: Recording and evidence

Read the `recording_ready` route and `download_recording()` method. Learn why the recording callback sends a URL instead of the audio itself, why a fresh JWT is required, and why the URL host is validated.

Milestone: one real call produces an MP3 plus a transcript.

## Stage 8: QA engineering

Read `bug_analyzer.py`. Compare deterministic checks with LLM review.

For each bug, capture:

- scenario and call ID;
- exact evidence or timestamp;
- actual behavior;
- why it matters;
- expected behavior;
- severity.

Milestone: manually verify every automatically generated finding against the audio.

## Stage 9: Testing

Read the `tests/` directory and learn fixtures, assertions, monkeypatching, and Flask's test client.

Milestone: `pytest` passes after you deliberately change and restore one behavior.

## Stage 10: Iteration and submission

Run calls individually. After each early call, listen to the complete audio and record one change you made to improve latency, naturalness, task steering, or error handling. The final repository should make that iteration visible through commits, notes, and the Loom walkthrough.
