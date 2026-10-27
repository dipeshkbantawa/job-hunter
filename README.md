# job-hunter

Takes the repetitive parts out of a job search across **Remote, Australia, New Zealand, South Korea, Dubai, Singapore and Nepal**, in that priority order (set `search.regions` in config.yaml).

| Step | What it does |
|---|---|
| **search** | Pulls jobs from public APIs (Remotive, Jobicy and its per-country filter, RemoteOK, Arbeitnow, Himalayas, We Work Remotely, plus the Greenhouse/Lever company boards you list, such as Coupang, Careem and Ninja Van, and optionally Google Programmable Search). Keeps only jobs in your regions ("Remote" means open worldwide/APAC/Asia, not US-only), filters them by your rules, scores them 0–100 against your skills and CV, and saves them in a local tracker. It also writes an HTML digest with a **Your CV** section (CV status plus every career site) and one section per region. |
| **links** | Builds search URLs per region: LinkedIn, Indeed (au/nz/kr/ae/sg), Google Jobs, Google "ATS boards" and Glassdoor, plus local boards: Seek (AU/NZ), JobKorea, Wanted, Bayt, MyCareersFuture, JobStreet, Merojob and Kumarijob. |
| **apply** | Opens your top matches one by one in a real browser, autofills name, email, phone, LinkedIn, GitHub and similar fields, and attaches your CV. **You review and click Submit.** |
| **update-cv** | Opens each career site's resume page (LinkedIn, Indeed, Glassdoor, Seek, Bayt, JobStreet, Wanted, Merojob…) and attaches your newest CV. You check it and click Save. |
| **cv-check** | Checks that your CV is ATS friendly by reading its text the way a parser does. It flags icon fonts that turn into junk, words that run together, hyphenation, missing contact details or sections, page count, images and tables, and the file name. It also compares your keywords with the jobs you're tracking (`--job <id>` for one job, `--region` for one region). |
| **list / mark / stats / export** | Tracks every job as new, saved, applied, interview, offer, rejected or skipped, so you never apply twice. |

### Why it doesn't auto-submit or scrape LinkedIn/Indeed
LinkedIn and Indeed forbid scraping and bot applications. They detect both and restrict or ban accounts, so the tool never fetches their pages and never clicks Submit. It also leaves CAPTCHAs to you. You log in yourself once, the browser profile in `data/browser-profile` remembers the session, and the tool does the typing.

## Setup (Windows, Python 3.10+)

```powershell
cd job-hunter
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium      # only needed if you don't set browser.channel: chrome
copy config.example.yaml config.yaml
mkdir cv                          # put your CV here, e.g. cv\My_CV.pdf
```

Edit `config.yaml` with your profile, keywords, skills and the path to your CV.

## Daily use

Run these with the project's Python: activate `.venv` first, or replace `python` with `.\.venv\Scripts\python.exe`.

```powershell
python -m hunter search                 # fetch + score, opens data\digest.html
python -m hunter links --region Australia --open   # LinkedIn / Indeed / Google Jobs for one region
python -m hunter list --region "South Korea"     # tracked jobs in one region
python -m hunter apply --top 10         # guided applying, top 10 by region priority then score
python -m hunter apply --region Singapore --top 5
python -m hunter apply 3fa9c1d2         # a specific job (id from list/digest)
python -m hunter mark 3fa9c1d2 interview --note "HR call Tue"
python -m hunter list --status applied
python -m hunter cv-check               # ATS check + keyword match vs your top jobs
python -m hunter cv-check --job 3fa9c1d2   # tailor your CV for one job
python -m hunter update-cv              # after you edit your CV
python -m hunter export                 # applications.csv
```

During `apply`, at each job:

- **Enter**: autofill the current page. Click the site's *Apply* button first if the form is on the next page.
- **a**: mark the job applied after you submitted it. **s**: skip it. **l**: save it for later. **q**: quit.

## Run the search every morning (Task Scheduler)

```powershell
schtasks /Create /SC DAILY /ST 08:00 /TN "JobHunter" /TR "cmd /c cd /d D:\path\to\job-hunter && .venv\Scripts\python.exe -m hunter search"
```

## Tips
- The job APIs are mostly remote boards. For Dubai, New Zealand and Nepal, use the search links in the digest, and add companies hiring there to `greenhouse_boards` or `lever_companies`. The slug is the part after `boards.greenhouse.io/` or `jobs.lever.co/`.
- If some keyword returns no jobs, add synonyms (for example `sysadmin`, `M365 administrator`, `site reliability`).
- `exclude` drops postings restricted to US citizens or that require clearance, so you don't waste applications.
- Raise `min_score` once the tracker fills up.
