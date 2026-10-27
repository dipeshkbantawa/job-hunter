"""Build ATS-safe CV and cover-letter PDFs from YAML data.

The master CV lives in cv.yaml (your single source of truth). Tailored CVs are copies of it with
reworded summary/bullets for one job. Rendering is HTML -> PDF in Chromium (Playwright), which
writes real text with real spaces: no icon fonts, no columns, no hyphenation, standard headings -
the things that broke the old LaTeX PDF for parsers.
"""
import html
import re
from datetime import date
from pathlib import Path

import yaml

CSS = """
@page { size: A4; margin: 11mm 13mm 11mm 13mm; }
* { box-sizing: border-box; }
/* no ligatures: "fi"/"ff" glyphs would turn "configured" into "conﬁgured" for parsers */
body { font-family: Calibri, Carlito, "Segoe UI", Arial, sans-serif; font-size: 10.1pt; line-height: 1.27;
       color: #1a1a1a; margin: 0; hyphens: manual; font-variant-ligatures: none;
       font-feature-settings: "liga" 0, "clig" 0, "dlig" 0; }
.nb { white-space: nowrap; }
h1 { font-size: 20pt; margin: 0; font-weight: 700; color: #0b3d5c; }
.headline { font-size: 11.5pt; font-weight: 600; margin: 2px 0 4px; color: #1f4e6b; }
.contact { font-size: 9.6pt; color: #333; }
.contact a { color: #333; text-decoration: none; }
h2 { font-size: 11.5pt; color: #0b3d5c; border-bottom: 1.2px solid #0b3d5c; margin: 11px 0 5px; padding-bottom: 1px;
     break-after: avoid-page; }
h2 + .entry, h2 + p, h2 + ul { break-before: avoid-page; }
p { margin: 0 0 4px; }
.entry { margin: 0 0 6px; break-inside: avoid-page; }
.row { display: flex; justify-content: space-between; gap: 12px; }
.role { font-weight: 700; }
.org { color: #333; }
.when { color: #444; white-space: nowrap; }
ul { margin: 2px 0 0 0; padding-left: 15px; }
li { margin: 0 0 1.5px; }
.comp { margin: 0; }
.skills p { margin: 0 0 2px; }
.letter p { margin: 0 0 9px; }
"""


def _md(text) -> str:
    """Escape, then allow **bold** only."""
    t = html.escape(str(text or ""))
    # keep hyphenated words on one line so a parser never sees "Graph-" + "based"
    t = re.sub(r"\b(\w+(?:-\w+)+)\b", r"<span class=nb>\1</span>", t)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)


def _contact(d) -> str:
    parts = [d.get("location"), d.get("email"), d.get("phone"), d.get("linkedin"), d.get("github"), d.get("website")]
    return " | ".join(html.escape(str(p)) for p in parts if p)


def render_cv(d: dict) -> str:
    out = [f"<h1>{_md(d['name'])}</h1>"]
    if d.get("headline"):
        out.append(f"<div class=headline>{_md(d['headline'])}</div>")
    out.append(f"<div class=contact>{_contact(d)}</div>")

    if d.get("summary"):
        out.append(f"<h2>Professional Summary</h2><p>{_md(d['summary'])}</p>")
    if d.get("competencies"):
        out.append("<h2>Core Competencies</h2><p class=comp>"
                   + " | ".join(_md(c) for c in d["competencies"]) + "</p>")
    if d.get("experience"):
        out.append("<h2>Work Experience</h2>")
        for e in d["experience"]:
            org = ", ".join(x for x in (e.get("company"), e.get("location")) if x)
            out.append(
                f"<div class=entry><div class=row><span><span class=role>{_md(e['title'])}</span>"
                f" <span class=org>| {_md(org)}</span></span>"
                f"<span class=when>{_md(e.get('start', ''))} – {_md(e.get('end', 'Present'))}</span></div>"
                + ("<ul>" + "".join(f"<li>{_md(b)}</li>" for b in e.get("bullets") or []) + "</ul>"
                   if e.get("bullets") else "") + "</div>")
    if d.get("projects"):
        out.append("<h2>Projects</h2>")
        for pr in d["projects"]:
            meta = " | ".join(x for x in (pr.get("tech"), pr.get("url")) if x)
            out.append(
                f"<div class=entry><div class=row><span><span class=role>{_md(pr['name'])}</span>"
                + (f" <span class=org>| {_md(meta)}</span>" if meta else "")
                + f"</span><span class=when>{_md(pr.get('date', ''))}</span></div>"
                + "<ul>" + "".join(f"<li>{_md(b)}</li>" for b in pr.get("bullets") or []) + "</ul></div>")
    if d.get("education"):
        out.append("<h2>Education</h2>")
        for ed in d["education"]:
            out.append(
                f"<div class=entry><div class=row><span><span class=role>{_md(ed['degree'])}</span>"
                f" <span class=org>| {_md(ed.get('school', ''))}</span></span>"
                f"<span class=when>{_md(ed.get('start', ''))} – {_md(ed.get('end', ''))}</span></div>"
                + (f"<p>{_md(ed['details'])}</p>" if ed.get("details") else "") + "</div>")
    if d.get("certifications"):
        out.append("<h2>Certifications</h2><ul>"
                   + "".join(f"<li>{_md(c)}</li>" for c in d["certifications"]) + "</ul>")
    if d.get("skills"):
        out.append("<h2>Skills</h2><div class=skills>" + "".join(
            f"<p><strong>{_md(k)}:</strong> {', '.join(_md(v) for v in vals)}</p>"
            for k, vals in d["skills"].items()) + "</div>")
    return _page(f"{d['name']} - CV" + (f" - {d['headline'].split('|')[0].strip()}" if d.get("headline") else ""),
                 "\n".join(out))


