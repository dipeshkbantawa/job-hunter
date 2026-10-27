"""Regions in priority order, and ready-made search URLs for sites that must not be scraped
(LinkedIn, Indeed, Google, Glassdoor, Seek, Bayt, ...). You open these in your own browser."""
import re
from urllib.parse import quote, quote_plus

ATS_SITES = ("site:boards.greenhouse.io OR site:job-boards.greenhouse.io OR site:jobs.lever.co OR "
             "site:jobs.ashbyhq.com OR site:apply.workable.com OR site:jobs.smartrecruiters.com OR "
             "site:wellfound.com")

# match: words that place a job in this region (checked against the job's location and title).
# jobicy: Jobicy geo filter for remote jobs open to that country.
# local: country job boards; {q} = url-encoded keyword, {slug} = keyword-as-slug.
REGIONS = {
    "remote": {
        "label": "Remote", "linkedin": "Worldwide", "indeed": "www.indeed.com", "jobicy": "apac",
        "match": [],  # special-cased in matches(): worldwide / anywhere / APAC / Asia remote
        "local": {},
    },
    "australia": {
        "label": "Australia", "linkedin": "Australia", "indeed": "au.indeed.com", "jobicy": "australia",
        "match": ["australia", "sydney", "melbourne", "brisbane", "perth", "adelaide", "canberra"],
        "local": {"Seek AU": "https://au.seek.com/{slug}-jobs/in-All-Australia"},
    },
    "new zealand": {
        "label": "New Zealand", "linkedin": "New Zealand", "indeed": "nz.indeed.com",
        "jobicy": "new-zealand",
        "match": ["new zealand", "auckland", "wellington", "christchurch", "hamilton nz"],
        "local": {"Seek NZ": "https://nz.seek.com/{slug}-jobs/in-All-New-Zealand"},
    },
    "south korea": {
        "label": "South Korea", "linkedin": "South Korea", "indeed": "kr.indeed.com",
        "jobicy": "south-korea",
        "match": ["south korea", "korea", "seoul", "busan", "pangyo", "seongnam", "incheon"],
        "local": {"JobKorea": "https://www.jobkorea.co.kr/Search/?stext={q}",
                  "Wanted": "https://www.wanted.co.kr/search?query={q}",
                  # Kowork (jobs for foreigners, E-7 visa sponsors) has no keyword URL, so go through Google
                  "Kowork": "https://www.google.com/search?q=site%3Akowork.kr+%22{q}%22"},
    },
    "dubai": {
        "label": "Dubai / UAE", "linkedin": "Dubai, United Arab Emirates", "indeed": "ae.indeed.com",
        "match": ["dubai", "uae", "united arab emirates", "abu dhabi", "sharjah"],
        "local": {"Bayt": "https://www.bayt.com/en/uae/jobs/{slug}-jobs-in-dubai/",
                  "Naukrigulf": "https://www.naukrigulf.com/{slug}-jobs-in-dubai",
                  # GulfTalent has no keyword URL (its search is a POST form), so go through Google
                  "GulfTalent": "https://www.google.com/search?q=site%3Agulftalent.com+%22{q}%22+UAE"},
    },
    "singapore": {
        "label": "Singapore", "linkedin": "Singapore", "indeed": "sg.indeed.com", "jobicy": "singapore",
        "match": ["singapore"],
        "local": {"MyCareersFuture": "https://www.mycareersfuture.gov.sg/search?search={q}",
                  "JobStreet SG": "https://sg.jobstreet.com/{slug}-jobs"},
    },
    "nepal": {
        "label": "Nepal", "linkedin": "Nepal", "indeed": None,
        "match": ["nepal", "kathmandu", "lalitpur", "pokhara", "bhaktapur"],
        "local": {"Merojob": "https://merojob.com/search?q={q}",
                  "Kumarijob": "https://www.kumarijob.com/search?keywords={q}"},
    },
}
ALIASES = {"uae": "dubai", "united arab emirates": "dubai", "korea": "south korea", "nz": "new zealand",
           "worldwide": "remote", "anywhere": "remote"}
WORLDWIDE = re.compile(r"anywhere|worldwide|world wide|global|international|apac|asia")


