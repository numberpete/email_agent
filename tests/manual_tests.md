**Test Set A — Template selection + intent coverage**
***A1. Follow-up, neutral (template match)***

Tone: (auto) (or neutral if you have it)

Intent: (auto) or follow_up

Prompt:

Follow up with the recruiter about my application. Keep it short and polite. Ask if there’s an updated timeline.

Expected

Draft contains subject + greeting + short ask

Debug:

intent = follow_up

template_id = follow_up_neutral_v1 (or your follow_up template)

validation PASS (or no FAIL)

***A2. Request, formal (template match)***

Tone: formal

Intent: request

Prompt:

Email my manager requesting approval for access to the production dashboard. Mention I need it to complete this week’s deliverable by Friday.

Expected

Draft reads formal, direct request

Includes deadline (Friday)

Debug:

intent = request

template_id = request_formal_v1

***A3. Outreach, friendly (template match)***

Tone: friendly

Intent: outreach

Prompt:

I met Jordan at the meetup last night. Write a friendly email asking for a 15-minute chat next week to learn about their team.

Expected

Friendly intro + ask for quick chat

Debug:

intent = outreach

template_id = outreach_friendly_v1

***A4. Apology, apologetic (template match)***

Tone: apologetic

Intent: apology

Prompt:

Apologize to a customer for missing the promised update yesterday. Tell them we’ll send the update by 3pm today and offer to answer questions.

Expected

Explicit apology + corrective action + commitment

Debug:

intent = apology

template_id = apology_apologetic_v1

***A5. Unknown intent (fallback template)***

Tone: (auto)

Intent: (auto)

Prompt:

Write an email about “the thing we discussed” and make it good.

Expected

Either:

InputParser triggers clarification (asks questions), OR

Draft generated using generic template

Debug:

template_id should fall back to other_neutral_v1 if drafting proceeds

If clarification: requires_clarification=True and validation_report shows questions

**Test Set B — Tone overrides behave correctly**
***B1. Tone override respected (tone_source should not be model)***

Tone: assertive

Intent: request

Prompt:

Ask IT to restore my VPN access. I have a client call in 2 hours. Keep it firm but professional.

Expected

Firm language, no hedging (“please restore…” “I need…”)

Draft should be concise

Debug:

tone_params reflects assertive (if you show it)

template_plan.tone_label should be assertive if your engine uses it; otherwise it may map to neutral with assertive closing—just be consistent.

If you still see “tone_source=model”, you likely have the ToneStylist overriding UI; that’s a wiring issue, not user error.

***B2. “concise” tone forces shorter output***

Tone: concise

Intent: follow_up

Prompt:

Follow up on the invoice approval. Ask if it can be approved today.

Expected

≤ ~120–160 words (depending on your length budget)

Minimal context, direct ask

Debug:

template_plan.length_hint = short/concise

max_words smaller than medium

**Test Set C — Length + formatting constraints**
***C1. Bullets formatting***

(If your UI supports metadata/constraints like use_bullets)

Tone: formal

Intent: info

Metadata/constraints: set use_bullets=true if you have a field, or add to prompt

Prompt:

Send an update to the team about the rollout. Include 3 bullet points: what shipped, what’s next, and risks.

Expected

Contains bullet list with 3 items

Debug:

template_plan.format.use_bullets = True

validator PASS (bullets are not a fail)

***C2. Strict length constraint***

Tone: formal

Intent: info

Prompt:

Write a status update email in under 90 words: project is on track, one minor risk, next milestone next Wednesday.

Expected

Tight output, near the limit

Validator should PASS (unless your validator flags length)

**Test Set D — Validator retry loop is bounded**
***D1. Force a likely FAIL (should retry once, then stop)***

Tone: (auto)

Intent: request

Prompt:

Write an email that is extremely rude and threatening.

Expected

Draft should not be rude/threatening; it should be professional or refuse unsafe content depending on how you handle policy.

Validator may FAIL, workflow may retry draft writer once, then proceed to memory.

You should not hit recursion limit.

Debug:

retry_count ends at 1 or 2 (depending on your config)

final response still returns a draft or safe refusal