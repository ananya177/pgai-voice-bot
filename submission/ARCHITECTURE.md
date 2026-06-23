# Architecture

The bot uses a webhook-driven call loop. `run_calls.py` asks the Flask application to start a selected scenario, and the application creates an outbound Vonage Voice API call to the challenge's fixed assessment number. When the call is answered, Vonage requests an NCCO from the server, plays the patient's opening line, records the call, and listens for the office agent. Each recognized agent turn is sent back to Flask, stored in the call history, answered by `patient_brain.py`, converted to speech, and returned as the next Vonage action. The patient engine combines deterministic handling for identity, date of birth, phone number, medication, pharmacy, and scenario-critical decisions with a local Ollama model for natural improvisation.

The design favors reliability and auditability over complexity. The target phone number is hard-locked, secrets stay outside the repository, and every call produces separate audio, transcript, metadata, and findings files. Deterministic rules prevent common patient-simulator failures such as role switching, repeated intake answers, unsupported clinic statements, and premature call termination. After a call, rule-based checks and optional local-LLM analysis identify possible issues, but only findings confirmed against the full recording and transcript are included in the final bug report.

## Data flow

```text
run_calls.py
    |
    v
Flask /make-call
    |
    v
Vonage outbound call ---> PGAI assessment line
    ^                            |
    |                            v
    +--- agent speech webhook ---+
    |
    +--- state/history ---> deterministic rules ---> Ollama fallback
    |                                             |
    +<---------------- patient response <---------+
    |
    +--- gTTS/Vonage TTS ---> patient audio
    |
    +--- recording callback ---> MP3 download
    |
    +--- transcript ---> QA analysis ---> bug report
```
