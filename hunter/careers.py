"""Scan the career pages in config.yaml `company_careers` for roles matching your keywords.

For employers with no public ATS API. Reads the page's links (rendering it in a headless browser if the plain
page has none that fit), then fetches each matching posting. Logins and bot checks are never worked around:
a page that blocks us just yields nothing, and it stays as a link in the digest.
"""
import html
import re
import sys
from urllib.parse import urljoin, urlparse

import requests

from .jd import BROWSER_UA, _browser_html, fetch
from .matcher import relevant
from .sources import TIMEOUT, Job

MAX_POSTINGS_PER_PAGE = 30
ANCHOR = re.compile(r"<a\b[^>]*?href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
ATS_HOSTS = re.compile(r"greenhouse|lever\.co|ashbyhq|smartrecruiters|workable|myworkdayjobs|bamboohr")


def job_links(page_html: str, base: str, keywords: list) -> list:
    """Links on the page whose text or URL slug fits a keyword. Listing pages often say only 'View opportunity',
    so the slug counts too."""
    site = urlparse(base).netloc.split(".", 1)[-1]
    found = {}
    for href, text in ANCHOR.findall(page_html):
        url = urljoin(base, html.unescape(href)).split("#")[0]
        if not url.startswith("http") or url.rstrip("/") == base.rstrip("/"):
            continue
        u = urlparse(url)
        if not ATS_HOSTS.search(u.netloc) and site not in u.netloc:
            continue
        label = re.sub(r"<[^>]+>", " ", text)
        slug = re.sub(r"[^a-z0-9]+", " ", u.path.rsplit("/", 1)[-1].lower())
        if relevant(Job("careers", f"{label} {slug}", "", url), keywords):
            found[url] = True
    return list(found)


def scan(name: str, url: str, region: str, keywords: list, channel: str = "", known=lambda _id: False) -> list:
    links = []
    try:
        r = requests.get(url, headers=BROWSER_UA, timeout=TIMEOUT)
        links = job_links(r.text, url, keywords) if r.ok else []
    except Exception as e:
        print(f"  ! careers/{name}: {e}", file=sys.stderr)
    if not links:
        try:  # JavaScript-only listing, or a plain page that blocked us: render it once
            links = job_links(_browser_html(url, channel), url, keywords)
        except Exception as e:
            print(f"  ! careers/{name}: {e}", file=sys.stderr)
    jobs = []
    for link in links[:MAX_POSTINGS_PER_PAGE]:
        if known(Job("careers", "", "", link).id):
            continue
        p = fetch(link, channel)
        if p.live != "closed" and p.title:
            place = p.location or region
            if region.lower() not in place.lower():
                place = f"{place}, {region}"
            jobs.append(Job("careers", p.title, name, link, place, p.posted, [], p.text, "remote" in place.lower()))
    return jobs


def scan_all(cfg: dict, keywords: list, known=lambda _id: False) -> list:
    channel = (cfg.get("browser") or {}).get("channel", "")
    jobs = []
    for region, pages in (cfg.get("company_careers") or {}).items():
        for page in pages or []:
            found = scan(page["name"], page["url"], region, keywords, channel, known)
            print(f"  {'careers':<15} {page['name'][:30]:<30} {len(found)} new")
            jobs += found
    return jobs
