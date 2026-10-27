"""Fetch a job description from a URL and decide whether the posting is still live.

Order: the ATS's public API (Greenhouse, Lever, Ashby) -> schema.org JobPosting JSON-LD that most
boards embed (Bayt, Naukrigulf, Seek, JobStreet, company sites...) -> readable page text ->
a headless browser for JavaScript-only pages. LinkedIn usually needs you to be logged in, so for
LinkedIn the reliable path is pasting the JD text (`add <url> --text-file jd.txt`).
"""
import html
import json
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

import requests

from .sources import HEADERS, TIMEOUT, strip_html, to_date

BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/130.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
CLOSED = re.compile(
    r"no longer (?:accepting applications|available|open|active)|position (?:has been|is) (?:filled|closed)"
    r"|job (?:has )?expired|this (?:job|posting|vacancy|position) (?:is|has been) (?:closed|removed|filled)"
    r"|applications? (?:are|is) (?:now )?closed|job not found|page not found|vacancy (?:has )?expired", re.I)


@dataclass
class Posting:
    url: str
    title: str = ""
    company: str = ""
    location: str = ""
    text: str = ""
    posted: str = ""
    live: str = "unknown"     # live / closed / unknown
    reason: str = ""


def _ats_api(url: str, gh_board: str = ""):
    u = urlparse(url)
    parts = [p for p in u.path.split("/") if p]
    try:
        gh_jid = re.search(r"gh_jid=(\d+)", u.query)
        if gh_jid and gh_board:  # Greenhouse job shown on the company's own careers domain
            parts, u = [gh_board, "jobs", gh_jid.group(1)], urlparse("https://boards.greenhouse.io")
        if "greenhouse.io" in u.netloc and "jobs" in parts:
            board = parts[0] if parts[0] != "embed" else re.search(r"for=([\w-]+)", u.query).group(1)
            job_id = parts[parts.index("jobs") + 1]
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}", headers=HEADERS,
                             timeout=TIMEOUT)
            if r.status_code == 404:
                return Posting(url, live="closed", reason="Greenhouse says the job no longer exists")
            j = r.json()
            return Posting(url, j.get("title", ""), board, (j.get("location") or {}).get("name", ""),
                           strip_html(j.get("content")), to_date(j.get("updated_at")), "live", "Greenhouse API")
        if u.netloc == "jobs.lever.co" and len(parts) >= 2:
            r = requests.get(f"https://api.lever.co/v0/postings/{parts[0]}/{parts[1]}", headers=HEADERS,
                             timeout=TIMEOUT)
            if r.status_code == 404:
                return Posting(url, live="closed", reason="Lever says the job no longer exists")
            j = r.json()
            return Posting(url, j.get("text", ""), parts[0], (j.get("categories") or {}).get("location", ""),
                           j.get("descriptionPlain", "") + "\n" + "\n".join(
                               strip_html(l.get("content")) for l in j.get("lists") or []),
                           to_date(j.get("createdAt")), "live", "Lever API")
        if u.netloc == "jobs.ashbyhq.com" and len(parts) >= 2:
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{parts[0]}", headers=HEADERS,
                             timeout=TIMEOUT)
            for j in r.json().get("jobs", []):
                if j.get("id") == parts[1]:
                    return Posting(url, j.get("title", ""), parts[0], j.get("location", ""),
                                   j.get("descriptionPlain") or strip_html(j.get("descriptionHtml")),
                                   to_date(j.get("publishedAt")), "live", "Ashby API")
            return Posting(url, live="closed", reason="not on the company's Ashby board any more")
    except Exception:
        return None
    return None


def _jsonld(page: str):
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(html.unescape(block.strip()))
        except Exception:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for it in items:
            if isinstance(it, dict) and "JobPosting" in str(it.get("@type")):
                org = it.get("hiringOrganization") or {}
                loc = it.get("jobLocation") or {}
                loc = loc[0] if isinstance(loc, list) and loc else loc
                addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
                place = ", ".join(str(addr.get(k)) for k in ("addressLocality", "addressRegion", "addressCountry")
                                  if isinstance(addr, dict) and addr.get(k) and isinstance(addr.get(k), str))
                if it.get("jobLocationType") == "TELECOMMUTE":
                    place = (place + " (Remote)").strip()
                return it, (org.get("name") if isinstance(org, dict) else str(org)), place
    return None, "", ""


def _page_text(page: str) -> str:
    page = re.sub(r"<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    m = re.search(r"<(main|article)[^>]*>(.*?)</\1>", page, re.S | re.I)
    return strip_html(m.group(2) if m else page)


def _browser_html(url: str, channel: str = "") -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel=channel) if channel else p.chromium.launch()
        pg = b.new_page()
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(2500)
        content = pg.content()
        b.close()
    return content


def fetch(url: str, channel: str = "", gh_board: str = "") -> Posting:
    api = _ats_api(url, gh_board)
    if api:
        return api
    page, status = "", 0
    try:
        r = requests.get(url, headers=BROWSER_UA, timeout=TIMEOUT, allow_redirects=True)
        status, page = r.status_code, r.text
        if status in (404, 410):
            return Posting(url, live="closed", reason=f"HTTP {status}")
    except Exception as e:
        status = -1
    if status != 200 or len(_page_text(page)) < 400:
        try:  # blocked or JavaScript-only page: render it
            page = _browser_html(url, channel)
        except Exception as e:
            return Posting(url, live="unknown", reason=f"could not load the page ({type(e).__name__}); "
                                                         "paste the JD with --text-file")
    post, company, place = _jsonld(page)
    title_tag = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    p = Posting(url, title=strip_html(title_tag.group(1)) if title_tag else "")
    if post:
        p.title, p.company, p.location = strip_html(post.get("title")), company or "", place
        p.text = strip_html(post.get("description"))
        p.posted = to_date(post.get("datePosted"))
        until = to_date(post.get("validThrough"))
        if until and until < date.today().isoformat():
            p.live, p.reason = "closed", f"validThrough {until} has passed"
            return p
    if not p.text:
        p.text = _page_text(page)
    if "linkedin.com" in url and ("authwall" in page or "Sign in" in p.title) and len(p.text) < 800:
        p.live, p.reason = "unknown", "LinkedIn needs a login; paste the JD with --text-file"
    elif CLOSED.search(p.text[:3000]) and len(p.text) < 2500:
        p.live, p.reason = "closed", f"page says: {CLOSED.search(p.text[:3000]).group(0)}"
    elif len(p.text) >= 400:
        p.live, p.reason = "live", "job description present"
    else:
        p.live, p.reason = "unknown", "page has too little text to judge"
    return p
