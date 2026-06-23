# PGAI Voice Bot

An automated Python voice bot built for the Pretty Good AI AI Engineering Challenge. The system calls the official assessment line, roleplays realistic patients, records and transcribes both sides of each conversation, and produces structured QA findings for manual review.

## Submission links

- Public GitHub repository: https://github.com/ananya177/pgai-voice-bot
- Product walkthrough video and AI debugging video : https://www.loom.com/share/82a2c9ba128545a79078d3338fe87070

- Single originating phone number used for every assessment call: **+14067170529**

## What the project does

- Places outbound calls through the Vonage Voice API.
- Restricts calls to the official assessment number: `+18054398008`.
- Uses scenario-specific patient personas and goals.
- Uses deterministic intake handling plus a local Ollama model for natural patient responses.
- Generates patient speech with gTTS, with a provider-side TTS fallback.
- Captures recognized agent speech through Vonage webhooks.
- Records the complete call and downloads it as MP3.
- Saves a timestamped, speaker-labeled transcript.
- Runs rule-based QA checks and optional local-LLM analysis.
- Includes a terminal simulator for free testing before paid calls.

## Architecture

```text
Operator / run_calls.py
          |
          v
Flask webhook server ----> Vonage Voice API ----> PGAI assessment line
          ^                         |
          |                         v
          +---- recognized agent speech
          |
          +---- patient_brain.py ----> Ollama
          |                |
          |                +---- deterministic scenario handling
          |
          +---- tts.py ----> patient MP3 ----> Vonage stream
          |
          +---- transcript + recording + findings + metadata
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the design rationale.

## Repository structure

```text
app.py                 Flask routes and real-time call loop
run_calls.py           CLI for one scenario or a controlled batch
start.py               Tunnel and Flask startup
scenarios.py           Patient personas, facts, and test goals
patient_brain.py       Deterministic answers and Ollama prompting
tts.py                 Patient speech generation
transcriber.py         Speaker-labeled transcript generation
bug_analyzer.py        Rule-based and optional LLM QA analysis
simulate.py            Local text-only scenario testing
preflight.py           Configuration and dependency checks
tests/                 Unit and Flask route tests
calls/final/           Selected final recordings, transcripts, and reports
BUG_REPORT.md          Manually verified consolidated findings
ARCHITECTURE.md        Design explanation
.env.example           Required environment variables without secrets
```

## Prerequisites

- Python 3.10 or newer
- Ollama with `gemma3:4b` or another tested local model
- Vonage Voice API application and virtual number
- Cloudflare `cloudflared`

## Setup

```bash
git clone YOUR_PUBLIC_REPOSITORY_URL
cd pgai-voice-bot

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

cp .env.example .env
ollama pull gemma3:4b
```

Configure `.env` with the Vonage application ID, Vonage number, and private-key path. Do not commit `.env` or `private.key`.

## Validate before calling

```bash
python -m pytest -q
python preflight.py
python simulate.py --scenario SCN-04
```

## Run

Terminal 1:

```bash
python start.py
```

Terminal 2:

```bash
python run_calls.py --list
python run_calls.py --scenario SCN-01
```

After each call, inspect the matching files under `calls/` before running another scenario.

## Evidence produced per call

```text
recording-<call-id>.mp3
transcript-<call-id>.txt
bugs-<call-id>.md
findings-<call-id>.json
metadata-<call-id>.json
```

The final submission contains at least ten manually selected calls with both audio and transcript evidence. Calls with patient-role drift, premature endings, poor audio, or incomplete task flow are kept out of `calls/final/`.

## Scenario coverage

| Scenario | Test area |
|---|---|
| SCN-01 | New appointment scheduling |
| SCN-02 | Rescheduling an existing appointment |
| SCN-03 | Appointment cancellation |
| SCN-04 | Medication refill and medication-name verification |
| SCN-05 | Office hours, weekends, and after-hours guidance |
| SCN-06 | Insurance questions |
| SCN-07 | Closed-day scheduling edge case |
| SCN-08 | Urgent symptom escalation |
| SCN-09 | Interruptions and changing requests |
| SCN-10 | Vague request clarification |
| SCN-11 | Wrong-office handling |
| SCN-12 | Multi-intent completion |

## Safety and privacy

- The target-number guard rejects calls to any number other than `+18054398008`.
- Secrets are loaded from environment variables and are excluded from version control.
- Test personas use synthetic data only.
- Recording downloads are restricted to trusted Vonage/Nexmo HTTPS hosts.
- Automatic findings are manually checked against the transcript and audio before inclusion in the consolidated report.

## Known limitations

- Speech recognition can mishear medication names, names, and phone numbers.
- A local model may add latency on slower hardware.
- The remote agent may associate the single originating number with a previously created profile; final scenarios account for this behavior.
- Cloudflare Quick Tunnel URLs are temporary and intended for development use.

## Final verification

```bash
python prepare_submission.py
```

This checks selected call evidence, required repository files, and common secret-file mistakes before submission.
