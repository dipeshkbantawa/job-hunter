"""Job sources: public JSON APIs / RSS feeds that allow programmatic access.

LinkedIn and Indeed are NOT scraped here (their terms forbid it and they block
bots quickly). For those, see links.py which builds ready-made search URLs.
"""
import hashlib
import html
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

from .links import region

HEADERS = {"User-Agent": "Mozilla/5.0 (personal job-hunter script)"}
TIMEOUT = 25
COMPANIES_FILE = Path(__file__).resolve().parent.parent / "companies.yaml"


@dataclass
class Job:
    source: str
    title: str
    company: str
    url: str
    location: str = ""
    posted: str = ""          # YYYY-MM-DD
    tags: list = field(default_factory=list)
    description: str = ""
    remote: bool = True

    @property
    def id(self) -> str:
        return hashlib.sha1(self.url.strip().lower().encode()).hexdigest()[:16]

    @property
    def text(self) -> str:
        return " ".join([self.title, " ".join(self.tags), self.description]).lower()


def strip_html(s) -> str:
    s = html.unescape(str(s or ""))
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def to_date(v) -> str:
    if v in (None, ""):
        return ""
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            ts = float(v)
            ts = ts / 1000 if ts > 1e11 else ts   # milliseconds -> seconds
            return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
        s = str(v).strip()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return parsedate_to_datetime(s).date().isoformat()
    except Exception:
        return ""


