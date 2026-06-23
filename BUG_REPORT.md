# Consolidated Bug Report

This report contains only findings manually verified against both the call recording and the speaker-labeled transcript. Patient-simulator errors, telephony/ASR artifacts, and unsupported automatic findings are excluded or labeled separately.

## Executive summary

- Final calls reviewed: **ADD NUMBER (minimum 10)**
- Confirmed product bugs: **ADD NUMBER**
- High severity: **ADD NUMBER**
- Medium severity: **ADD NUMBER**
- Low severity: **ADD NUMBER**
- Non-product observations: **ADD NUMBER**

## Confirmed findings

### BUG-01 - ADD SHORT TITLE

- **Severity:** High / Medium / Low
- **Scenario:** SCN-XX - Scenario name
- **Call:** `CALL-ID`
- **Evidence:** `transcript-CALL-ID.txt` at `MM:SS`; confirm in `recording-CALL-ID.mp3`
- **Patient request:** Add the exact request in a short paraphrase.
- **Actual behavior:** Describe exactly what the office agent did.
- **Why it matters:** Explain the user, safety, accuracy, or workflow impact.
- **Expected behavior:** Describe the correct response or action.
- **Reproduction steps:**
  1. Run `python run_calls.py --scenario SCN-XX`.
  2. Allow the patient scenario to reach the relevant turn.
  3. Observe the office agent's response.
- **Verification note:** State that the recording confirms the behavior and that it is not merely a transcript/ASR error.

---

### BUG-02 - ADD SHORT TITLE

- **Severity:** High / Medium / Low
- **Scenario:** SCN-XX - Scenario name
- **Call:** `CALL-ID`
- **Evidence:** `transcript-CALL-ID.txt` at `MM:SS`; confirm in `recording-CALL-ID.mp3`
- **Patient request:**
- **Actual behavior:**
- **Why it matters:**
- **Expected behavior:**
- **Reproduction steps:**
- **Verification note:**

## Quality observations

Use this section for issues that reduce conversational quality but are not clear functional bugs, such as excessive pauses, repeated verification, awkward wording, or poor recovery from silence.

### OBS-01 - ADD TITLE

- **Scenario / Call:**
- **Evidence:**
- **Observation:**
- **Impact:**
- **Suggested improvement:**

## Excluded findings

Record false positives here to demonstrate careful analysis.

| Candidate finding | Why excluded |
|---|---|
| Example: medication name appears incorrect in ASR transcript | Excluded unless the recording confirms the agent actually spoke the wrong medication name. |
| Example: profile mismatch under a reused caller ID | Excluded when caused by the test harness using one number for multiple synthetic identities. |
| Example: patient repeated or ended early | Classified as a caller-simulator defect, not a PGAI product bug. |
