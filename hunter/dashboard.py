"""Local web dashboard over the tracker: `python -m hunter dashboard`.

Same ideas as career-ops' Go dashboard (status tabs, sort, filter, preview, status changes), served by the
standard library on 127.0.0.1 only. Status changes go through Tracker.set_status like `hunter mark`.
"""
import json
import mimetypes
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__, atscheck
from .links import region
from .matcher import korean_required
from .tracker import ACTIVE, STATUSES

PAGE = Path(__file__).with_name("dashboard.html")
HOSTS = ("127.0.0.1", "localhost")


def _folder(root: Path, row):
    """The job's applications/<id8>-<slug>/ folder, if it exists."""
    if row["report"]:
        p = _inside(root, row["report"])
        if p:
            return p.parent
    return next((p for p in (root / "applications").glob(f"{row['id'][:8]}-*") if p.is_dir()), None)


def _inside(root: Path, rel):
    """Resolve a stored path (relative or absolute) and refuse anything outside the repo."""
    if not rel:
        return None
    p = Path(rel)
    p = (p if p.is_absolute() else root / p).resolve()
    return p if p.is_file() and p.is_relative_to(root.resolve()) else None


def _paths(root: Path, row):
    folder = _folder(root, row)
    return {"report": _inside(root, row["report"]) or (folder and _inside(root, folder / "report.md")),
            "jd": folder and _inside(root, folder / "jd.md"),
            "cv": _inside(root, row["cv_pdf"]),
            "cover": _inside(root, row["cover_pdf"])}


_ATS = {}  # (path, mtime) -> (score, issues, text)


def _ats_check(path: Path):
    """Format check of a CV file, as `hunter cv-check` does; cached until the file changes."""
    key = (str(path), path.stat().st_mtime)
    if key not in _ATS:
        try:
            res = atscheck.check(path)
            _ATS[key] = (res.score, [f"{lvl}: {title}" for lvl, title, _ in res.checks if lvl != "OK"], res.text)
        except Exception as ex:
            _ATS[key] = (None, [f"ATS check failed: {ex}"], "")
    return _ATS[key]


def _ats(cv: Path, kind: str, description: str, skills):
    """ATS format score of the CV you'd send, plus how many of the ad's keywords that CV contains."""
    score, issues, text = _ats_check(cv)
    out = {"score": score, "cv": kind, "file": cv.name, "issues": issues, "keywords": None, "have": [], "missing": []}
    if description and text:
        gap = atscheck.keyword_gap(text, [description], skills)
        if gap:
            out["have"] = [t for t, _, ok in gap if ok]
            out["missing"] = [t for t, _, ok in gap if not ok]
            out["keywords"] = round(100 * len(out["have"]) / len(gap))
    return out


def _data(cfg, tracker):
    root = cfg["_root"]
    due = {r["id"]: f"{kind} ({days}d)" for r, days, kind in tracker.due_followups()}
    master = _inside(root, (cfg.get("profile") or {}).get("resume"))
    skills = cfg["search"].get("skills") or []
    jobs = []
    for r in tracker.list(None, 0, 100000):
        j = {k: r[k] for k in r.keys() if k != "description"}
        paths = _paths(root, r)
        j["docs"] = [k for k, p in paths.items() if p]
        j["due"] = due.get(r["id"], "")
        j["korean"] = korean_required(r["description"])
        cv, kind = (paths["cv"], "tailored") if paths["cv"] else (master, "master")
        j["ats"] = _ats(cv, kind, r["description"], skills) if cv else None
        jobs.append(j)
    f = tracker.funnel()
    f = {k: ([dict(x) for x in v] if isinstance(v, list) else v) for k, v in f.items()}
    regions = [region(n)["label"] for n in (cfg["search"].get("regions") or ["Remote"])]
    return {"version": __version__, "jobs": jobs, "funnel": f, "statuses": STATUSES, "active": ACTIVE, "regions": regions,
            "master_ats": _ats_check(master)[0] if master else None}


def make_handler(cfg, tracker, token):
    root = cfg["_root"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the terminal quiet
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, default=str)
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self):  # blocks DNS-rebinding pages from talking to the server
            return (self.headers.get("Host") or "").rsplit(":", 1)[0] in HOSTS

        def _row(self, q):
            rows = tracker.db.execute("SELECT * FROM jobs WHERE id=?", ((q.get("id") or [""])[0],)).fetchall()
            return rows[0] if rows else None

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "bad host"})
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if url.path == "/":
                return self._send(200, PAGE.read_text(encoding="utf-8").replace("__TOKEN__", token),
                                  "text/html; charset=utf-8")
            if url.path == "/api/data":
                return self._send(200, _data(cfg, tracker))
            if url.path in ("/api/doc", "/api/file"):
                row = self._row(q)
                kind = (q.get("kind") or [""])[0]
                p = row and _paths(root, row).get(kind)
                if not p:
                    return self._send(404, {"error": "not found"})
                if url.path == "/api/doc":
                    return self._send(200, p.read_text(encoding="utf-8", errors="replace"),
                                      "text/plain; charset=utf-8")
                return self._send(200, p.read_bytes(), mimetypes.guess_type(p.name)[0] or "application/octet-stream")
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._host_ok() or self.headers.get("X-Token") != token:
                return self._send(403, {"error": "forbidden"})
            if urlparse(self.path).path != "/api/status":
                return self._send(404, {"error": "not found"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except ValueError:
                return self._send(400, {"error": "bad json"})
            row = self._row({"id": [str(body.get("id", ""))]})
            status = body.get("status")
            if not row or status not in STATUSES:
                return self._send(400, {"error": "unknown job or status"})
            tracker.set_status(row["id"], status, str(body.get("note") or "").strip()[:500])
            self._send(200, {"ok": True})

    return Handler


def serve(cfg, tracker, port=8765, open_browser=True):
    token = secrets.token_urlsafe(24)
    handler = make_handler(cfg, tracker, token)
    for p in range(port, port + 20):  # next free port if this one is taken
        try:
            server = HTTPServer(("127.0.0.1", p), handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"No free port between {port} and {port + 19}")
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Dashboard: {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()