def _get(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def _is_remote(*parts) -> bool:
    return any("remote" in str(p).lower() or "anywhere" in str(p).lower() for p in parts)


# --- keyword-searchable APIs -------------------------------------------------

def remotive(keyword):
    data = _get("https://remotive.com/api/remote-jobs", {"search": keyword, "limit": 100}).json()
    for j in data.get("jobs", []):
        yield Job("remotive", j.get("title", ""), j.get("company_name", ""), j.get("url", ""),
                  j.get("candidate_required_location", ""), to_date(j.get("publication_date")),
                  j.get("tags") or [], strip_html(j.get("description")))


def _jobicy_jobs(data):
    for j in data.get("jobs", []) or []:
        yield Job("jobicy", strip_html(j.get("jobTitle")), j.get("companyName", ""), j.get("url", ""),
                  j.get("jobGeo", ""), to_date(j.get("pubDate")),
                  j.get("jobIndustry") or [], strip_html(j.get("jobDescription") or j.get("jobExcerpt")))


def jobicy(keyword):
    yield from _jobicy_jobs(_get("https://jobicy.com/api/v2/remote-jobs", {"count": 50, "tag": keyword}).json())


def jobicy_geo(geo):
    """Remote jobs open to residents of a country/region (Jobicy's geo filter, e.g. australia, apac)."""
    yield from _jobicy_jobs(_get("https://jobicy.com/api/v2/remote-jobs", {"count": 100, "geo": geo}).json())


def google_cse(keyword, api_key, cx, max_age_days=7):
    """Google Programmable Search over ATS job boards (needs your own API key + cx)."""
    q = (f'"{keyword}" remote (site:boards.greenhouse.io OR site:jobs.lever.co OR '
         f'site:jobs.ashbyhq.com OR site:apply.workable.com OR site:jobs.smartrecruiters.com)')
    for start in (1, 11):
        data = _get("https://www.googleapis.com/customsearch/v1",
                    {"key": api_key, "cx": cx, "q": q, "start": start,
                     "dateRestrict": f"d{max_age_days}"}).json()
        for it in data.get("items", []):
            link = it.get("link", "")
            path = urlparse(link).path.strip("/").split("/")
            company = path[0] if path and path[0] else urlparse(link).netloc
            yield Job("google", it.get("title", ""), company, link, "Remote", "",
                      [], it.get("snippet", ""))


# --- whole-feed APIs (fetched once per run, filtered locally) ----------------

@lru_cache(maxsize=None)
def _remoteok_raw():
    return _get("https://remoteok.com/api").json()


def remoteok(_keyword=None):
    for j in _remoteok_raw():
        if not isinstance(j, dict) or "position" not in j:
            continue  # first element is a legal notice
        yield Job("remoteok", j.get("position", ""), j.get("company", ""),
                  j.get("url") or j.get("apply_url", ""), j.get("location") or "Remote",
                  to_date(j.get("date") or j.get("epoch")), j.get("tags") or [],
                  strip_html(j.get("description")))


@lru_cache(maxsize=None)
def _arbeitnow_raw():
    return _get("https://www.arbeitnow.com/api/job-board-api").json().get("data", [])


def arbeitnow(_keyword=None):
    for j in _arbeitnow_raw():
        yield Job("arbeitnow", j.get("title", ""), j.get("company_name", ""), j.get("url", ""),
                  j.get("location", ""), to_date(j.get("created_at")), j.get("tags") or [],
                  strip_html(j.get("description")), bool(j.get("remote")))


@lru_cache(maxsize=None)
def _himalayas_raw():
    return _get("https://himalayas.app/jobs/api", {"limit": 100}).json().get("jobs", [])


def himalayas(_keyword=None):
    for j in _himalayas_raw():
        loc = j.get("locationRestrictions") or []
        yield Job("himalayas", j.get("title", ""), j.get("companyName", ""),
                  j.get("applicationLink") or j.get("guid", ""),
                  ", ".join(loc) if isinstance(loc, list) else str(loc) or "Remote",
                  to_date(j.get("pubDate")), j.get("categories") or [],
                  strip_html(j.get("description") or j.get("excerpt")))


@lru_cache(maxsize=None)
def _wwr_raw():
    return _get("https://weworkremotely.com/remote-jobs.rss").content


def weworkremotely(_keyword=None):
    root = ET.fromstring(_wwr_raw())
    for item in root.iter("item"):
        raw_title = item.findtext("title", "")
        company, _, title = raw_title.partition(": ")
        if not title:
            company, title = "", raw_title
        yield Job("weworkremotely", title, company, item.findtext("link", ""),
                  item.findtext("region", "") or "Remote", to_date(item.findtext("pubDate")),
                  [item.findtext("category", "")], strip_html(item.findtext("description")))


# --- company career boards (public ATS APIs) ---------------------------------

def greenhouse(board):
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", {"content": "true"}).json()
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        yield Job("greenhouse", j.get("title", ""), board, j.get("absolute_url", ""), loc,
                  to_date(j.get("first_published") or j.get("updated_at")), [], strip_html(j.get("content")),
                  _is_remote(loc, j.get("title")))


def lever(company):
    for j in _get(f"https://api.lever.co/v0/postings/{company}", {"mode": "json"}).json():
        cats = j.get("categories") or {}
        loc = cats.get("location", "")
        yield Job("lever", j.get("text", ""), company, j.get("hostedUrl", ""), loc,
                  to_date(j.get("createdAt")), [cats.get("team", ""), cats.get("commitment", "")],
                  j.get("descriptionPlain", ""), _is_remote(loc, j.get("workplaceType")))


def ashby(company):
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{company}").json()
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        others = [o.get("location", "") for o in j.get("secondaryLocations") or []]
        loc = ", ".join(filter(None, [j.get("location", "")] + others))
        yield Job("ashby", j.get("title", "").strip(), company, j.get("jobUrl", ""), loc, to_date(j.get("publishedAt")),
                  [j.get("department", ""), j.get("team", "")], j.get("descriptionPlain", ""),
                  bool(j.get("isRemote")) or _is_remote(loc))


def smartrecruiters(company, keywords=()):
    """The list has no descriptions and big employers post thousands of jobs, so search by keyword and
    fetch the details of the hits only."""
    base = f"https://api.smartrecruiters.com/v1/companies/{company}/postings"
    seen = {}
    for kw in keywords:
        for j in _get(base, {"q": kw, "limit": 100}).json().get("content", []):
            seen[j["id"]] = j
    for jid, j in seen.items():
        d = _get(f"{base}/{jid}").json()
        sections = (d.get("jobAd") or {}).get("sections") or {}
        text = " ".join(strip_html((sections.get(k) or {}).get("text"))
                        for k in ("jobDescription", "qualifications", "additionalInformation"))
        where = j.get("location") or {}
        loc = where.get("fullLocation") or where.get("city") or ""
        yield Job("smartrecruiters", j.get("name", ""), company,
                  d.get("postingUrl") or f"https://jobs.smartrecruiters.com/{company}/{jid}", loc,
                  to_date(j.get("releasedDate")), [], text, bool(where.get("remote")) or _is_remote(loc))


KEYWORD_SOURCES = {"remotive": remotive, "jobicy": jobicy}
FEED_SOURCES = {"remoteok": remoteok, "arbeitnow": arbeitnow,
                "himalayas": himalayas, "weworkremotely": weworkremotely}


def _safe(label, gen):
    try:
        return list(gen)
    except Exception as e:  # one broken source must not kill the run
        print(f"  ! {label}: {e}", file=sys.stderr)
        return []


def company_boards(search: dict) -> dict:
    """{ats: [slugs]} from companies.yaml plus the lists in config.yaml."""
    listed = yaml.safe_load(COMPANIES_FILE.read_text(encoding="utf-8")) if COMPANIES_FILE.exists() else {}
    own = {"greenhouse": "greenhouse_boards", "lever": "lever_companies", "ashby": "ashby_companies",
           "smartrecruiters": "smartrecruiters_companies"}
    return {ats: list(dict.fromkeys((listed or {}).get(ats, []) + (search.get(key) or [])))
            for ats, key in own.items()}


def _board_jobs(ats, slug, keywords):
    if ats == "smartrecruiters":
        return _safe(f"{ats}/{slug}", smartrecruiters(slug, keywords))
    return _safe(f"{ats}/{slug}", {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}[ats](slug))


def collect(search: dict) -> list:
    keywords = search.get("keywords") or []
    boards = company_boards(search)
    enabled = set(search.get("sources") or list(KEYWORD_SOURCES) + list(FEED_SOURCES) + list(boards))
    jobs = []

    for name, fn in KEYWORD_SOURCES.items():
        if name in enabled:
            for kw in keywords:
                found = _safe(f"{name} '{kw}'", fn(kw))
                print(f"  {name:<15} {kw!r:<30} {len(found)}")
                jobs += found

    if "jobicy" in enabled:
        geos = dict.fromkeys(region(r).get("jobicy") for r in search.get("regions") or [])
        for geo in filter(None, geos):
            found = _safe(f"jobicy geo={geo}", jobicy_geo(geo))
            print(f"  {'jobicy':<15} {'geo=' + geo:<30} {len(found)}")
            jobs += found

    for name, fn in FEED_SOURCES.items():
        if name in enabled:
            found = _safe(name, fn())
            print(f"  {name:<15} {'(full feed)':<30} {len(found)}")
            jobs += found

    for ats, slugs in boards.items():
        if ats in enabled and slugs:
            with ThreadPoolExecutor(8) as pool:
                found = [j for batch in pool.map(lambda s: _board_jobs(ats, s, keywords), slugs) for j in batch]
            print(f"  {ats:<15} {str(len(slugs)) + ' companies':<30} {len(found)}")
            jobs += found

    cse = search.get("google_cse") or {}
    if cse.get("api_key") and cse.get("cx"):
        for kw in keywords:
            found = _safe(f"google '{kw}'", google_cse(kw, cse["api_key"], cse["cx"],
                                                       search.get("max_age_days", 7)))
            print(f"  {'google':<15} {kw!r:<30} {len(found)}")
            jobs += found

    unique = {}
    for j in jobs:
        if j.url and j.title:
            unique.setdefault(j.id, j)
    return list(unique.values())
