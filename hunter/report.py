"""Clickable HTML digest: your CV + career sites, then one section per region in priority order
with one-click LinkedIn/Indeed/Google/local-board searches and the matched jobs."""
import html
from datetime import datetime
from pathlib import Path

from .links import board_links, company_pages, region, visa_links

CSS = """body{font:14px system-ui,sans-serif;margin:24px;background:#f7f7f8;color:#1f2328}
h1{font-size:20px}h2{font-size:17px;margin:32px 0 8px}table{border-collapse:collapse;width:100%;background:#fff}
td,th{padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}
th{background:#f0f1f3}.s{font-weight:600}.m{color:#57606a;font-size:12px}a{color:#0b62d6}
.links{margin:4px 0}.links a{display:inline-block;margin:2px 10px 2px 0}code{color:#57606a;background:#eef0f2;padding:1px 4px}
.box{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px}.warn{color:#b42318}
nav a{margin-right:14px}.empty{color:#57606a;font-style:italic}h3{font-size:14px;margin:16px 0 4px}
.badge{font-size:11px;padding:1px 6px;border-radius:10px;margin-left:6px;white-space:nowrap}
.badge.ok{background:#dafbe1;color:#116329}.badge.no{background:#ffebe9;color:#a40e26}
.badge.open{background:#ddf4ff;color:#0a3069}
summary{cursor:pointer;color:#0b62d6;margin:4px 0 8px}"""


def _cv_section(cfg, e):
    rel = (cfg.get("profile") or {}).get("resume")
    path = Path(rel) if rel else None
    if path and not path.is_absolute():
        path = cfg["_root"] / path
    if path and path.exists():
        cv = (f"<b>{e(path.name)}</b> &middot; last changed {datetime.fromtimestamp(path.stat().st_mtime):%Y-%m-%d %H:%M}"
              f" &middot; <a href=\"{e(path.as_uri())}\">open</a>")
        try:
            from .atscheck import check
            res = check(path)
            issues = [f"{lvl}: {title}" for lvl, title, _ in res.checks if lvl != "OK"]
            cls = "" if res.score >= 80 else " class=warn"
            cv += (f"<div><b{cls}>ATS format score {res.score}/100</b>"
                   + (f" &middot; {e('; '.join(issues))}" if issues else "")
                   + " &middot; details: <code>python -m hunter cv-check</code></div>")
        except Exception as ex:
            cv += f"<div class=warn>ATS check failed: {e(str(ex))}</div>"
    else:
        cv = (f"<span class=warn>CV not found ({e(str(path or 'profile.resume not set'))}). "
              "Put your CV in the <code>cv</code> folder and set <code>profile.resume</code> in config.yaml.</span>")
    sites = "".join(f'<a href="{e(s["url"])}" target=_blank>{e(s["name"])}</a>'
                    for s in cfg.get("career_sites") or [])
    return ("<h2 id=cv>Your CV</h2><div class=box>"
            f"<div>{cv}</div>"
            "<p>After you edit your CV, run <code>.\\.venv\\Scripts\\python.exe -m hunter update-cv</code>. "
            "It opens each site below in the tool's browser and attaches the new file; you check it and click Save.</p>"
            f"<div class=links><b>Career sites:</b> {sites or '<span class=empty>none in config.yaml</span>'}</div></div>")


VISA_BADGE = {"visa+relocation": ("ok", "Visa + relocation"), "visa": ("ok", "Visa sponsorship"),
              "relocation": ("ok", "Relocation support"), "open": ("open", "Open to relocating"),
              "no": ("no", "No sponsorship")}


def _badge(r, e):
    kind, text = VISA_BADGE.get(r["visa"] or "", ("", ""))
    return f" <span class=\"badge {kind}\">{e(text)}</span>" if text else ""


def _jobs_table(rows, e, empty="No matched jobs from the job APIs yet. Use the search links above."):
    if not rows:
        return f"<p class=empty>{e(empty)}</p>"
    out = ["<table><tr><th>Score</th><th>Job</th><th>Location</th><th>Posted</th><th>Status</th><th>ID</th></tr>"]
    for r in rows:
        out.append(
            f"<tr><td class=s>{r['score']}</td><td><a href=\"{e(r['url'])}\" target=_blank>{e(r['title'])}</a>"
            f" &middot; {e(r['company'])}{_badge(r, e)}"
            f"<div class=m>{e(r['source'])} &middot; {e(r['matched'] or '')}</div></td>"
            f"<td>{e(r['location'] or '')}</td><td>{e(r['posted'] or '')}</td><td>{e(r['status'])}</td>"
            f"<td><code>{r['id'][:8]}</code></td></tr>")
    out.append("</table>")
    return "".join(out)


