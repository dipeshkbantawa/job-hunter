# Mode: answers (application form)

Draft answers for the application form. **The user submits; you never click Submit.**

1. Get the questions: ask the user to paste them, or list the visible ones from the page they share.
   If none are given, draft the usual set: why this role, why this company, a relevant achievement,
   why you're a good fit, salary expectation, notice period, work authorization / visa, how you heard about it.
2. Answer each in 2-4 sentences in `applications/<id>-<slug>/answers.md`:
   - Tone: confident, specific, choosing them. The proof is the hook ("I built X that did Y"), not adjectives.
   - Facts only from `cv.yaml`, `profile.md`, `story-bank.md`.
   - **Work authorization**: state it truthfully from `profile.md` (Nepali citizen; needs sponsorship for that
     country; remote from Nepal needs none). Never tick "authorized to work" when it isn't true.
   - **Salary**: use `profile.md`; if it's TODO, ask the user instead of inventing a number.
   - Knock-out questions (years of X, certification Y): answer truthfully; flag any that would disqualify.
3. Then point the user to the guided browser apply, which autofills contact fields and attaches the tailored
   CV if one was built:
   `.venv\Scripts\python.exe -m hunter apply <id>`
   After they submit: `hunter mark <id> applied`.
