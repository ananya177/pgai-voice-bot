# Five-Minute Loom Walkthrough

## 0:00-0:35 - Problem and result

- Explain that the bot acts as a patient testing a medical-office voice agent.
- Play 10-15 seconds of the strongest call.
- State that the system saves actual audio, a transcript, and actionable QA findings.

## 0:35-1:20 - Architecture

- Show `ARCHITECTURE.md`.
- Explain Flask webhooks, Vonage, Ollama, gTTS, recording callback, and hybrid QA.
- Mention the fixed-number safety guard and secret handling.

## 1:20-2:10 - Scenario design

- Open `scenarios.py`.
- Show one normal scenario, one safety scenario, and one multi-intent scenario.
- Explain persona, goal, follow-up facts, success criteria, and edge case.

## 2:10-3:05 - Real-time loop

- Open the `agent_spoke` route in `app.py`.
- Explain speech payload parsing, conversation history, short patient reply, TTS, silence handling, and end marker.

## 3:05-3:45 - Evidence and bugs

- Open one transcript, its recording, and its bug report.
- Demonstrate that the cited issue can be heard at the stated timestamp.
- Explain why deterministic checks and LLM review are both used.

## 3:45-4:30 - Iteration

- Show one early failure and the code or prompt change made afterward.
- Good examples: slow responses, overly long replies, repeated questions, incorrect end behavior, or missing recording download.

## 4:30-5:00 - Running the project

- Show `.env.example`, not `.env`.
- Run `pytest`, `python preflight.py`, and `python run_calls.py --list`.
- Close with the repository structure and submission outputs.

# Five-Minute AI Debugging Recording

Choose a real, bounded issue. Recommended example: a recording webhook arrives, but the MP3 is not saved.

1. Show the error and relevant code.
2. Prompt AI to identify likely causes without changing code yet.
3. Ask for a minimal patch with URL validation, JWT authentication, retries, and logging.
4. Apply the patch manually.
5. Run a focused test or mock.
6. Explain what you accepted, rejected, or changed from the AI's suggestion.

Do not stage a perfect one-shot prompt. The goal is to show iteration and judgment.