def _visa_section(offering, names, search, e, home=""):
    offers = [r for r in offering if r["visa"] != "open"]
    open_ = [r for r in offering if r["visa"] == "open"]
    out = ["<h2 id=visa>Visa sponsorship &amp; relocation</h2><div class=box>",
           "<p class=m>Tracked jobs whose ad mentions visa sponsorship or relocation. On-site jobs abroad whose ad "
           "rules sponsorship out are dropped automatically. Few ads say this explicitly, so also use the "
           "sponsorship searches at the bottom.</p>",
           "<h3>Offers visa sponsorship or relocation support</h3>",
           _jobs_table(offers, e, "No tracked job ad currently offers sponsorship or relocation support."),
           "<h3>Open to candidates relocating (no support promised - ask in your application)</h3>",
           _jobs_table(open_, e, "None right now."),
           "<h3>Sponsorship searches by country</h3>"]
    for name in names:
        label = region(name)["label"]
        if label == "Remote" or any(m in home.lower() for m in region(name)["match"]):
            continue  # no visa needed for remote work or your own country
        links = visa_links(search.get("keywords") or [], name)
        out.append(f"<div class=links><b>{e(region(name)['label'])}:</b> " + "".join(
            f'<a href="{e(u)}" target=_blank>{e(n)}</a>' for n, u in links.items()) + "</div>")
    out.append("</div>")
    return "".join(out)


def _file_link(p, label, e):
    if not p:
        return ""
    path = Path(p)
    return f'<a href="{e(path.resolve().as_uri())}">{e(label)}</a>' if path.exists() else ""


def _pipeline_section(rows, due, e):
    stage_order = ["offer", "interview", "assessment", "responded", "applied", "evaluated", "saved"]
    active = sorted([r for r in rows if r["status"] in stage_order],
                    key=lambda r: (stage_order.index(r["status"]), -(r["rating"] or 0)))
    out = ["<h2 id=pipeline>Your pipeline</h2><div class=box>"]
    if not active:
        out.append("<p class=empty>Nothing evaluated or applied yet. Open Claude Code in this folder and paste a job "
                   "link (or type <code>/job-hunter evaluate &lt;id&gt;</code>).</p></div>")
        return "".join(out)
    out.append("<table><tr><th>Stage</th><th>Rating</th><th>Job</th><th>Documents</th><th>Next</th></tr>")
    for r in active:
        rating = f"{r['rating']:.1f}/5" if r["rating"] is not None else "-"
        docs = " &middot; ".join(x for x in (_file_link(r["report"], "report", e), _file_link(r["cv_pdf"], "CV", e),
                                             _file_link(r["cover_pdf"], "cover letter", e)) if x) or "-"
        nxt = due.get(r["id"]) or {"evaluated": "tailor CV / apply" if (r["rating"] or 0) >= 4 else "skip?",
                                   "saved": "evaluate"}.get(r["status"], "")
        out.append(f"<tr><td class=s>{e(r['status'])}</td><td>{rating}</td><td><a href=\"{e(r['url'])}\" "
                   f"target=_blank>{e(r['title'])}</a> &middot; {e(r['company'])}{_badge(r, e)}"
                   f"<div class=m>{e(r['region'] or '-')} &middot; <code>{r['id'][:8]}</code></div></td>"
                   f"<td>{docs}</td><td>{e(nxt)}</td></tr>")
    out.append("</table></div>")
    return "".join(out)


def write_report(path, rows, cfg, due=None):
    e = html.escape
    search = cfg["search"]
    names = search.get("regions") or ["Remote"]
    labels = [region(n)["label"] for n in names]
    open_rows = [r for r in rows if r["status"] not in ("discarded", "skipped", "rejected")]
    by_region = {label: [r for r in open_rows if r["region"] == label] for label in labels}

    offering = [r for r in open_rows if (r["visa"] or "") in ("visa", "relocation", "visa+relocation", "open")]
    in_pipe = sum(r["status"] not in ("new", "discarded", "skipped") for r in rows)
    out = [f"<!doctype html><meta charset=utf-8><title>Job digest</title><style>{CSS}</style>",
           f"<h1>Job digest &middot; {datetime.now():%Y-%m-%d %H:%M}</h1>",
           "<nav><a href=#cv>Your CV</a>"
           f"<a href=#pipeline>Pipeline ({in_pipe})</a>"
           f"<a href=#visa>Visa &amp; relocation ({len(offering)})</a>" + "".join(
               f'<a href="#r{i}">{i}. {e(lb)} ({len(by_region[lb])})</a>' for i, lb in enumerate(labels, 1)) + "</nav>",
           _cv_section(cfg, e),
           _pipeline_section(rows, due or {}, e),
           _visa_section(offering, names, search, e, (cfg.get("profile") or {}).get("location", ""))]
    for i, (name, label) in enumerate(zip(names, labels), 1):
        out.append(f"<h2 id=r{i}>{i}. {e(label)}</h2><details{' open' if i == 1 else ''}>"
                   f"<summary>Search LinkedIn, Indeed, Google, Glassdoor and local boards</summary>")
        for kw in search.get("keywords") or []:
            links = board_links(kw, name, search.get("max_age_days", 7))
            out.append(f"<div class=links><b>{e(kw)}:</b> " + "".join(
                f'<a href="{e(u)}" target=_blank>{e(n)}</a>' for n, u in links.items()) + "</div>")
        out.append("</details>")
        companies = company_pages(cfg, name)
        if companies:
            out.append("<div class=links><b>Company career pages:</b> " + "".join(
                f'<a href="{e(c["url"])}" target=_blank>{e(c["name"])}</a>' for c in companies) + "</div>")
        out.append(_jobs_table(by_region[label], e))
    path.write_text("\n".join(out), encoding="utf-8")
    return path
