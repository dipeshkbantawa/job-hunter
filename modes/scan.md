# Mode: scan (daily routine)

1. `.venv\Scripts\python.exe -m hunter search --no-open`: fetch, filter by regions/visa/blacklist, score.
2. `.venv\Scripts\python.exe -m hunter inbox`: add the URLs the user dropped into `data/pipeline.md`.
3. `.venv\Scripts\python.exe -m hunter live`: drop postings that have closed.
4. `.venv\Scripts\python.exe -m hunter followups`: anything due today.
4b. `.venv\Scripts\python.exe -m hunter watch`: new notices on employers' own vacancy pages, such as Nepal Telecom.
    Notices are often scanned Nepali PDFs: read the deadline and eligibility from the notice before advising.
5. Summarise for the user in a few lines:
   - new jobs per region (priority order), anything tagged visa/relocation,
   - the top 5 new jobs worth evaluating (quick score + why),
   - follow-ups due,
   - new vacancy notices from `watch`.
   Then offer to `evaluate` the top ones. Point them to `data/digest.html` for the full list and to the
   region search links (LinkedIn, Indeed, Seek, Bayt, Naukrigulf, GulfTalent...) for jobs the feeds don't cover;
   anything they find there goes into `data/pipeline.md`.
