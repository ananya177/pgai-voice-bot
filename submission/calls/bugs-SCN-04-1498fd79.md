# Bug Report - SCN-04-1498fd79

**Scenario:** SCN-04 - Medication refill request  
**Persona:** Robert, 67, slightly hard of hearing. He asks for repetition once when something is unclear, but does not repeatedly ask after understanding.  
**Goal:** Request a refill for lisinopril 10mg  

## BUG-01: Incorrect Initial Medication Identification

**Severity:** High  
**Evidence:** [00:00] PATIENT: Yes hello, I need a refill on my blood pressure medication please.  
**Detection:** llm  

### Why this is a problem

The patient immediately states they need a refill for 'blood pressure medication,' failing to specify the exact drug. This leads to an unnecessary and potentially confusing data collection process.

### Expected behavior

Upon initial request regarding refills, the agent should proactively ask the patient which medication they require a refill for.

## BUG-02: Refill workflow omitted pharmacy information

**Severity:** Medium  
**Evidence:** The transcript contains no request or confirmation of a pharmacy.  
**Detection:** rule  

### Why this is a problem

The refill request may be incomplete or routed incorrectly.

### Expected behavior

Ask for or confirm the patient's preferred pharmacy and explain the refill timeline.

## BUG-03: Unnecessary Repeated Confirmation

**Severity:** Medium  
**Evidence:** [01:28] AGENT: could you please spell your first and last name for me [ASR confidence: 0.99]  
**Detection:** llm  

### Why this is a problem

The agent repeatedly confirms the patient's date of birth and name after initial verification, adding unnecessary steps to the process.

### Expected behavior

After confirming key identifiers (name and DOB), the agent should avoid redundant confirmation unless explicitly requested by the patient.

## BUG-04: Failure to Address Patient Confusion

**Severity:** Medium  
**Evidence:** [02:47] PATIENT: Could you repeat that? I didn't quite catch it.  
**Detection:** llm  

### Why this is a problem

The patient expresses confusion regarding the agent’s statement ('connecting you to a representative'), indicating potential issues with clarity or communication flow.

### Expected behavior

Upon receiving a clarification request, the agent should immediately rephrase the information clearly and concisely.
