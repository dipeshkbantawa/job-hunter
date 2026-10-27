# Mode: pipeline (paste a job → everything)

Run these in order, stopping at any gate:
1. `modes/evaluate.md`: gates, report, rating, record.
2. If the rating is below 4.0: stop, give the verdict, and ask whether the user still wants documents.
3. `modes/tailor.md`: tailored CV PDF (fact-checked, ATS 100), already linked to the job.
3b. Overleaf (optional, if the user wants to polish the layout or wording by hand):
   `hunter cv tex --data applications/<id>-<slug>/cv.yaml --job <id>`, then tell the user: dashboard → the job →
   "Tailored CV in Overleaf" (creates a project in their Overleaf account; compile with pdfLaTeX), edit, download
   the PDF, then run `hunter cv import <downloaded.pdf> --job <id>`. The import re-runs the ATS and fact checks and
   links that PDF for `apply`. If they skip Overleaf, the PDF from step 3 is used.
4. `modes/cover.md`: draft in chat, user OK, build PDF.
5. If the rating is 4.5 or higher: `modes/answers.md`.
6. Finish with a short summary: the match summary (match %, ATS keywords %, strengths, weaknesses, tips), rating,
   verdict, files created (paths), and the next action for the user: review in the dashboard, optionally polish
   in Overleaf (3b), then `hunter apply <id>` (autofills; the user checks and clicks Submit), then
   `hunter mark <id> applied`.
