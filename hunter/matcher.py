"""Filter jobs against your preferences and score them against your CV/skills."""
import re
from datetime import date, timedelta
from pathlib import Path

from . import links

STOPWORDS = set("""a an the and or of to in on for with at by from as is are be will you your we our
our their this that these those it its into about over under who what when where how all any
can may must should would could have has had not but if than then also more most such per
experience work working team teams role job company years year strong ability skills using""".split())


def load_cv_text(path) -> str:
    if not path or not Path(path).exists():
        return ""
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            return "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
        if suffix == ".docx":
            import docx
            return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"  ! could not read CV {path}: {e}")
        return ""


def tokens(text: str) -> set:
    words = re.findall(r"[a-z][a-z0-9+#.\-]{2,}", text.lower())
    return {w.strip(".-") for w in words if w not in STOPWORDS}


def _stem_hit(word: str, text: str) -> bool:
    stem = word if len(word) <= 5 else word[: max(4, len(word) - 2)]
    return re.search(r"\b" + re.escape(stem), text) is not None


def relevant(job, keywords) -> bool:
    """True if a search keyword fits the job title/tags (or appears verbatim in the description)."""
    head = (job.title + " " + " ".join(job.tags)).lower()
    for kw in keywords:
        kw = kw.lower()
        if all(_stem_hit(w, head) for w in kw.split()) or kw in job.description.lower():
            return True
    return False


def match_region(job, search: dict):
    """(rank, region label) of the first region in your priority list that fits the job, else None."""
    for rank, name in enumerate(search.get("regions") or [], 1):
        if links.matches(job, name):
            return rank, links.region(name)["label"]
    return None


def passes(job, search: dict) -> bool:
    text = job.text + " " + job.location.lower()
    if search.get("regions"):
        if match_region(job, search) is None:
            return False
    elif search.get("remote_only", True) and not (job.remote or "remote" in text):
        return False
    if any(x.lower() in text for x in search.get("exclude") or []):
        return False
    must = search.get("must_have_any") or []
    if must and not any(x.lower() in text for x in must):
        return False
    max_age = search.get("max_age_days")
    # company boards (greenhouse/lever) only list open roles, so an older post date is still live
    if max_age and job.source not in ("greenhouse", "lever") and job.posted and job.posted < (date.today() - timedelta(days=max_age)).isoformat():
        return False
    return relevant(job, search.get("keywords") or [])


_NEG = r"(?:no|not|unable to|cannot|can't|does not|do not|will not|won't|is not|isn't|are not)"
VISA_NO = re.compile(
    rf"{_NEG}\s+(?:\w+\s+){{0,3}}(?:offer\s+|provide\s+)?(?:visa\s+|work\s+permit\s+)?sponsor"
    rf"|{_NEG}\s+(?:\w+\s+){{0,2}}(?:visa|immigration|relocation)\s+(?:assistance|support|sponsorship|help)"
    r"|without\s+(?:\w+\s+)?sponsorship"
    r"|(?:not\s+)?require\s+(?:\w+\s+){0,2}sponsorship"
    r"|(?:must|need to)\s+(?:already\s+)?(?:have|hold)\s+(?:the\s+|a\s+)?(?:current\s+)?"
    r"(?:right to work|work authori[sz]ation|valid work)"
    r"|relocation\s+(?:is\s+)?not\s+(?:\w+\s+)?(?:provided|offered|available|supported)"
    # South Korea: nationals / existing visa holders only
    r"|korean\s+(?:citizens?|nationals?)\s+only|only\s+(?:\w+\s+){0,3}korean\s+(?:citizens?|nationals?)"
    r"|f-?[2456]\s*(?:visa\s*)?(?:holders?\s+)?only"
    r"|(?:must|need to)\s+(?:already\s+)?(?:have|hold)\s+(?:a\s+)?valid\s+korean\s+(?:work\s+)?visa"
    r"|외국인\s*(?:지원\s*)?불가|내국인\s*(?:만|한정)", re.I)
