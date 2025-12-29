TEMPLATES = [
    {
        "template_id": "follow_up_neutral_v1",
        "intent": "follow_up",
        "tone_label": "neutral",
        "name": "Follow-up (Neutral)",
        "body": (
            "Subject: {{subject}}\n\n"
            "{{greeting}}\n\n"
            "{{context}}\n\n"
            "{{ask}}\n\n"
            "{{closing}}\n"
            "{{signature}}\n"
        ),
        "meta": {"version": 1},
    },
    {
        "template_id": "request_formal_v1",
        "intent": "request",
        "tone_label": "formal",
        "name": "Request (Formal)",
        "body": (
            "Subject: {{subject}}\n\n"
            "{{greeting}}\n\n"
            "{{context}}\n\n"
            "Would you be able to {{ask}}?\n\n"
            "{{closing}}\n"
            "{{signature}}\n"
        ),
        "meta": {"version": 1},
    },
    {
        "template_id": "apology_apologetic_v1",
        "intent": "apology",
        "tone_label": "apologetic",
        "name": "Apology (Apologetic)",
        "body": (
            "Subject: {{subject}}\n\n"
            "{{greeting}}\n\n"
            "I’m sorry for {{context}}.\n\n"
            "{{ask}}\n\n"
            "{{closing}}\n"
            "{{signature}}\n"
        ),
        "meta": {"version": 1},
    },
    {
        "template_id": "outreach_friendly_v1",
        "intent": "outreach",
        "tone_label": "friendly",
        "name": "Outreach (Friendly)",
        "body": (
            "Subject: {{subject}}\n\n"
            "{{greeting}}\n\n"
            "{{context}}\n\n"
            "{{ask}}\n\n"
            "{{closing}}\n"
            "{{signature}}\n"
        ),
        "meta": {"version": 1},
    },
    {
        "template_id": "other_neutral_v1",
        "intent": "other",
        "tone_label": "neutral",
        "name": "Generic (Neutral)",
        "body": (
            "Subject: {{subject}}\n\n"
            "{{greeting}}\n\n"
            "{{context}}\n\n"
            "{{ask}}\n\n"
            "{{closing}}\n"
            "{{signature}}\n"
        ),
        "meta": {"version": 1},
    },
]
