"""Ready-made search URLs for sites that must not be scraped (LinkedIn, Indeed, Google)."""
from urllib.parse import quote_plus

ATS_SITES = ("site:boards.greenhouse.io OR site:job-boards.greenhouse.io OR site:jobs.lever.co OR "
             "site:jobs.ashbyhq.com OR site:apply.workable.com OR site:jobs.smartrecruiters.com OR "
             "site:wellfound.com")


def board_links(keyword: str, remote=True, max_age_days=7, location="") -> dict:
    q = quote_plus(keyword)
    seconds = max(1, max_age_days) * 86400
    fromage = next((d for d in (1, 3, 7, 14) if max_age_days <= d), 14)
    where = "Remote" if remote else location
    dork = f'"{keyword}" {"remote" if remote else location} ({ATS_SITES})'
    return {
        "LinkedIn": (f"https://www.linkedin.com/jobs/search/?keywords={q}&f_TPR=r{seconds}"
                     + ("&f_WT=2" if remote else f"&location={quote_plus(location)}")),
        "Indeed": f"https://www.indeed.com/jobs?q={q}&l={quote_plus(where)}&fromage={fromage}",
        "Google Jobs": f"https://www.google.com/search?q={quote_plus(keyword + ' ' + where + ' jobs')}&ibp=htl;jobs",
        "Google (ATS boards)": f"https://www.google.com/search?q={quote_plus(dork)}&tbs=qdr:w",
        "Wellfound": f"https://wellfound.com/role/{'r/' if remote else ''}{keyword.lower().replace(' ', '-')}",
        "Glassdoor": f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}&remoteWorkType=1",
    }
