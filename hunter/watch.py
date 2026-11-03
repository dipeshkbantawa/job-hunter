"""Watch employers' vacancy pages and notify you when a new notice appears.

For employers who post notices on their own site rather than on a job board, such as Nepal Telecom. Each watch
entry can have `pages` that are always read, and `url_templates` that are tried for the previous, current and next
Nepali fiscal year (`{fy}` = 2083-84, `{fy_long}` = 2083-2084), since the post for a new year doesn't exist until it
is published. Addresses can change between years ({fy_compact} = 208384 is also available), so also list a page that
links to each year's post and set `follow: true` to read the linked posts. The first run only records what is there.
After that, anything new triggers a notification.

It sees that a notice appeared, not its deadline: those are usually inside scanned PDFs, so open the notice to check.
"""
import html
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

import requests

from .jd import BROWSER_UA
from .sources import TIMEOUT

NUXT_FILE = re.compile(r'title:"([^"]{1,300})",file:"(https?://[^"]+?\.pdf)"', re.I)  # PDFs in the page's data
ANCHOR = re.compile(r"<a\b[^>]*?href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
DEFAULT_MATCH = r"vacanc|recruit|दरखास्त|रिक्त|पदपूर्ति|विज्ञापन"
DEFAULT_EXCLUDE = r"promotion|बढुवा|result|syllabus|interview|applicants"
TOAST_APP = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
TOAST_SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$esc = { param($s) [System.Security.SecurityElement]::Escape($s) }
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast activationType="protocol" launch="' + (& $esc $env:HUNTER_TOAST_URL) + '"><visual><binding template="ToastGeneric"><text>' +
    (& $esc $env:HUNTER_TOAST_TITLE) + '</text><text>' + (& $esc $env:HUNTER_TOAST_BODY) + '</text></binding></visual></toast>')
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:HUNTER_TOAST_APP).Show(
    (New-Object Windows.UI.Notifications.ToastNotification $xml))
"""


def fiscal_years(today=None) -> list:
    """Previous, current and next Nepali fiscal year as start years. The year starts around 16 July (1 Shrawan)."""
    today = today or date.today()
    current = today.year + (57 if (today.month, today.day) >= (7, 16) else 56)
    return [current - 1, current, current + 1]


def fill_template(template: str, start_year: int) -> str:
    end = start_year + 1
    return (template.replace("{fy_compact}", f"{start_year}{end % 100:02d}").replace("{fy_long}", f"{start_year}-{end}")
            .replace("{fy}", f"{start_year}-{end % 100:02d}"))


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def find_notices(page: str, base: str, match: str = DEFAULT_MATCH, exclude: str = DEFAULT_EXCLUDE) -> dict:
    """{url: title} of the links and PDFs on a page that look like vacancy notices."""
    text = page.replace("\\u002F", "/")
    found = {}
    for title, url in NUXT_FILE.findall(text):
        found[url] = _clean(title.encode().decode("unicode_escape", "ignore") if "\\u" in title else title)
    for href, label in ANCHOR.findall(text):
        url = urljoin(base, html.unescape(href))
        if url.startswith("http"):
            found.setdefault(url, _clean(label))
    return {_same_form(url): title for url, title in found.items()
            if re.search(match, f"{title} {url}", re.I) and not re.search(exclude, f"{title} {url}", re.I)}


def _same_form(url: str) -> str:
    """The same post can be linked as http and https, or with a trailing slash."""
    return re.sub(r"^http://", "https://", url).rstrip("/")


def _page_title(page: str, url: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    return _clean(m.group(1)) if m else urlparse(url).path.rsplit("/", 1)[-1]


def scan_entry(entry: dict, today=None) -> tuple:
    """Returns ({url: title}, failures). A template address that isn't there yet is normal, not a failure."""
    match, exclude = entry.get("match", DEFAULT_MATCH), entry.get("exclude", DEFAULT_EXCLUDE)
    found, failures = {}, []
    guesses = [fill_template(t, y) for t in entry.get("url_templates") or [] for y in fiscal_years(today)]
    pages = list(entry.get("pages") or [])
    read = set()

    def read_page(url, must_exist):
        read.add(_same_form(url))
        try:
            r = requests.get(url, headers=BROWSER_UA, timeout=TIMEOUT)
        except requests.RequestException as e:
            failures.append(f"{url}: {e}")
            return None
        if not r.ok:
            if must_exist:
                failures.append(f"{url}: HTTP {r.status_code}")
            return None
        return r.text

    for url in pages + guesses:
        text = read_page(url, url in pages)
        if text is None:
            continue
        if url in guesses:
            found[_same_form(url)] = _page_title(text, url)
        found.update(find_notices(text, url, match, exclude))
    if entry.get("follow"):
        home = {urlparse(p).netloc for p in pages + guesses}
        for url in [u for u in found if urlparse(u).netloc in home and not u.lower().endswith(".pdf") and u not in read]:
            text = read_page(url, False)  # a link in a side menu may be dead; that isn't a failed check
            if text is not None:
                found.update(find_notices(text, url, match, exclude))
    return found, failures


