# Mode: contact (who to message, and what to say)

1. From the JD and company, list the 2-3 people worth contacting, by role rather than by guessing names:
   the hiring manager (team lead of the role's team), a recruiter for that region, and a peer on the team.
   Give LinkedIn search URLs the user can open, e.g.
   `https://www.linkedin.com/search/results/people/?keywords=<company>%20<team>%20manager`.
   Do not scrape LinkedIn or browse it for the user.
2. Draft one message per contact type in `applications/<id>-<slug>/outreach.md`:
   - LinkedIn connection note: max 300 characters.
   - Hiring manager: one concrete proof point mapped to their team's problem + a direct question.
   - Recruiter: role title, region/visa or remote status in one line, one proof point, ask about next steps.
   - Peer: a genuine question about the team's work; no ask for a referral in the first message.
   - Facts only from `cv.yaml`.
3. The user sends the messages themselves. Afterwards: `hunter followups --done <id>` if it counts as a follow-up.
