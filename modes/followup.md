# Mode: followup

1. Run `.venv\Scripts\python.exe -m hunter followups`. It lists applications due a nudge:
   - applied: first follow-up after 7 days, second after another 7, then "cold" (suggest marking rejected)
   - responded / assessment: reply or check-in after 1 day, then every 3 days
   - interview: thank-you note the day after, then a check-in every 3 days
2. For each due item, read its `report.md` and draft a message in its `outreach.md`:
   - First follow-up (email or LinkedIn): 3-4 sentences: role, date applied, one new or sharp proof point,
     a simple question about the timeline.
   - Second follow-up: 2 sentences, polite, last nudge.
   - Interview thank-you: thank them, one specific moment from the conversation (ask the user), one line
     reinforcing fit.
3. The user sends them. Then record each: `hunter followups --done <id>`.
4. If the user tells you about a reply, update the stage: `hunter mark <id> responded|assessment|interview|offer|rejected`.