def notify_desktop(title: str, body: str, url: str) -> bool:
    """Windows notification. The text comes from web pages, so it reaches PowerShell only through variables."""
    env = dict(os.environ, HUNTER_TOAST_TITLE=title, HUNTER_TOAST_BODY=body[:300], HUNTER_TOAST_URL=url,
               HUNTER_TOAST_APP=TOAST_APP)
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", TOAST_SCRIPT], env=env,
                       capture_output=True, text=True, timeout=60)
    if r.returncode or r.stderr.strip():
        print(f"  ! desktop notification failed: {r.stderr.strip()[:300]}", file=sys.stderr)
        return False
    return True


def notify_phone(topic: str, title: str, body: str, url: str) -> bool:
    """Optional push through ntfy.sh. Anyone who knows the topic name can read it, so use a hard-to-guess name."""
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=f"{title}\n{body}".encode(),
                      headers={"Title": "Job vacancy notice", "Click": url}, timeout=TIMEOUT).raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"  ! phone notification failed: {e}", file=sys.stderr)
        return False


def send(cfg: dict, title: str, body: str, url: str):
    options = (cfg.get("watch") or {}).get("notify") or {}
    if options.get("desktop", True):
        notify_desktop(title, body, url)
    if options.get("ntfy_topic"):
        notify_phone(options["ntfy_topic"], title, body, url)


def run(cfg: dict, notify: bool = True) -> int:
    """Check every watch entry and return how many new notices were found."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Nepali titles must not crash a redirected run
    state_path = cfg["_root"] / "data" / "watch.json"
    log_path = cfg["_root"] / "data" / "watch.log"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    entries = (cfg.get("watch") or {}).get("employers") or []
    if not entries:
        raise SystemExit("No employers under watch: in config.yaml. See config.example.yaml.")
    stamp = datetime.now().isoformat(timespec="seconds")
    total_new = 0
    for entry in entries:
        name = entry["name"]
        found, failures = scan_entry(entry)
        for failure in failures:
            print(f"  ! {name}: {failure}", file=sys.stderr)
        known = state.get(name)
        if known is None and (failures or not found):
            print(f"{name}: could not read the first time; nothing recorded")  # never baseline a failed read
            continue
        first_run = known is None
        known = known or {}
        new = {url: title for url, title in found.items() if url not in known}
        for url, title in new.items():
            known[url] = {"title": title, "first_seen": stamp}
        state[name] = known
        if first_run:
            print(f"{name}: first check, recorded {len(new)} existing notice(s)")
            continue
        print(f"{name}: {len(new)} new, {len(known)} known")
        for url, title in new.items():
            total_new += 1
            print(f"  NEW  {title}\n       {url}")
            with log_path.open("a", encoding="utf-8") as log:
                log.write(f"{stamp}\t{name}\t{title}\t{url}\n")
            if notify:
                send(cfg, f"New vacancy notice: {name}", f"{title}. Open it to check the deadline.", url)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return total_new
