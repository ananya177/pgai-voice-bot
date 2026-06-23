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


Several candidate findings were reviewed but excluded from the confirmed product-bug count. Medication-name inconsistencies that appeared only in ASR transcripts were not included unless the recording clearly confirmed that the office agent actually said the wrong medication. Identity or profile mismatches were also excluded because the same originating phone number was reused across multiple synthetic patient identities, which made those cases a limitation of the test setup rather than a confirmed privacy defect.

Other excluded issues originated from the local patient simulator rather than the Pretty Good AI office agent. These included repeating the phone number instead of confirming information, answering intake questions with unrelated details, switching into the receptionist role, and ending calls prematurely because of an incorrect `[END_CALL]` marker or local turn-limit behavior. Incomplete calls caused by silence detection, webhook timing, or telephony behavior were treated as integration issues. Malformed Ollama JSON, unsupported automatic findings, and metadata remaining in an `ending` state were also excluded because they belonged to the local analysis and finalization workflow rather than the product being evaluated.
