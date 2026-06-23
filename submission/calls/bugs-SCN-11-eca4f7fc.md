# Bug Report - SCN-11-eca4f7fc

**Scenario:** SCN-11 - Wrong number / misdial scenario  
**Persona:** Betty, 70, called the wrong clinic  
**Goal:** Ask about a doctor that doesn't work there  

## BUG-01: Agent may have failed to correct a wrong-office assumption

**Severity:** Medium  
**Evidence:** Dr. Patel is discussed without clear correction that the caller reached a different office.  
**Detection:** rule  

### Why this is a problem

The caller may believe they reached a clinician or practice that is not represented by the agent.

### Expected behavior

Clearly identify the practice and correct the caller before offering further help.
