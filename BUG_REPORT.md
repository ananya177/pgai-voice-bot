# Consolidated Bug Report

This report contains only findings manually verified against both the call recording and the speaker-labeled transcript. Patient-simulator errors, telephony/ASR artifacts, and unsupported automatic findings are excluded or labeled separately.

## Executive summary

- Final calls reviewed: 11
- Confirmed product bugs: 0
- High severity: 0
- Medium severity: 0
- Low severity: 0
- Non-product observations: 0

# Confirmed findings

No confirmed Pretty Good AI product bugs were identified in the 11 selected calls.

Several candidate issues were investigated, but they were excluded because they originated from the local patient simulator, reused caller identification, telephony timing, speech-recognition transcription, or unsupported automated analysis. No issue was counted as a product bug unless it was clearly attributable to the office agent and verified in both the transcript and recording.

# Quality observations

No separate conversational-quality observations are included in the final count.

Pauses, repeated verification, and silence-recovery behavior were reviewed during manual validation. However, the available evidence did not support classifying these behaviors as consistent product-quality defects rather than normal call latency, telephony behavior, or scenario-specific verification.

#  Excluded findings

EXC-01 — Medication-name inconsistency in ASR output:
Medication-name variations appearing only in automatically generated transcripts were excluded unless the corresponding recording clearly confirmed that the office agent spoke or confirmed the wrong medication.

EXC-02 — Profile mismatch caused by reused caller ID:
Identity and profile mismatches were excluded because the same originating phone number was reused for multiple synthetic patient identities. These cases were treated as limitations of the test setup rather than confirmed privacy defects.

EXC-03 — Incorrect or repeated patient responses:
Cases where the patient repeated a phone number, gave unrelated intake information, or switched into the receptionist role originated from the local patient simulator and were not classified as Pretty Good AI product bugs.

EXC-04 — Premature call termination:
Calls that ended because of an incorrect [END_CALL] marker, local turn limits, silence handling, or webhook timing were classified as caller-system or telephony integration issues.

EXC-05 — Automated analysis issues:
Malformed Ollama JSON and unsupported automatic findings were excluded because they originated from the local bug-analysis workflow and were not verified product defects.

EXC-06 — Metadata finalization status:
Calls whose metadata remained in an ending state were excluded as bugs after manual review confirmed that their recordings and transcripts were complete.