def region(name: str) -> dict:
    """Region definition by name; unknown names get a generic definition built from the name."""
    key = ALIASES.get(name.strip().lower(), name.strip().lower())
    return REGIONS.get(key) or {"label": name, "linkedin": name, "indeed": "www.indeed.com",
                                "match": [key], "local": {}}


def visa_links(keywords: list, name: str) -> dict:
    """Searches restricted to ads that mention visa sponsorship / relocation in one country."""
    r = region(name)
    place = r["linkedin"]
    anyof = " OR ".join(f'"{k}"' for k in keywords)
    boolean = f'({anyof}) AND ("visa sponsorship" OR "relocation")'
    links = {"LinkedIn": f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(boolean)}"
                         f"&location={quote_plus(place)}&f_TPR=r2592000"}
    if r["indeed"]:
        links["Indeed"] = (f"https://{r['indeed']}/jobs?q={quote_plus(f'({anyof}) visa sponsorship')}"
                           + ("&l=Dubai" if r["indeed"].startswith("ae.") else ""))
    links["Google"] = ("https://www.google.com/search?q="
                       + quote_plus(f'"visa sponsorship" ({anyof}) {place} jobs') + "&tbs=qdr:m")
    if "seek" in " ".join(r["local"]).lower():
        country = "All-Australia" if "au." in str(r["local"]) else "All-New-Zealand"
        host = "au.seek.com" if country == "All-Australia" else "nz.seek.com"
        links["Seek"] = f"https://{host}/visa-sponsorship-jobs/in-{country}"
    return links


def company_pages(cfg: dict, name: str) -> list:
    """Company career pages from config.yaml `company_careers`, keyed by region name or label."""
    pages = cfg.get("company_careers") or {}
    wanted = {name.strip().lower(), region(name)["label"].lower()}
    return [p for key, items in pages.items() if key.strip().lower() in wanted for p in items or []]


def matches(job, name: str) -> bool:
    r = region(name)
    loc = job.location.lower()
    if r["label"] == "Remote":
        # remote that is open to you: no country restriction, or worldwide / APAC / Asia
        bare = re.sub(r"[^a-z]", "", loc.replace("remote", ""))
        return job.remote and (bare == "" or WORLDWIDE.search(loc) is not None)
    where = f"{loc} {job.title.lower()}"
    return any(re.search(r"(?<![a-z])" + re.escape(m) + r"(?![a-z])", where) for m in r["match"])


def board_links(keyword: str, name: str = "Remote", max_age_days=7) -> dict:
    r = region(name)
    q, slug = quote_plus(keyword), keyword.lower().replace(" ", "-")
    seconds = max(1, max_age_days) * 86400
    fromage = next((d for d in (1, 3, 7, 14) if max_age_days <= d), 14)
    remote = r["label"] == "Remote"
    place = "remote" if remote else r["linkedin"]
    dork = f'"{keyword}" "{place}" ({ATS_SITES})'

    links = {"LinkedIn": f"https://www.linkedin.com/jobs/search/?keywords={q}&f_TPR=r{seconds}"
                         f"&location={quote_plus(r['linkedin'])}" + ("&geoId=92000000&f_WT=2" if remote else "")}
    if r["indeed"]:
        where = "Remote" if remote else ("Dubai" if r["indeed"].startswith("ae.") else "")
        links["Indeed"] = f"https://{r['indeed']}/jobs?q={q}&l={quote_plus(where)}&fromage={fromage}"
    links["Google Jobs"] = (f"https://www.google.com/search?q={quote_plus(f'{keyword} jobs {place}')}"
                            "&ibp=htl;jobs")
    links["Google (ATS boards)"] = f"https://www.google.com/search?q={quote_plus(dork)}&tbs=qdr:w"
    if remote:
        links["Wellfound"] = f"https://wellfound.com/role/r/{slug}"
        links["Glassdoor"] = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}&remoteWorkType=1"
    else:
        # Glassdoor's location filter needs internal ids, so search it through Google instead
        links["Glassdoor"] = ("https://www.google.com/search?q="
                              + quote_plus(f'site:glassdoor.com "{keyword}" jobs "{place}"'))
    for board, url in r["local"].items():
        links[board] = url.format(q=quote(keyword), slug=slug)
    return links
