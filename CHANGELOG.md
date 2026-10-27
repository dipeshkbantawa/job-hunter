# Changelog

Versions follow `MAJOR.MINOR.PATCH`: a new feature bumps MINOR, a fix bumps PATCH. The version lives in
`hunter/__init__.py` (`python -m hunter --version`). Each release is tagged `vX.Y.Z` in git.

## [Unreleased]

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