VISA_YES = re.compile(
    r"visa\s+sponsorship\s+(?:is\s+)?(?:available|provided|offered|possible|support)"
    r"|(?:we|will|can|able to|happy to|willing to)\s+(?:\w+\s+){0,2}sponsor"
    r"|sponsor(?:ship)?\s+(?:for|of)\s+(?:a\s+|an\s+|your\s+)?(?:work\s+|employment\s+)?(?:visa|permit|pass)"
    r"|(?:employment\s+pass|work\s+visa|work\s+permit)\s+(?:sponsorship|support|assistance)"
    r"|(?:help|assist|support)\w*\s+(?:you\s+)?with\s+(?:your\s+)?(?:visa|work permit|immigration)"
    # South Korea: E-7 (skilled worker) sponsorship, 비자 지원 = visa support
    r"|e-?7\s*(?:visa\s*)?(?:sponsor|support|available|provided|issu)|(?:sponsor|support|issu)\w*\s+(?:\w+\s+){0,2}e-?7"
    r"|비자\s*(?:지원|스폰서|발급\s*지원)", re.I)
RELOC_YES = re.compile(
    r"relocation\s+(?:support|assistance|package|allowance|bonus|benefits?|help)"
    r"|(?:full|paid|generous)\s+relocation"
    r"|relocation\s+(?:\w+\s+){0,5}(?:will be|is|are)\s+(?:\w+\s+)?(?:provided|offered|available|covered)"
    r"|(?:help|assist|support)\w*\s+(?:you\s+)?(?:with\s+)?(?:your\s+)?relocat"
    r"|facilitat\w*\s+(?:\w+\s+){0,2}relocation", re.I)


OPEN_INTL = re.compile(  # accepts people moving in, without promising support
    r"willing to relocate|open to relocation|relocat\w* (?:candidates|applicants)|expatriate"
    r"|international (?:candidates|applicants)|candidates from (?:abroad|overseas|any country)"
    r"|foreign(?:ers|\s+nationals|\s+candidates|\s+applicants|\s+workers)\s+(?:are\s+)?(?:welcome|eligible|can apply|may apply)"
    r"|open to foreigners|외국인\s*(?:지원\s*가능|가능|환영|우대|채용)", re.I)

KOREAN_REQ = re.compile(
    r"(?:native|fluent|fluency|business[- ]level|proficient|proficiency)\s+(?:\w+\s+){0,3}korean"
    r"|korean\s+(?:language\s+)?(?:\w+\s+){0,2}(?:fluency|fluent|proficiency|native)"
    r"|topik\s*(?:level\s*)?[3-6]|한국어\s*(?:능력\s*)?(?:능통|원어민|필수)|한국어\s*및\s*영어\s*능통", re.I)
NICE_TO_HAVE = re.compile(r"plus|preferred|advantage|bonus|nice to have|desirable|우대", re.I)


def korean_required(description: str) -> str:
    """'required' when the ad asks for Korean fluency, 'korean-ad' when it is written mostly in Korean,
    '' otherwise. 'Korean is a plus' does not count."""
    text = re.sub(r"\s+", " ", (description or "").replace(" ", " "))
    for m in KOREAN_REQ.finditer(text):
        if not NICE_TO_HAVE.search(text[m.end():m.end() + 40]):
            return "required"
    hangul = sum("가" <= ch <= "힣" for ch in text)
    latin = sum(ch.isascii() and ch.isalpha() for ch in text)
    return "korean-ad" if hangul > latin else ""


def visa_status(job) -> str:
    """'visa+relocation' / 'visa' / 'relocation' when the ad offers it, 'open' when it accepts people relocating,
    'no' when it rules sponsorship out, '' if the ad is silent."""
    text = re.sub(r"\s+", " ", job.description.replace("\xa0", " "))
    if VISA_NO.search(text):
        return "no"
    visa, reloc = bool(VISA_YES.search(text)), bool(RELOC_YES.search(text))
    if visa or reloc:
        return "visa+relocation" if visa and reloc else "visa" if visa else "relocation"
    return "open" if OPEN_INTL.search(text) else ""


def score(job, search: dict, cv_tokens: set):
    """0-100: title fit (40) + listed skills found (40) + overlap with CV vocabulary (20)."""
    text = job.text
    title = job.title.lower()
    pts = 0
    if any(all(_stem_hit(w, title) for w in kw.lower().split()) for kw in search.get("keywords") or []):
        pts += 40
    matched = [s for s in search.get("skills") or []
               if re.search(r"(?<![a-z0-9])" + re.escape(s.lower()) + r"(?![a-z0-9])", text)]
    pts += min(40, len(matched) * 8)
    if cv_tokens:
        jt = tokens(text)
        if jt:
            pts += min(20, round(40 * len(jt & cv_tokens) / len(jt)))
    return min(100, pts), matched
