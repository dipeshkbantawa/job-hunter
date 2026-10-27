# Mode: cv-update (change the master CV)

Only when the user gives you new facts (a new role, a finished certification, a project, a corrected number).

1. Edit `cv.yaml` with exactly what the user said. Ask for dates and numbers rather than estimating.
2. Rebuild and check: `.venv\Scripts\python.exe -m hunter cv build`, then make sure the score is 100 and it's
   still 2 pages.
3. If `config.yaml` → `profile.resume` points to the built PDF, the new file is what `apply` and `update-cv` use.
   Offer to run `.venv\Scripts\python.exe -m hunter update-cv` (the user runs it; it opens each career site
   and attaches the CV, and they click Save).
4. Update `profile.md` if a gap closed (e.g. AZ-104 passed).
