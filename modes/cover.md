# Mode: cover (cover letter)

## Inputs
`report.md` (blocks B, C, E), `jd.md`, `cv.yaml`, `profile.md`.

## Write `applications/<id>-<slug>/cover.yaml`
```yaml
company: Company name
role: Role title
recipient: Hiring Manager    # or a real name if the JD gives one
greeting: Dear Hiring Manager,
paragraphs:
  - Hook: the role and one concrete reason this candidate fits it (a real achievement mapped to the JD's top need).
  - Proof: two or three short achievements from cv.yaml that answer the JD's must-haves, in the JD's words.
  - Why them: one specific thing about the company or team from the JD (or a source the user gives you), not flattery.
  - Logistics, only when relevant: remote from GMT+5:45 with APAC overlap, or open to relocating with sponsorship.
  - Close: one sentence, a direct ask for a conversation.
closing: Kind regards,
```
Rules: 250-350 words, plain confident English, no "passionate", no clichés, every fact and number from
`cv.yaml`. Show the draft in chat and get the user's OK before building.

## Build
`.venv\Scripts\python.exe -m hunter cover build --data applications/<id>-<slug>/cover.yaml --job <id>`
(The numbers fact check must pass.)
