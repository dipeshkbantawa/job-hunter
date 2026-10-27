"""ATS-friendliness check for a CV (PDF/DOCX/TXT).

An ATS reads the *extracted text* of your CV, not how it looks. This module extracts the text the
same way (pypdf / python-docx), then checks the things that make parsers drop or garble content:
icon fonts, words glued together, hyphenation, missing sections/contact details, images, tables,
length - and how well your keywords cover the jobs you are targeting.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Terms recruiters' ATS filters commonly look for in IT support / infra / cloud / security roles.
TERMS = """microsoft 365|entra id|intune|exchange online|active directory|group policy|sccm|azure|aws|gcp|
google workspace|okta|sso|saml|mfa|windows server|linux|macos|jamf|vmware|hyper-v|powershell|bash|python|
javascript|sql|git|ci/cd|docker|kubernetes|terraform|ansible|jenkins|rest api|json|itil|servicenow|jira|
zendesk|freshdesk|ticketing|helpdesk|service desk|sla|incident management|incident response|root cause|
troubleshooting|escalation|customer support|technical support|remote support|documentation|knowledge base|
runbooks|monitoring|grafana|prometheus|datadog|zabbix|nagios|splunk|siem|sentinel|defender|edr|crowdstrike|
firewall|fortigate|palo alto|cisco|meraki|vpn|sd-wan|tcp/ip|dns|dhcp|lan|wan|vlan|wi-fi|bgp|ospf|mpls|
routing|switching|load balancing|backup|disaster recovery|iso 27001|soc 2|gdpr|phishing|spf|dkim|dmarc|
endpoint|patch management|asset management|onboarding|saas|networking|security|cloud|automation|scripting|
ccna|az-104|comptia|mcsa|cissp|ceh""".replace("\n", "").split("|")
ALIASES = {"office 365": "microsoft 365", "o365": "microsoft 365", "m365": "microsoft 365",
           "azure ad": "entra id", "azure active directory": "entra id", "fortinet": "fortigate",
           "help desk": "helpdesk", "service-desk": "service desk", "rca": "root cause",
           "amazon web services": "aws", "google cloud": "gcp", "k8s": "kubernetes", "wifi": "wi-fi"}

SECTIONS = {
    "experience": r"(work|professional|employment)?\s*(experience|history)",
    "education": r"education|academic|qualifications",
    "skills": r"(technical\s+)?skills|competencies|technologies",
    "summary": r"(professional\s+)?summary|profile|objective|about me",
    "certifications": r"certifications?|licen[cs]es|training",
}
TITLE_WORDS = r"engineer|administrator|manager|analyst|specialist|developer|consultant|technician|architect|lead"


@dataclass
class Result:
    path: Path
    text: str = ""
    pages: int = 0
    checks: list = field(default_factory=list)    # (level, title, detail) level: OK / WARN / FAIL

    def add(self, level, title, detail=""):
        self.checks.append((level, title, detail))

    @property
    def score(self) -> int:
        penalty = {"FAIL": 15, "WARN": 5}
        return max(0, 100 - sum(penalty.get(c[0], 0) for c in self.checks))


def extract(path: Path):
    """Return (text, pages, images, tables, metadata_title) the way a parser sees the file."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = [p.extract_text() or "" for p in reader.pages]
        images = 0
        for p in reader.pages:
            try:
                images += len(p.images)
            except Exception:
                pass
        title = (reader.metadata or {}).get("/Title", "") if reader.metadata else ""
        return pages, images, 0, str(title or "")
    if suffix == ".docx":
        import docx
        d = docx.Document(str(path))
        body = "\n".join(p.text for p in d.paragraphs)
        header = "\n".join(p.text for s in d.sections for p in s.header.paragraphs)
        images = len(d.inline_shapes)
        return [header + "\n" + body], images, len(d.tables), d.core_properties.title or ""
    return [path.read_text(encoding="utf-8", errors="ignore")], 0, 0, ""