def render_letter(d: dict, cv: dict) -> str:
    """Cover letter: d has company, role, greeting, paragraphs, closing; contact comes from the CV data."""
    out = [f"<h1>{_md(cv['name'])}</h1>", f"<div class=contact>{_contact(cv)}</div><br>",
           f"<p>{_md(d.get('date') or date.today().strftime('%d %B %Y'))}</p>"]
    if d.get("recipient"):
        out.append(f"<p>{_md(d['recipient'])}<br>{_md(d.get('company', ''))}</p>")
    out.append(f"<p><strong>Re: {_md(d.get('role', ''))}</strong></p>")
    out.append(f"<p>{_md(d.get('greeting', 'Dear Hiring Manager,'))}</p>")
    out += [f"<p>{_md(p)}</p>" for p in d.get("paragraphs") or []]
    out.append(f"<p>{_md(d.get('closing', 'Kind regards,'))}<br>{_md(cv['name'])}</p>")
    return _page(f"{cv['name']} - Cover letter - {d.get('company', '')}", "<div class=letter>" + "\n".join(out) + "</div>")


def _page(title, body) -> str:
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{html.escape(title)}</title>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")


def to_pdf(html_text: str, out: Path, channel: str = "") -> Path:
    from playwright.sync_api import sync_playwright
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".html").write_text(html_text, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel) if channel else p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_text, wait_until="load")
        page.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True)
        browser.close()
    return out


def load(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


# --- fact check: a tailored document must not contain numbers/claims absent from the master CV ---

NUM = re.compile(r"\d[\d,.]*\s?(?:%|\+|k|K|M|x)?")


def _numbers(text: str) -> set:
    return {re.sub(r"[\s,]", "", m.group()).rstrip(".").lower() for m in NUM.finditer(text)}


def flatten(d) -> str:
    if isinstance(d, dict):
        return " ".join(flatten(v) for v in d.values())
    if isinstance(d, list):
        return " ".join(flatten(v) for v in d)
    return str(d or "")


def fact_check(tailored: dict, master: dict) -> list:
    """Return problems: numbers/years/employers/titles in the tailored doc that the master CV doesn't have."""
    problems = []
    master_text = flatten(master)
    extra = sorted(_numbers(flatten(tailored)) - _numbers(master_text))
    # dates of today's letter are fine
    extra = [n for n in extra if not re.fullmatch(r"20\d\d|\d{1,2}", n)]
    if extra:
        problems.append(f"numbers not in your master CV: {', '.join(extra[:15])}")
    m_jobs = {(e.get("company", "").lower(), e.get("title", "").lower()) for e in master.get("experience") or []}
    for e in tailored.get("experience") or []:
        key = (e.get("company", "").lower(), e.get("title", "").lower())
        if key not in m_jobs:
            problems.append(f"job title/employer changed or added: {e.get('title')} @ {e.get('company')}")
        m = next((x for x in master.get("experience") or []
                  if (x.get("company", "").lower(), x.get("title", "").lower()) == key), None)
        if m and (m.get("start"), m.get("end")) != (e.get("start"), e.get("end")):
            problems.append(f"dates changed for {e.get('title')} @ {e.get('company')}")
    m_certs = " ".join(master.get("certifications") or []).lower()
    for c in tailored.get("certifications") or []:
        name = re.split(r"\s[—-]\s", c)[0].strip("* ").lower()
        if name and name not in m_certs:
            problems.append(f"certification not in master CV: {c}")
    return problems
