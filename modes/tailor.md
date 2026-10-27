# Mode: tailor (ATS CV for one job)

## Inputs
`applications/<id>-<slug>/report.md` (run `evaluate` first if it is missing), `jd.md`, master `cv.yaml`.

## Rules
- Copy `cv.yaml` to `applications/<id>-<slug>/cv.yaml` and edit the copy, never the master.
- **Reword, reorder, select. Never add.** No new numbers, employers, titles, dates, certifications or skills.
  The `cv build` fact check enforces this; if it fails, fix the copy instead of bypassing.
- Mirror the JD's vocabulary only where the experience is real (JD "incident management" + CV "resolved escalated
  issues end to end" → "incident management: resolved escalated issues end to end").
- `headline`: the JD's role title if it honestly fits, plus 2-3 of its key areas.
- `summary`: 3-4 lines; the first line answers "what role, why this candidate"; put the top 5 JD keywords here.
- `competencies`: 6-9 phrases from the JD that the CV supports.
- In each role, order bullets so the one matching the JD's riskiest requirement comes first. You may drop
  irrelevant bullets (keep at least one per role) and drop irrelevant projects.
- Keep it to 2 pages. Keep section headings as they are (ATS-standard).

## Build and check
```
.venv\Scripts\python.exe -m hunter cv build --data applications/<id>-<slug>/cv.yaml --job <id>
.venv\Scripts\python.exe -m hunter cv-check --file <the PDF it printed> --job <id>
```
Target: format score 100 and keyword match as high as the truth allows. Report the remaining missing
keywords to the user and ask whether any are true for them (if yes, they go into the master `cv.yaml` first,
via `modes/cv-update.md`).
