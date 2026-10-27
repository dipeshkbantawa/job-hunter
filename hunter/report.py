"""Clickable HTML digest: your CV + career sites, then one section per region in priority order
with one-click LinkedIn/Indeed/Google/local-board searches and the matched jobs."""
import html
from datetime import datetime
from pathlib import Path

from .links import board_links, company_pages, region

CSS = """body{font:14px system-ui,sans-serif;margin:24px;background:#f7f7f8;color:#1f2328}
h1{font-size:20px}h2{font-size:17px;margin:32px 0 8px}table{border-collapse:collapse;width:100%;background:#fff}
td,th{padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}
th{background:#f0f1f3}.s{font-weight:600}.m{color:#57606a;font-size:12px}a{color:#0b62d6}
.links{margin:4px 0}.links a{display:inline-block;margin:2px 10px 2px 0}code{color:#57606a;background:#eef0f2;padding:1px 4px}
.box{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px}.warn{color:#b42318}
nav a{margin-right:14px}.empty{color:#57606a;font-style:italic}
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


def _jobs_table(rows, e):
    if not rows:
        return "<p class=empty>No matched jobs from the job APIs yet. Use the search links above.</p>"
    out = ["<table><tr><th>Score</th><th>Job</th><th>Location</th><th>Posted</th><th>Status</th><th>ID</th></tr>"]
    for r in rows:
        out.append(
            f"<tr><td class=s>{r['score']}</td><td><a href=\"{e(r['url'])}\" target=_blank>{e(r['title'])}</a>"
            f" &middot; {e(r['company'])}<div class=m>{e(r['source'])} &middot; {e(r['matched'] or '')}</div></td>"
            f"<td>{e(r['location'] or '')}</td><td>{e(r['posted'] or '')}</td><td>{e(r['status'])}</td>"
            f"<td><code>{r['id'][:8]}</code></td></tr>")
    out.append("</table>")
    return "".join(out)


def write_report(path, rows, cfg):
    e = html.escape
    search = cfg["search"]
    names = search.get("regions") or ["Remote"]
    labels = [region(n)["label"] for n in names]
    by_region = {label: [r for r in rows if r["region"] == label] for label in labels}

    out = [f"<!doctype html><meta charset=utf-8><title>Job digest</title><style>{CSS}</style>",
           f"<h1>Job digest &middot; {datetime.now():%Y-%m-%d %H:%M}</h1>",
           "<nav><a href=#cv>Your CV</a>" + "".join(
               f'<a href="#r{i}">{i}. {e(lb)} ({len(by_region[lb])})</a>' for i, lb in enumerate(labels, 1)) + "</nav>",
           _cv_section(cfg, e)]
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
