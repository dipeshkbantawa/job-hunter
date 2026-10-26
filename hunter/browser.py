"""Human-in-the-loop browser helper (Playwright).

- Uses a persistent browser profile, so you log in to LinkedIn/Indeed/etc. ONCE by hand
  and the session is reused next time.
- Autofills common application fields from your profile and attaches your CV.
- NEVER clicks Submit/Apply and never touches CAPTCHAs: you review and submit yourself.
"""
import re
from pathlib import Path

FIELD_RULES = [  # first match wins, so specific rules come before generic ones
    ("first_name", r"first.?name|given.?name|\bfname\b"),
    ("last_name", r"last.?name|family.?name|surname|\blname\b"),
    ("email", r"e-?mail"),
    ("phone", r"phone|mobile|\btel\b"),
    ("linkedin", r"linked.?in"),
    ("github", r"github"),
    ("website", r"website|portfolio|personal.?(site|url)|blog"),
    ("current_company", r"current.?(company|employer)|\bemployer\b|company.?name|organi[sz]ation"),
    ("current_title", r"current.?(title|role|position)|job.?title|headline"),
    ("years_experience", r"years.?(of.?)?experience|total.?experience"),
    ("notice_period", r"notice"),
    ("salary_expectation", r"salary|compensation|\bctc\b|expected.?pay"),
    ("location", r"location|\bcity\b|where.*based|current.?address"),
    ("full_name", r"full.?name|\bname\b"),
]

DESCRIBE_JS = """el => {
  const parts = [el.name, el.id, el.placeholder, el.getAttribute('aria-label'), el.getAttribute('autocomplete')];
  if (el.labels) for (const l of el.labels) parts.push(l.innerText);
  const lb = el.getAttribute('aria-labelledby');
  if (lb) lb.split(/\\s+/).forEach(id => { const n = document.getElementById(id); if (n) parts.push(n.innerText); });
  return parts.filter(Boolean).join(' | ').toLowerCase();
}"""


def _profile_values(profile: dict) -> dict:
    v = {k: str(val) for k, val in profile.items() if val not in (None, "")}
    if "full_name" not in v and ("first_name" in v or "last_name" in v):
        v["full_name"] = f"{v.get('first_name', '')} {v.get('last_name', '')}".strip()
    return v


def autofill(page, profile: dict, resume: Path = None, cover: Path = None) -> int:
    """Fill empty text fields and file inputs across all frames. Returns number of fields touched."""
    values = _profile_values(profile)
    filled = 0
    for frame in page.frames:
        try:
            fields = frame.locator("input, textarea").all()
        except Exception:
            continue
        file_inputs = []
        for el in fields:
            try:
                kind = (el.get_attribute("type") or "text").lower()
                if kind == "file":
                    file_inputs.append(el)
                    continue
                if kind in ("hidden", "submit", "button", "checkbox", "radio", "password", "search") \
                        or not el.is_visible() or not el.is_editable() or el.input_value():
                    continue
                desc = el.evaluate(DESCRIBE_JS)
                for key, rx in FIELD_RULES:
                    if re.search(rx, desc) and key in values:
                        el.fill(values[key])
                        filled += 1
                        break
            except Exception:
                continue
        for el in file_inputs:
            try:
                desc = el.evaluate(DESCRIBE_JS)
                if cover and re.search(r"cover", desc):
                    el.set_input_files(str(cover))
                elif resume and (re.search(r"resume|\bcv\b|curriculum", desc) or len(file_inputs) == 1):
                    el.set_input_files(str(resume))
                else:
                    continue
                filled += 1
            except Exception:
                continue
    return filled


def _context(p, cfg):
    opts = cfg.get("browser") or {}
    profile_dir = cfg["_root"] / "data" / "browser-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    kwargs = {"headless": False, "viewport": None, "args": ["--start-maximized"]}
    if opts.get("channel"):          # "chrome" or "msedge" = use your installed browser
        kwargs["channel"] = opts["channel"]
    return p.chromium.launch_persistent_context(str(profile_dir), **kwargs)


def _active_page(ctx):
    return ctx.pages[-1]


def apply_queue(cfg, rows, tracker, resume: Path, cover: Path = None):
    from playwright.sync_api import sync_playwright
    profile = cfg.get("profile") or {}
    with sync_playwright() as p:
        ctx = _context(p, cfg)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for i, row in enumerate(rows, 1):
            print(f"\n[{i}/{len(rows)}] {row['title']} @ {row['company']}  (score {row['score']})\n    {row['url']}")
            try:
                page.goto(row["url"], wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"    ! could not open: {e}")
            print("    Click 'Apply' / log in if needed, then use the prompt below. I never submit for you.")
            while True:
                choice = input("    [Enter]=autofill  a=mark applied  s=skip  l=later  q=quit > ").strip().lower()
                if choice == "":
                    n = autofill(_active_page(ctx), profile, resume, cover)
                    print(f"    filled {n} field(s). Review every answer, complete the rest, then SUBMIT yourself.")
                elif choice == "a":
                    tracker.set_status(row["id"], "applied")
                    print("    marked applied")
                    break
                elif choice == "s":
                    tracker.set_status(row["id"], "skipped")
                    break
                elif choice == "l":
                    tracker.set_status(row["id"], "saved")
                    break
                elif choice == "q":
                    ctx.close()
                    return
        ctx.close()


def update_cv_sites(cfg, resume: Path):
    """Open each career site's profile/resume page and attach the latest CV for you to save."""
    from playwright.sync_api import sync_playwright
    sites = cfg.get("career_sites") or []
    if not sites:
        raise SystemExit("No career_sites in config.yaml")
    with sync_playwright() as p:
        ctx = _context(p, cfg)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for site in sites:
            print(f"\n== {site['name']}: {site['url']}")
            try:
                page.goto(site["url"], wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"   ! could not open: {e}")
            print("   Log in if asked (first time only), open the resume/CV upload section.")
            while True:
                choice = input("   [Enter]=attach CV to upload field  n=next site  q=quit > ").strip().lower()
                if choice == "":
                    n = 0
                    for frame in _active_page(ctx).frames:
                        for el in frame.locator("input[type=file]").all():
                            try:
                                el.set_input_files(str(resume))
                                n += 1
                            except Exception:
                                pass
                    print(f"   attached to {n} upload field(s)." if n else
                          "   no upload field found here - click the site's 'Upload/Replace resume' button, then retry.")
                    if n:
                        print("   Check the preview and click the site's Save button yourself.")
                elif choice == "n":
                    break
                elif choice == "q":
                    ctx.close()
                    return
        ctx.close()
