# job-hunter

A local job-search system for **Remote, Australia, New Zealand, South Korea, Dubai, Singapore and Nepal**, in that priority order. The design follows [career-ops](https://github.com/career-ops-hq/career-ops):

- **Python does the mechanical work:** finding jobs, tracking them, checking postings are still open, building ATS-safe PDFs and fact-checking them.
- **Claude Code does the judgment work** through the `/job-hunter` skill: is this job worth it, a tailored CV, a cover letter, form answers, messages and interview prep.
- **You decide and press Submit.** Nothing is ever submitted or sent for you.

> Apply better to fewer. Every fact comes from your own CV, and a check stops anything that doesn't.

## The flow

```
search / inbox / add  ->  live check  ->  evaluate (1-5)  ->  tailor CV + cover letter  ->  apply (you submit)
       |                                                                                       |
   digest.html  <------------------  tracker (stages, follow-ups, stats)  <-------------------+
```

| Part | What it does |
|---|---|
| **search** | Pulls jobs from public APIs: Remotive, Jobicy (including its per-country filter), RemoteOK, Arbeitnow, Himalayas, We Work Remotely, and the Greenhouse/Lever boards of companies you list (Coupang, Careem, Ninja Van, Deputy…). It keeps jobs in your regions, where "Remote" means open worldwide or to APAC. Then it applies your exclude list, blacklist and visa rules, scores each job 0–100 against your CV, and tracks it. |
| **add / inbox** | Jobs you find yourself on LinkedIn, Bayt, Seek, Naukrigulf or company sites. `add <url>` fetches the job description through the ATS API, the page's JobPosting data, or a browser. For LinkedIn, paste the description into a file with `--text-file`. To add several, drop URLs into `data/pipeline.md` and run `inbox`. |
| **live** | Checks postings are still open. Closed ones are marked `discarded`. |
| **evaluate** *(Claude Code)* | Writes `applications/<id>/report.md`. It covers: the role summary, a CV-vs-requirements table, gaps and how to address them honestly, level and positioning, pay against your targets, a tailoring plan, interview STAR stories, a posting check and keywords. It ends with a **1–5 rating and verdict**. It blocks on work authorization (no visa sponsorship) and on your dealbreakers. Below 4.0 it advises against applying. |
| **cv build** | Builds the PDF from `cv.yaml`, your single source of truth. The layout is single-column with standard headings, real text, no icons, no ligatures and no hyphenation. It then runs the ATS check automatically. |
| **tailor** *(Claude Code)* | Copies `cv.yaml` for one job and rewords it in the ad's language. A **fact check** blocks any number, employer, title, date or certification that isn't in your master CV. |
| **cover** *(Claude Code + `cover build`)* | A 250–350-word letter built from your real achievements. Numbers are fact-checked. |
| **answers / contact / interview** *(Claude Code)* | Draft form answers (with truthful work-authorization and salary answers), LinkedIn notes of 300 characters or less to the hiring manager, recruiter or a peer, and an interview prep sheet plus your STAR story bank. |
| **apply** | Opens each job in a real browser and autofills your details. It attaches the **tailored CV and cover letter for that job** if they exist. **You review and click Submit.** |
| **Visa & relocation** | Tags every ad: visa sponsorship, relocation support, open to relocating, or no sponsorship. The digest has its own section for these, with sponsorship searches per country. |
| **Tracker** | Stages are new, saved, evaluated, applied, responded, assessment, interview, offer, hired, rejected, discarded and skipped. Each job also stores its rating, report, CV and cover letter. |
| **followups** | Reminds you when to follow up: 7 days after applying (twice, then "cold"), 1 then every 3 days once they've responded or set an assessment, and a thank-you the day after an interview. |
| **stats** | Shows the funnel (evaluated, applied, responded, interview, offer) with response rates, plus applications by region and source. |
| **digest** | `data/digest.html`: your CV and its ATS score, your pipeline, visa jobs, and one section per region with LinkedIn, Indeed, Seek, Bayt, Naukrigulf, GulfTalent and other search links. |
| **cv-check / update-cv** | `cv-check` gives the ATS score and keyword gaps against your jobs. `update-cv` attaches the newest CV on each career site; you click Save. |

### What it will not do
- **Submit an application or send a message.** It drafts and fills; you press Submit and Send.
- **Invent anything.** Tailored CVs and letters can only reword `cv.yaml`, and the build refuses new facts.
- **Scrape LinkedIn or Indeed, or solve CAPTCHAs.** You log in once in the tool's browser (`data/browser-profile`) and it remembers you.

## Setup (Windows, Python 3.10+)

```powershell
cd job-hunter
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium      # only needed if you don't set browser.channel: chrome
copy config.example.yaml config.yaml     # search settings + autofill details
copy cv.example.yaml cv.yaml             # your master CV
copy profile.example.md profile.md       # target roles, regions, visa needs, dealbreakers, salary
python -m hunter cv build                # -> output\<Name>_<Role>_CV.pdf, set it as profile.resume
```

`config.yaml`, `cv.yaml`, `profile.md`, `story-bank.md`, `cv/`, `data/`, `output/` and `applications/` are git-ignored, so your personal data never reaches GitHub.

## Daily use

**In Claude Code, opened in this folder:**
```
/job-hunter scan                 # today's new jobs, closed postings dropped, follow-ups due
/job-hunter <paste a job URL>    # evaluate -> tailored CV -> cover letter -> answers
/job-hunter evaluate 62f55eab    # just the evaluation for a tracked job
/job-hunter followup             # draft today's follow-ups
/job-hunter interview 62f55eab   # interview prep + mock interview
/job-hunter patterns             # what's working, what to change
```

**In the terminal.** Run these with `.\.venv\Scripts\python.exe -m hunter …`, or activate `.venv` first and use `python -m hunter …`:
```powershell
python -m hunter search                  # fetch + score, opens data\digest.html
python -m hunter add <url>               # a job you found (LinkedIn: --text-file jd.txt)
python -m hunter inbox                   # every URL in data\pipeline.md
python -m hunter live                    # drop closed postings
python -m hunter list --region Australia --visa
python -m hunter apply 62f55eab          # guided apply with that job's tailored CV
python -m hunter mark 62f55eab applied   # then responded / assessment / interview / offer / rejected
python -m hunter followups               # who to nudge; --done <id> after you send it
python -m hunter stats                   # funnel + by region / source
python -m hunter cv build                # rebuild your master CV PDF
python -m hunter cv-check --job 62f55eab # ATS + keyword match for one job
python -m hunter update-cv               # attach the new CV on each career site
python -m hunter digest                  # rebuild the HTML page without fetching
```

During `apply`, at each job:
- **Enter**: autofill the current page. Click the site's *Apply* button first if the form is on the next page.
- **a**: mark the job applied after you submitted it. **s**: skip it. **l**: save it for later. **q**: quit.

## Run the search every morning (Task Scheduler)

```powershell
schtasks /Create /SC DAILY /ST 08:00 /TN "JobHunter" /TR "cmd /c cd /d D:\path\to\job-hunter && .venv\Scripts\python.exe -m hunter search"
```

## Tips
- The job APIs are mostly remote boards. For Dubai, New Zealand and Nepal, use the search links in the digest and put what you find in `data/pipeline.md`. You can also add companies hiring there to `greenhouse_boards` or `lever_companies`, using the slug after `boards.greenhouse.io/` or `jobs.lever.co/`.
- Fill in the salary table and dealbreakers in `profile.md`, so evaluations can judge pay and stop on your hard limits.
- Add companies you never want to see to `blacklist` in `config.yaml`.
- If a keyword returns no jobs, add synonyms such as `sysadmin`, `M365 administrator` or `site reliability`.
