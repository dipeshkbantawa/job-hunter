# Mode: pipeline (paste a job → everything)

Run these in order, stopping at any gate:
1. `modes/evaluate.md`: gates, report, rating, record.
2. If the rating is below 4.0: stop, give the verdict, and ask whether the user still wants documents.
3. `modes/tailor.md`: tailored CV PDF (fact-checked, ATS 100).
4. `modes/cover.md`: draft in chat, user OK, build PDF.
5. If the rating is 4.5 or higher: `modes/answers.md`.
6. Finish with a short summary: rating, verdict, files created (paths), and the next action for the user
   (`hunter apply <id>`, then `hunter mark <id> applied`).
