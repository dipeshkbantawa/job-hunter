"""Human-in-the-loop browser helper (Playwright).

- Uses a persistent browser profile, so you log in to LinkedIn/Indeed/etc. ONCE by hand
  and the session is reused next time.
- Autofills common application fields from your profile and attaches your CV.
- Fills long questions ("Why this company?") from the job's answers.md, drafted and reviewed beforehand.
- Lists what it left empty, so you can answer it before submitting.
- NEVER clicks Submit/Apply and never touches CAPTCHAs: you review and submit yourself.
- Does not autofill on LinkedIn, Indeed or Glassdoor, whose terms forbid automation: those you do by hand.
"""
import re
from pathlib import Path
from urllib.parse import urlparse

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


LABEL_JS = """el => {
  const clean = t => (t || '').replace(/\\s+/g, ' ').trim();
  if (el.labels && el.labels.length) return clean(el.labels[0].innerText);
  const prev = el.previousElementSibling || (el.parentElement && el.parentElement.previousElementSibling);
  return clean(el.getAttribute('aria-label') || (prev && prev.innerText) || el.placeholder || el.name);
}"""

HAND_ONLY_SITES = re.compile(r"(^|\.)(linkedin|indeed|glassdoor)\.", re.I)
WORD = re.compile(r"[a-z0-9]{3,}")
MIN_QUESTION_MATCH = 0.7   # share of a question's words that must appear in the field's label


def hand_only(url: str) -> bool:
    return bool(HAND_ONLY_SITES.search(urlparse(url).netloc))


def parse_answers(path: Path) -> dict:
    """answers.md: each '## question' heading followed by its answer. Unfinished answers (TODO) are left out."""
    if not path or not path.exists():
        return {}
    answers = {}
    for chunk in re.split(r"^## +", path.read_text(encoding="utf-8"), flags=re.M)[1:]:
        question, _, answer = chunk.partition("\n")
        answer = answer.strip()
        if answer and "TODO" not in answer:
            answers[question.strip()] = answer
    return answers


def match_answer(desc: str, answers: dict) -> str:
    """The question whose words best fit this field's label, or '' if none fits well enough."""
    label = set(WORD.findall(desc.lower()))
    best, best_share = "", 0
    for question in answers:
        words = set(WORD.findall(question.lower()))
        share = len(words & label) / len(words) if words else 0
        if share > best_share:
            best, best_share = question, share
    return best if best_share >= MIN_QUESTION_MATCH else ""


def _profile_values(profile: dict) -> dict:
    v = {k: str(val) for k, val in profile.items() if val not in (None, "")}
    if "full_name" not in v and ("first_name" in v or "last_name" in v):
        v["full_name"] = f"{v.get('first_name', '')} {v.get('last_name', '')}".strip()
    return v


def unfilled(page) -> list:
    """Labels of visible fields still empty on the page, for the candidate to answer."""
    labels = []
    for frame in page.frames:
        try:
            fields = frame.locator("input, textarea, select").all()
        except Exception:
            continue
        for el in fields:
            try:
                kind = (el.get_attribute("type") or "text").lower()
                if kind in ("hidden", "submit", "button", "checkbox", "radio", "file", "search", "password") \
                        or not el.is_visible() or el.input_value():
                    continue
                label = el.evaluate(LABEL_JS)
                if label and label not in labels:
                    labels.append(label)
            except Exception:
                continue
    return labels


def autofill(page, profile: dict, resume: Path = None, cover: Path = None, answers: dict = None) -> int:
    """Fill empty text fields and file inputs across all frames. Returns number of fields touched."""
    values = _profile_values(profile)
    answers = dict(answers or {})
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
                question = match_answer(desc, answers)
                if question:
                    el.fill(answers.pop(question))
                    filled += 1
                    continue
                if el.evaluate("e => e.tagName") == "TEXTAREA":
                    continue  # a long question never gets a contact detail
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


def apply_queue(cfg, rows, tracker, resume: Path, cover: Path = None, job_dir=None, daily_limit: int = 0):
    from playwright.sync_api import sync_playwright
    profile = cfg.get("profile") or {}
    with sync_playwright() as p:
        ctx = _context(p, cfg)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for i, row in enumerate(rows, 1):
            if daily_limit and tracker.applied_today() >= daily_limit:
                print(f"\nDaily limit reached ({daily_limit} applications). Stopping here.")
                break
            print(f"\n[{i}/{len(rows)}] {row['title']} @ {row['company']}  (score {row['score']})\n    {row['url']}")
            try:
                page.goto(row["url"], wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"    ! could not open: {e}")
            # a CV / cover letter tailored for this job wins over the default files
            keys = row.keys()
            job_cv = Path(row["cv_pdf"]) if "cv_pdf" in keys and row["cv_pdf"] else None
            job_cover = Path(row["cover_pdf"]) if "cover_pdf" in keys and row["cover_pdf"] else None
            use_cv = job_cv if job_cv and job_cv.exists() else resume
            use_cover = job_cover if job_cover and job_cover.exists() else cover
            print(f"    CV: {use_cv.name if use_cv else '-'}" + (f"   cover letter: {use_cover.name}" if use_cover else ""))
            folder = job_dir(cfg, row) if job_dir else None
            answers = parse_answers(folder / "answers.md") if folder else {}
            if answers:
                print(f"    {len(answers)} drafted answer(s) in answers.md")
            print("    Click 'Apply' / log in if needed, then use the prompt below. I never submit for you.")
            while True:
                choice = input("    [Enter]=autofill  a=mark applied  s=skip  l=later  q=quit > ").strip().lower()
                if choice == "":
                    current = _active_page(ctx)
                    if hand_only(current.url):
                        print("    LinkedIn, Indeed and Glassdoor don't allow automation: fill this one by hand.")
                        continue
                    if folder:  # edits made while the browser is open count
                        answers = parse_answers(folder / "answers.md")
                    n = autofill(current, profile, use_cv, use_cover, answers)
                    print(f"    filled {n} field(s). Review every answer, complete the rest, then SUBMIT yourself.")
                    empty = unfilled(current)
                    if empty:
                        print("    Still empty:\n      - " + "\n      - ".join(empty))
                        if folder:
                            (folder / "questions.md").write_text("\n".join(f"- {q}" for q in empty) + "\n", encoding="utf-8")
                            print(f"    Saved to questions.md. For long questions, run `/job-hunter answers {row['id'][:8]}` "
                                  "in Claude Code, then press Enter again.")
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
