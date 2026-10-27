# Mode: patterns (what's working)

1. `.venv\Scripts\python.exe -m hunter stats`: funnel, applications by region and source.
2. `.venv\Scripts\python.exe -m hunter list --status rejected --limit 100` and `--status applied`: read their
   `report.md` gaps.
3. `.venv\Scripts\python.exe -m hunter cv-check`: keyword gaps across the jobs being targeted.
4. Tell the user, briefly:
   - where replies come from (region, source, role type) and where they don't,
   - the gaps that keep recurring in rejected or low-rated jobs, and which are fixable quickly (wording, a
     certification in progress) vs. long-term (a skill to learn),
   - the response rate if there are 10+ applications, and what to change (fewer, better-fit applications;
     different role titles; different regions).
   Suggest at most 3 concrete changes. Never suggest adding unearned skills to the CV.
