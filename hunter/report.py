"""Clickable HTML digest of matched jobs plus one-click LinkedIn/Indeed/Google searches."""
import html
from datetime import datetime

from .links import board_links

CSS = """body{font:14px system-ui,sans-serif;margin:24px;background:#f7f7f8;color:#1f2328}
h1{font-size:20px}h2{font-size:16px;margin-top:28px}table{border-collapse:collapse;width:100%;background:#fff}
td,th{padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}
th{background:#f0f1f3}.s{font-weight:600}.m{color:#57606a;font-size:12px}a{color:#0b62d6}
.links a{display:inline-block;margin:2px 8px 2px 0}code{color:#57606a}"""


def write_report(path, rows, search: dict):
    e = html.escape
    out = [f"<!doctype html><meta charset=utf-8><title>Job digest</title><style>{CSS}</style>",
           f"<h1>Job digest &middot; {datetime.now():%Y-%m-%d %H:%M}</h1>",
           "<h2>Search boards directly (opens with your saved login)</h2>"]
    for kw in search.get("keywords") or []:
        links = board_links(kw, search.get("remote_only", True), search.get("max_age_days", 7),
                            search.get("location", ""))
        out.append(f"<div class=links><b>{e(kw)}:</b> " +
                   "".join(f'<a href="{e(u)}" target=_blank>{e(n)}</a>' for n, u in links.items()) + "</div>")
    out.append(f"<h2>Matched jobs ({len(rows)})</h2><table><tr><th>Score</th><th>Job</th>"
               "<th>Location</th><th>Posted</th><th>Status</th><th>ID</th></tr>")
    for r in rows:
        out.append(
            f"<tr><td class=s>{r['score']}</td><td><a href=\"{e(r['url'])}\" target=_blank>{e(r['title'])}</a>"
            f" &middot; {e(r['company'])}<div class=m>{e(r['source'])} &middot; {e(r['matched'] or '')}</div></td>"
            f"<td>{e(r['location'] or '')}</td><td>{e(r['posted'] or '')}</td><td>{e(r['status'])}</td>"
            f"<td><code>{r['id'][:8]}</code></td></tr>")
    out.append("</table>")
    path.write_text("\n".join(out), encoding="utf-8")
    return path
