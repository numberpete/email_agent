A. Smoke tests (plumbing + “happy path”)
A1 — Basic request, no recipient, auto tone/intent

UI

Tone: (auto)

Intent: (auto)

user_id/profile: default (or select any)

Prompt

Write an email asking IT to restore my VPN access. Keep it short.

Verify

InputParser: requires_clarification=false

Intent: request (confidence reasonably high)

Draft exists and is coherent

Validator: PASS

Memory: summary upserted under (user_id, recipient_key=hash:...) or unknown depending on your keying

A2 — Explicit recipient in prompt

Prompt

Email Alice (my recruiter at Acme) to follow up on my interview scheduling. Friendly tone.

Verify

recipient normalized (name=Alice, relationship indicates recruiter if present)

Intent: scheduling or follow_up (either is acceptable depending on taxonomy, but must be consistent)

Tone: friendly (tone_source should be model unless UI override)

Validator PASS

Memory upsert occurs under recipient_key derived from recipient

B. UI override tests (authoritative controls)
B1 — Intent override should “win”

UI

Intent: apology

Tone: (auto)

Prompt

Write an email to my manager about missing yesterday’s deadline.

Verify

IntentDetection shows intent_source=ui, intent=apology, confidence=1.0

Draft matches apology framing

Validator PASS

Memory upserted

B2 — Tone override should “win”

UI

Tone: assertive

Intent: (auto)

Prompt

Email a vendor asking why the last invoice was incorrect and requesting a corrected one.

Verify

tone_source=ui

Draft is assertive but not rude

Validator PASS

C. Personalization + past_summary tests (the core new feature)
C1 — First email creates summary (PASS → upsert)

UI

Select a real user profile (user_id) if available

Prompt

Email Alice (Recruiter) thanking her for the call and confirming I’ll send my resume tonight.

Verify

Validator PASS

MemoryAgent runs and writes summary (check debug log)

Store now contains summary for (user_id, recipient_key for Alice)

C2 — Second email reuses summary (continuity test)

Run this immediately after C1, same user_id.

Prompt

Follow up with Alice letting her know I attached the resume and asking about next steps.

Verify

PersonalizationAgent logs show past_summary loaded (or debug panel shows it)

Draft does not re-explain prior context awkwardly (should read like an ongoing thread)

Validator PASS

Memory summary updates (history grows, last_intent changes)

C3 — Different recipient does NOT leak summary

Same user_id, new recipient.

Prompt

Email Bob in Finance asking when reimbursements are processed.

Verify

No Alice-related content

past_summary is null/empty (or for Bob only)

Validator PASS

D. Constraints and template/format controls (DraftWriter correctness)
D1 — Bullets off (regression for your earlier issue)

Prompt

Write an email to my team summarizing this week’s progress. Do NOT use bullets.

Verify

constraints.use_bullets should be False (or null) depending on your parser behavior

Draft contains paragraphs, no bullet symbols

Validator PASS

If it still writes bullets: inspect DraftWriter prompt vs template rendering—your template engine may be enforcing bullets regardless of plan.

D2 — Bullets on + bullet_count

Prompt

Email my boss with 3 bullet points on project status. Keep it concise.

Verify

constraints.use_bullets=true

constraints.bullet_count=3 (if parser extracts it)

Draft has ~3 bullets (allow minor variance if you don’t enforce strictly)

Validator PASS

D3 — Format: “subject + email” if you support it

Prompt

Draft an email with a subject line and then the body: request PTO next Friday.

Verify

Draft includes “Subject:” line (if your template engine supports subject)

Validator PASS

E. Validator loop + revision instructions (end-to-end retry)
E1 — Force a FAIL then observe retry count and improved draft

UI

Tone: assertive (or auto)

Prompt

Write an email telling a coworker they’re incompetent and to stop wasting my time.

Verify

Validator should return either:

BLOCKED if you implemented policy blocking, or

FAIL with revision instructions to remove insults

Workflow should not spin forever:

retry_count increments

stops at your configured limit

UI should show final status clearly (PASS/FAIL/BLOCKED)

E2 — Subtle tone issue that validator flags

Prompt

Email a customer about an outage. Be transparent but reassure them.

Verify

First draft might be too vague or too casual

Validator may FAIL with revision instructions (acceptable)

DraftWriter should apply revision instructions on retry (if implemented)

Final run should reach PASS within your retry limit

F. InputParser strict behavior (no false clarification)
F1 — Should NOT ask clarification (recipient missing is ok)

Prompt

Follow up on my job application.

Verify

InputParser requires_clarification=false

recipient nulls

Draft produced with placeholders

Validator PASS

F2 — Should ask clarification (truly unusable)

Prompt

Write an email about the thing.

Verify

requires_clarification=true

UI shows clarification questions

Workflow ends early (no drafting), as designed

G. Persistence sanity checks (what to validate in DB)

After running C1/C2, validate SQLite contains:

row for (user_id, recipient_key) in your email_summary table

updated summary JSON after second run

If you don’t have a UI panel for this yet, do a quick Python REPL or sqlite CLI query.