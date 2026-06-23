# Bug Report - SCN-10-d0ac6127

**Scenario:** SCN-10 - Unclear mumbled request  
**Persona:** Maria, 34, soft-spoken, hesitant, and unclear  
**Goal:** Make a new general check-up appointment while speaking unclearly  

## BUG-01: Unnecessary Confirmation of Date of Birth

**Severity:** Medium  
**Evidence:** [00:34] AGENT: can you please provide your date of birth and [00:52] AGENT: just to confirm with that March 1st 1990 or March 1990 with no specific day could you clarify the exact date  
**Detection:** llm  

### Why this is a problem

The agent unnecessarily repeated and clarified the date of birth, adding an extra step when it was already provided. This increases friction for the patient.

### Expected behavior

Once the date of birth is provided, the agent should move directly to confirming the appointment type without further clarification.

## BUG-02: Potential Confusion with Existing Appointment

**Severity:** Low  
**Evidence:** [02:02] AGENT: you already have a general checkup appointment scheduled would you like to reschedule it to a different time or cancel your current appointment  
**Detection:** llm  

### Why this is a problem

The agent prematurely introduced the possibility of rescheduling/canceling an existing appointment before fully understanding the patient's needs. This could lead to confusion and unnecessary questioning.

### Expected behavior

Wait until the patient explicitly states they want to reschedule or cancel before mentioning their existing appointments.
