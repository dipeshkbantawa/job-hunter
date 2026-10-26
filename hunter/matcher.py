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