def norm(text: str) -> str:
    t = " " + re.sub(r"\s+", " ", text.lower()) + " "
    for a, b in ALIASES.items():
        t = re.sub(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", b, t)
    return t


def has_term(term: str, ntext: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"s?(?![a-z0-9])", ntext) is not None  # plural ok


def check(path: Path) -> Result:
    res = Result(Path(path))
    pages, images, tables, meta_title = extract(res.path)
    text = "\n".join(pages)
    res.text, res.pages = text, len(pages)
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#/.\-]*", text)
    head = "\n".join(text.strip().splitlines()[:6])

    # 1. readable at all
    if len(text.strip()) < 300:
        res.add("FAIL", "Almost no text could be extracted",
                "Looks like a scanned/image PDF. Export it from Word/Google Docs/LaTeX as a text PDF.")
        return res
    res.add("OK", "Text is extractable", f"{len(words)} words over {res.pages} page(s)")

    # 2. icon fonts / symbol glyphs
    junk = re.findall(r"[☀-➿-¶]|/(?:linkedin|github|envelope|phone|globe)\b|"
                      r"[a-z]+-(?:alt|marker|square)\b", text)
    if junk:
        res.add("FAIL", "Icon fonts turn into junk text",
                f"Parsers read: {' '.join(sorted(set(junk))[:8])}. Remove the icons beside location/email/phone/"
                "LinkedIn, or use plain labels like 'Email:' and 'LinkedIn:'.")
    else:
        res.add("OK", "No icon/symbol junk in the text")

    # 3. words glued together (bold/italic runs with no real space characters)
    glued = re.findall(r"\b(?:with|of|the|to|for|in|at|by|from|across|serving|through|and|on|over)"
                       r"(?=[A-Z0-9])\w+|\b[a-z]{3,}\d[\w%+]*|\b\d+[%+]?(?:and|to|at|with|in)\b", text)
    if len(glued) >= 3:
        res.add("FAIL", f"{len(glued)} places where words run together",
                f"e.g. {', '.join(sorted(set(glued))[:8])}. Usually bold text in a LaTeX/designer PDF: the "
                "ATS sees one unknown word, so those keywords and numbers don't count. "
                "LaTeX: add \\input{glyphtounicode} \\pdfgentounicode=1 \\pdfinterwordspaceon to the preamble "
                "(or compile with XeLaTeX/LuaLaTeX); otherwise export from Word/Google Docs.")
    elif glued:
        res.add("WARN", "Some words run together", ", ".join(glued))
    else:
        res.add("OK", "Word spacing survives extraction")

    # 4. hyphenation / ligatures split keywords
    hyph = re.findall(r"[A-Za-z]+-\n[a-z]+", text)
    if hyph:
        res.add("WARN", "Words hyphenated across lines",
                f"{', '.join(h.replace(chr(10), '') for h in hyph[:6])} - the ATS sees two half-words. "
                "Turn off hyphenation (LaTeX: \\usepackage[none]{hyphenat} or \\hyphenpenalty=10000).")
    lig = re.findall(r"\w*[ﬀ-ﬆ]\w*", text)
    if lig:
        res.add("WARN", "Ligature characters inside words", f"{', '.join(lig[:6])} won't match keyword searches.")

    # 5. contact details
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    phone = re.search(r"\+?\d[\d\s().-]{7,}\d", text)
    linkedin = re.search(r"linkedin\.com/in/[\w-]+", text, re.I)
    missing = [n for n, ok in (("email", email), ("phone", phone)) if not ok]
    if missing:
        res.add("FAIL", "Missing contact details", ", ".join(missing))
    else:
        res.add("OK", "Email and phone found")
    if not linkedin:
        res.add("WARN", "No LinkedIn URL", "Add linkedin.com/in/<you> in plain text.")
    if email and email.start() > 600:
        res.add("WARN", "Contact details are not at the top", "Put them in the first lines, not in a footer/sidebar.")

    # 6. headline / target title
    if not re.search(TITLE_WORDS, "\n".join(head.splitlines()[1:4]), re.I):
        res.add("WARN", "No job title under your name",
                "Add a headline like 'Technical Support Engineer | IT Infrastructure | Microsoft 365'. "
                "Many ATS rank by title match.")

    # 7. standard section headings
    lines = [l.strip() for l in text.splitlines() if 0 < len(l.strip()) < 45]
    found = {}
    for name, rx in SECTIONS.items():
        for i, l in enumerate(lines):
            if re.fullmatch(rf"(?i)(?:[\w&]+\s+)?(?:{rx})(?:\s*&\s*[\w ]+)?", l):
                found[name] = i
                break
    req = [s for s in ("experience", "education", "skills") if s not in found]
    if req:
        res.add("FAIL", "Standard section headings not found", ", ".join(req) +
                " - use plain headings like 'Work Experience', 'Education', 'Skills'.")
    else:
        res.add("OK", "Standard sections found", ", ".join(found))
    if "summary" not in found:
        res.add("WARN", "No summary/profile section")
    proj = next((i for i, l in enumerate(lines) if re.match(r"(?i)(selected\s+)?projects", l)), None)
    if proj is not None and "experience" in found and proj < found["experience"]:
        res.add("WARN", "Projects come before Work Experience",
                "Recruiters and some parsers expect experience first; move projects after it.")

    # 8. dates
    ranges = re.findall(r"(?:[A-Z][a-z]{2,8}\.?\s+)?(?:19|20)\d{2}\s*[–—-]+\s*(?:Present|Current|Now|"
                        r"(?:[A-Z][a-z]{2,8}\.?\s+)?(?:19|20)\d{2})", text)
    numeric = re.findall(r"\b\d{1,2}/(?:19|20)\d{2}\b", text)
    if not ranges:
        res.add("WARN", "No date ranges found", "Use 'Mon YYYY – Mon YYYY' (or 'Present') for every role.")
    elif numeric:
        res.add("WARN", "Mixed date formats", "Pick one style, e.g. 'May 2025 – Present'.")
    else:
        res.add("OK", f"{len(ranges)} date ranges in a consistent format")

    # 9. achievements with numbers
    bullets = re.findall(r"^[•\-*▪◦·]\s*(.+)$", text, re.M)
    if bullets:
        quant = sum(bool(re.search(r"\d", b)) for b in bullets)
        pct = round(100 * quant / len(bullets))
        level = "OK" if pct >= 35 else "WARN"
        res.add(level, f"{pct}% of bullet points contain a number",
                "" if level == "OK" else "Add results: %, counts, time saved, users/sites supported.")

    # 10. length, pages, images, tables
    if len(words) < 300:
        res.add("WARN", "CV is short", f"{len(words)} words; aim for 450-900.")
    elif len(words) > 1100:
        res.add("WARN", "CV is long", f"{len(words)} words; aim for 450-900 and 2 pages.")
    if res.pages > 2:
        last = len(pages[-1].split())
        res.add("WARN", f"{res.pages} pages", f"Last page has only {last} words - trim to 2 pages." if last < 150
                else "Most recruiters expect 1-2 pages.")
    if images:
        res.add("WARN", f"{images} image(s) in the file", "Photos/logos/charts are ignored or break parsing.")
    if tables:
        res.add("WARN", f"{tables} table(s) in the document", "Many ATS read tables out of order; use plain lines.")

    # 11. file name and metadata
    name = res.path.stem
    if re.search(r"\(\d+\)|copy|final|resume$|^cv$", name, re.I) or " " in name:
        res.add("WARN", "File name looks like a download copy",
                f"'{res.path.name}' -> e.g. 'Dipesh_Bantawa_Technical_Support_Engineer_CV{res.path.suffix}'"
                if "dipesh" in name.lower() else "Use Firstname_Lastname_Role_CV.pdf")
    if res.path.suffix.lower() == ".pdf" and not meta_title.strip():
        res.add("WARN", "PDF has no Title metadata",
                "Some portals show it as the document name. LaTeX: \\hypersetup{pdftitle={Your Name - CV}}")
    return res


def keyword_gap(cv_text: str, job_texts: list, extra_terms=()):
    """Terms that appear in the target job descriptions, with how many jobs mention them and if your CV has them."""
    ncv = norm(cv_text)
    terms = list(dict.fromkeys([t.lower() for t in extra_terms] + TERMS))
    counts = Counter()
    for jt in job_texts:
        nj = norm(jt)
        for t in terms:
            if has_term(t, nj):
                counts[t] += 1
    rows = [(t, n, has_term(t, ncv)) for t, n in counts.most_common()]
    return rows
