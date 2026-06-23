"""
Patient scenarios for the PGAI voice bot tester.
Each scenario has a persona, goal, opening line, and follow-up hints.
"""

SCENARIOS = [
    {
        "id": "SCN-01",
        "name": "Simple appointment scheduling",
        "persona": "Maria, 34, working mom, polite but in a hurry",
        "goal": "Schedule a new patient appointment for next Tuesday morning",
        "opening": "Hi, I'd like to make an appointment. I'm a new patient.",
        "follow_ups": [
            "Tuesday morning works best for me, around 9 or 10am",
            "My name is Maria Johnson, date of birth March 15 1990",
            "I have Blue Cross insurance"
        ],
        "success_criteria": "Agent confirms a specific date, time, and gives next steps",
        "edge_to_watch": "Does agent check availability before confirming?"
    },
    {
        "id": "SCN-02",
        "name": "Existing appointment reschedule",
        "persona": "Maria, 34, an existing patient, polite and flexible",
        "goal": "Reschedule Maria's existing appointment to the next available Friday morning",
        "opening": (
            "Hi, this is Maria Johnson. I need to reschedule the appointment "
            "already on my account to the next available Friday morning."
        ),
        "patient_details": {
            "full_name": "Maria Johnson",
            "spelled_name": "M-A-R-I-A, J-O-H-N-S-O-N",
            "date_of_birth": "March 15th, 1990",
            "original_appointment": "Tuesday, June 30th at 9:45 a.m",
            "preferred_time": "The next available Friday morning works for me.",
        },
        "follow_ups": [
            "I’m calling for myself.",
            "My date of birth is March 15th, 1990.",
            "It’s spelled M-A-R-I-A, J-O-H-N-S-O-N.",
            "The appointment I want to move is Tuesday, June 30th at 9:45 a.m",
            "The next available Friday morning works for me.",
            "Please confirm the new date and time once it has been rescheduled.",
        ],
        "success_criteria": (
            "Agent verifies Maria's identity, finds the existing appointment, "
            "offers a specific Friday time, reschedules it, and confirms the new date and time."
        ),
        "edge_to_watch": (
            "Does the agent verify identity before making changes, find the existing "
            "appointment tied to the caller ID, and confirm the replacement date and time?"
        ),
    },
    {
        "id": "SCN-03",
        "name": "Appointment cancellation",
        "persona": "Sarah, 28, anxious, speaks fast",
        "goal": "Cancel tomorrow's appointment",
        "opening": "I need to cancel my appointment tomorrow, something came up at work.",
        "follow_ups": [
            "Sarah Williams",
            "Tomorrow at 11am",
            "No I don't need to reschedule right now"
        ],
        "success_criteria": "Agent cancels and confirms cancellation",
        "edge_to_watch": "Does agent ask about rescheduling? Does it note cancellation policy?"
    },
    {
        "id": "SCN-04",
        "name": "Medication refill request",
        "persona": "Robert, 67, hard of hearing, asks to repeat things",
        "goal": "Request a refill for lisinopril 10mg",
        "opening": "Yes hello, I need a refill on my blood pressure medication please.",
        "follow_ups": [
            "Could you repeat that? I didn't quite catch it.",
            "It's lisinopril, 10 milligrams",
            "Robert Garcia, born June 3rd 1957"
        ],
        "success_criteria": "Agent logs refill request and gives timeline",
        "edge_to_watch": "Does agent handle repetition gracefully? Does it ask for pharmacy info?"
    },
    {
        "id": "SCN-05",
        "name": "Office hours inquiry",
        "persona": "Jennifer, 41, direct and businesslike",
        "goal": "Find out office hours and whether they're open on weekends",
        "opening": "Quick question — what are your office hours? Are you open on weekends?",
        "follow_ups": [
            "What about Saturday?",
            "Is there an after-hours line for urgent issues?",
            "Thank you, that's all I needed"
        ],
        "success_criteria": "Agent gives accurate hours and weekend policy",
        "edge_to_watch": "BUG TARGET: Does agent incorrectly say they're open Sunday?"
    },
    {
        "id": "SCN-06",
        "name": "Insurance verification",
        "persona": "Tom, 39, confused about insurance",
        "goal": "Find out if the practice accepts Aetna PPO",
        "opening": "Hi, I want to become a patient but I need to check if you take my insurance first.",
        "follow_ups": [
            "I have Aetna PPO",
            "What about Aetna HMO, would that be different?",
            "Do you need my member ID to check?"
        ],
        "success_criteria": "Agent answers clearly about insurance acceptance",
        "edge_to_watch": "Does agent give confident wrong answer about insurance?"
    },
    {
        "id": "SCN-07",
        "name": "Sunday appointment edge case",
        "persona": "Lisa, 30, unaware offices close on weekends",
        "goal": "Try to book an appointment for Sunday",
        "opening": "I'd like to come in this Sunday at 10am, is that available?",
        "follow_ups": [
            "Oh really? You're closed Sundays?",
            "What's the earliest Monday morning slot?",
            "Okay let's do Monday then"
        ],
        "success_criteria": "Agent should say office is closed Sunday and offer weekday alternative",
        "edge_to_watch": "BUG TARGET: Does agent mistakenly book Sunday appointment?"
    },
    {
        "id": "SCN-08",
        "name": "Urgent symptom call",
        "persona": "Mike, 45, worried about chest tightness",
        "goal": "Describe urgent symptoms and see how agent handles it",
        "opening": "I've been having some chest tightness since this morning and I'm not sure if I should come in.",
        "follow_ups": [
            "It's not severe, more like pressure",
            "I'm 45, no history of heart problems",
            "Should I go to urgent care instead?"
        ],
        "success_criteria": "Agent should triage appropriately, possibly escalate to nurse/doctor",
        "edge_to_watch": "Does agent just schedule normally without flagging urgency?"
    },
    {
        "id": "SCN-09",
        "name": "Interruption and barge-in test",
        "allow_barge_in": True,
        "persona": "Karen, 55, impatient, talks over the agent",
        "goal": "Test how agent handles being interrupted mid-sentence",
        "opening": "Hi I need an appointment—actually wait, do you have anything today?",
        "follow_ups": [
            "No wait, actually tomorrow is better",
            "Sorry, I keep changing my mind — let me just say Wednesday",
            "Wednesday afternoon please"
        ],
        "success_criteria": "Agent handles interruptions gracefully without getting confused",
        "edge_to_watch": "Does agent lose context after interruptions? Does it double-book?"
    },
    {
        "id": "SCN-10",
        "name": "Unclear mumbled request",
        "persona": "Maria, 34, soft-spoken, hesitant, and unclear",
        "goal": "Make a new general check-up appointment while speaking unclearly",
        "opening": (
            "Um yeah hi so I was wondering if maybe I could like... "
            "get an appointment or something?"
        ),
        "patient_details": {
            "full_name": "Maria Johnson",
            "spelled_name": "M-A-R-I-A, J-O-H-N-S-O-N",
            "date_of_birth": "March 15th, 1990",
            "appointment_type": "general check-up",
            },
        "follow_ups": [
            "Like, for a general check-up, I guess.",
            "I’m not sure—whenever you have an opening is fine.",
            "Wednesday afternoon would work for me.",
            "A separate new appointment, please.",
        ],
        "success_criteria": (
            "Agent clarifies the vague request, verifies the patient, offers a "
            "specific appointment time, and confirms the booking."
        ),
        "edge_to_watch": (
            "Does the agent give up, transfer unnecessarily, or fail to turn "
            "the vague request into a specific confirmed appointment?"
        ),
    },
    {
        "id": "SCN-11",
        "name": "Wrong number / misdial scenario",
        "persona": "Betty, 70, called the wrong clinic",
        "goal": "Ask about a doctor that doesn't work there",
        "opening": "Hello, I'm looking for Dr. Patel's office. Is this Dr. Patel?",
        "follow_ups": [
            "Oh, this isn't Dr. Patel's office?",
            "I'm sorry, I must have the wrong number",
            "Wait, do you have any doctors available? Maybe I'll just make an appointment here."
        ],
        "success_criteria": "Agent handles confusion gracefully and pivots if needed",
        "edge_to_watch": "Does agent pretend to be Dr. Patel's office?"
    },
    {
        "id": "SCN-12",
        "name": "Multiple requests in one call",
        "persona": "Chris, 38, efficient, wants to do everything in one call",
        "goal": "Schedule appointment AND request a prescription refill in one call",
        "opening": "Hi, I need to do a couple things — schedule an appointment and also get a refill on my metformin.",
        "follow_ups": [
            "For the appointment, next week any day works",
            "For the metformin, I take 500mg twice daily",
            "Can you handle both of those?"
        ],
        "success_criteria": "Agent handles multiple requests without dropping one",
        "edge_to_watch": "Does agent forget the refill after booking the appointment?"
    }
]
