# Changelog

Versions follow `MAJOR.MINOR.PATCH`: a new feature bumps MINOR, a fix bumps PATCH. The version lives in
`hunter/__init__.py` (`python -m hunter --version`). Each release is tagged `vX.Y.Z` in git.

## [Unreleased]
### Added
- Dubizzle: job search links in the Dubai / UAE section, and its job profile in the career sites list.
- `Install-WatchTask.ps1`: schedules `hunter watch` twice a day.
- `hunter watch`: checks employers' own vacancy pages, follows links from listing pages, tries fiscal-year addresses
  such as Nepal Telecom's `/post/vacancy-notices-208384`, and sends a Windows notification (optional phone push) when a new notice appears.
- `companies.yaml`: about 100 verified company boards searched through their public APIs. New Ashby and SmartRecruiters
  sources; add your own slugs in `config.yaml`.
- `search` now scans the `company_careers` pages for matching roles (`hunter/careers.py`).
- `search --days N`: only fresh postings, company boards included. Greenhouse dates now use the first-published date.
- `apply` fills long questions from the job's `answers.md`, lists the fields left empty and saves them to `questions.md`.
- `apply --min-score` and the `apply:` settings (`daily_limit`, default 50; `min_score`).
- `/job-hunter batch` mode: shortlist this week's jobs, draft answers, prefill the forms.
- SDOC (sdoc.gov.np/vacancies, Government of Nepal) as a Nepal company career page in `config.example.yaml`.
- Kowork search links for South Korea; Kowork, JobKorea and SEEK Pass in the career sites list.
- South Korea jobs show whether the ad confirms foreign workers are hired (E-7 sponsorship, 외국인 지원 가능) and
  flag Korean-fluency requirements and Korean-only ads, in the dashboard and digest; `evaluate` treats Korean
  fluency or nationals-only as a hard blocker and makes "confirm E-7 sponsorship" the first step when the ad is silent.
- `hunter retag`: re-check stored ads for visa and foreign-worker signals after detection rules change.
- Overleaf flow: `hunter cv tex` writes an ATS-safe LaTeX CV (glyph-to-unicode, real inter-word spaces, no
  hyphenation or ligatures, no icons, PDF title); the dashboard's "CV in Overleaf" buttons open the master or
  tailored CV as a new Overleaf project (free plan); `hunter cv import <pdf> --job <id>` re-runs the ATS and fact
  checks on the PDF downloaded from Overleaf and links it for `apply`.
- Evaluation reports start with a match summary: match %, ATS keyword %, strengths, weaknesses, improvement tips.

### Changed
- `apply` no longer autofills on LinkedIn, Indeed or Glassdoor, whose terms forbid automation: those forms are filled by hand.
- Autofill no longer puts contact details into long-question text boxes.

## [0.5.0] - 2026-10-27
### Added
- `hunter dashboard`: a live web dashboard at `http://127.0.0.1:8765` with funnel cards, status tabs, search,
  region and visa filters, an evaluation report and job ad viewer, CV and cover letter PDF links, and status changes
  that go through the tracker like `hunter mark`.
- ATS scores per job: the format score of the CV you'd send and the share of the ad's keywords it contains.
- Missing skills column and a Skill gaps tab that totals missing keywords across jobs, with CSV export.
- Sortable columns in both tables; funnel cards open the jobs behind each number.
- `--version` flag and this changelog.

## [0.4.0] - 2026-10-27
### Added
- career-ops style workflow: `/job-hunter` modes for evaluate, tailor, cover, answers, contact, follow-up, interview,
  scan, compare, patterns and CV updates; per-job `applications/<id>-<slug>/` folders; `record`, `jd`, `live`, `add`,
  `inbox`, `followups`, `stats` and `cv`/`cover` builds with a fact check.

## [0.3.0] - 2026-10-27
### Added
- `cv-check`: ATS-friendliness check and keyword gap against tracked jobs (plural forms count as matches).
- Visa sponsorship and relocation tagging, with its own digest section and per-country sponsorship searches.

## [0.2.0] - 2026-10-26
### Added
- Region priority (Remote, Australia, New Zealand, South Korea, Dubai, Singapore, Nepal) and a CV section in the digest.
- Naukrigulf, GulfTalent and company career pages for Dubai.

## [0.1.0] - 2026-10-26
### Added
- First version: remote job search across public job APIs, scoring against the CV, SQLite tracker, HTML digest and
  browser autofill.
