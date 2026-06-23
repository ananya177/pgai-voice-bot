# Bug Report - SCN-07-1c3da104

**Scenario:** SCN-07 - Sunday reschedule edge case  
**Persona:** Maria, 34, existing patient, polite but persistent  
**Goal:** Try to reschedule an existing appointment to Sunday at 10am  

## BUG-01: Incorrectly Reschedules to Sunday

**Severity:** High  
**Evidence:** 02:41 AGENT: it looks like you already have a new patient consultation scheduled if you'd like I can help you reschedule or cancel that appointment or I can connect you with a team member for further help what would you like to do  
**Detection:** llm  

### Why this is a problem

The agent failed to recognize the user’s intent to reschedule to Sunday at 10am and instead focused on rescheduling the existing new patient consultation, potentially leading to an incorrect appointment being scheduled.

### Expected behavior

The agent should have confirmed that Sunday at 10am was unavailable due to clinic closure and offered a weekday alternative.
