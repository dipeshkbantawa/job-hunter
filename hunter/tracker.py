"""SQLite application tracker so you never apply twice or lose track."""
import csv
import sqlite3
from datetime import datetime
from pathlib import Path

# Pipeline stages (same lifecycle as career-ops): found -> evaluated -> applied -> responses -> outcome
STATUSES = ("new", "saved", "evaluated", "applied", "responded", "assessment", "interview",
            "offer", "hired", "rejected", "discarded", "skipped")
ACTIVE = ("applied", "responded", "assessment", "interview", "offer")
# Follow-up cadence: (days before first nudge, days between nudges, max nudges or None)
CADENCE = {"applied": (7, 7, 2), "responded": (1, 3, None), "assessment": (1, 3, None), "interview": (1, 3, None)}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    source TEXT, title TEXT, company TEXT, location TEXT, url TEXT,
    posted TEXT, score INTEGER, matched TEXT,
    status TEXT DEFAULT 'new',
    found_at TEXT, applied_at TEXT, notes TEXT DEFAULT ''
)"""


class Tracker:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute(SCHEMA)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(jobs)")}
        for col, typ in (("region", "TEXT"), ("region_rank", "INTEGER"), ("description", "TEXT"), ("visa", "TEXT"),
                         ("rating", "REAL"), ("report", "TEXT"), ("cv_pdf", "TEXT"), ("cover_pdf", "TEXT"),
                         ("status_at", "TEXT"), ("followups", "INTEGER DEFAULT 0"), ("last_contact", "TEXT"),
                         ("live", "TEXT"), ("checked_at", "TEXT")):
            if col not in cols:  # databases created by older versions
                self.db.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typ}")

    def upsert(self, job, score: int, matched: list, region=None, rank=None, visa="") -> bool:
        """Insert a job; returns True if it was new. Existing rows get score/region/description/visa refreshed."""
        desc = f"{job.title}\n{' '.join(job.tags)}\n{job.description}"[:8000]
        cur = self.db.execute(
            "INSERT OR IGNORE INTO jobs (id, source, title, company, location, url, posted, score, matched,"
            " found_at, region, region_rank, description, visa) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (job.id, job.source, job.title, job.company, job.location, job.url, job.posted,
             score, ", ".join(matched), datetime.now().isoformat(timespec="seconds"), region, rank, desc, visa))
        if cur.rowcount == 0:
            self.db.execute("UPDATE jobs SET score=?, matched=?, region=?, region_rank=?, description=?, visa=?"
                            " WHERE id=?", (score, ", ".join(matched), region, rank, desc, visa, job.id))
        self.db.commit()
        return cur.rowcount == 1

    def forget_new(self, job_id: str):
        """Remove a job you haven't acted on (e.g. it now fails your filters)."""
        self.db.execute("DELETE FROM jobs WHERE id=? AND status='new'", (job_id,))
        self.db.commit()

    def prune_unplaced(self) -> int:
        """Drop untouched jobs that don't belong to any of your regions (e.g. found before regions were set)."""
        n = self.db.execute("DELETE FROM jobs WHERE status='new' AND region IS NULL").rowcount
        self.db.commit()
        return n

    def list(self, status=None, min_score=0, limit=50, region=None, visa=False):
        """Your region priority first, then best score. visa=True: only jobs offering sponsorship/relocation."""
        sql, args = "SELECT * FROM jobs WHERE score >= ?", [min_score]
        if visa:
            sql += " AND visa IN ('visa', 'relocation', 'visa+relocation', 'open')"
        if status:
            sql += " AND status = ?"
            args.append(status)
        if region:
            sql += " AND lower(region) LIKE ?"
            args.append(region.lower() + "%")
        sql += " ORDER BY COALESCE(region_rank, 99), score DESC, posted DESC LIMIT ?"
        args.append(limit)
        return self.db.execute(sql, args).fetchall()

    def get(self, id_prefix: str):
        rows = self.db.execute("SELECT * FROM jobs WHERE id LIKE ?", (id_prefix + "%",)).fetchall()
        if len(rows) != 1:
            raise SystemExit(f"{'No' if not rows else 'Ambiguous'} job id: {id_prefix}")
        return rows[0]

    def set_status(self, job_id: str, status: str, note: str = ""):
        if status not in STATUSES:
            raise SystemExit(f"Status must be one of: {', '.join(STATUSES)}")
        now = datetime.now().isoformat(timespec="seconds")
        applied = now if status == "applied" else None
        self.db.execute(
            "UPDATE jobs SET status=?, status_at=?, applied_at=COALESCE(?, applied_at),"
            " last_contact=CASE WHEN ? IN ('applied','responded','assessment','interview','offer') THEN ?"
            " ELSE last_contact END,"
            " followups=CASE WHEN status<>? THEN 0 ELSE followups END,"
            " notes=CASE WHEN ?='' THEN notes ELSE TRIM(notes || ' | ' || ?, ' |') END WHERE id=?",
            (status, now, applied, status, now, status, note, note, job_id))
        self.db.commit()

    def set_visa(self, job_id: str, visa: str):
        self.db.execute("UPDATE jobs SET visa=? WHERE id=?", (visa, job_id))
        self.db.commit()

    def add_note(self, job_id: str, note: str):
        self.db.execute("UPDATE jobs SET notes=TRIM(notes || ' | ' || ?, ' |') WHERE id=?", (note, job_id))
        self.db.commit()

    def record(self, job_id: str, rating=None, report=None, cv_pdf=None, cover_pdf=None):
        """Store an evaluation (1-5 rating + report) and generated documents; new/saved jobs become 'evaluated'."""
        self.db.execute(
            "UPDATE jobs SET rating=COALESCE(?, rating), report=COALESCE(?, report), cv_pdf=COALESCE(?, cv_pdf),"
            " cover_pdf=COALESCE(?, cover_pdf),"
            " status=CASE WHEN status IN ('new','saved') THEN 'evaluated' ELSE status END,"
            " status_at=CASE WHEN status IN ('new','saved') THEN ? ELSE status_at END WHERE id=?",
            (rating, report, cv_pdf, cover_pdf, datetime.now().isoformat(timespec="seconds"), job_id))
        self.db.commit()

    def set_live(self, job_id: str, live: str, reason: str = ""):
        self.db.execute("UPDATE jobs SET live=?, checked_at=? WHERE id=?",
                        (live, datetime.now().isoformat(timespec="seconds"), job_id))
        if live == "closed":
            self.db.execute("UPDATE jobs SET status='discarded', status_at=?, notes=TRIM(notes || ' | posting closed: '"
                            " || ?, ' |') WHERE id=? AND status IN ('new','saved','evaluated')",
                            (datetime.now().isoformat(timespec="seconds"), reason, job_id))
        self.db.commit()

    def followed_up(self, job_id: str):
        self.db.execute("UPDATE jobs SET followups=COALESCE(followups,0)+1, last_contact=? WHERE id=?",
                        (datetime.now().isoformat(timespec="seconds"), job_id))
        self.db.commit()

    def due_followups(self, today=None):
        """Applications whose next nudge is due, per CADENCE. Returns (row, days_since_contact, kind)."""
        today = today or datetime.now()
        due = []
        for r in self.db.execute(f"SELECT * FROM jobs WHERE status IN ({','.join('?' * len(CADENCE))})",
                                 tuple(CADENCE)).fetchall():
            first, every, cap = CADENCE[r["status"]]
            n = r["followups"] or 0
            since = r["last_contact"] or r["status_at"] or r["applied_at"]
            if not since:
                continue
            days = (today - datetime.fromisoformat(since)).days
            if cap is not None and n >= cap:
                if r["status"] == "applied" and days >= every:
                    due.append((r, days, "cold: no reply after 2 follow-ups - consider marking rejected"))
                continue
            if days >= (first if n == 0 else every):
                kind = {"applied": "follow-up" if n == 0 else "second follow-up",
                        "interview": "thank-you note" if n == 0 else "check-in",
                        }.get(r["status"], "reply / check-in")
                due.append((r, days, kind))
        return due

    def stats(self):
        return self.db.execute("SELECT status, COUNT(*) n FROM jobs GROUP BY status ORDER BY n DESC").fetchall()

    def funnel(self):
        q = lambda sql, *a: self.db.execute(sql, a).fetchone()[0]
        reached = lambda states: q(f"SELECT COUNT(*) FROM jobs WHERE status IN ({','.join('?' * len(states))})",
                                   *states)
        applied_plus = ("applied", "responded", "assessment", "interview", "offer", "hired", "rejected")
        return {
            "tracked": q("SELECT COUNT(*) FROM jobs"),
            "evaluated": q("SELECT COUNT(*) FROM jobs WHERE rating IS NOT NULL"),
            "applied": q("SELECT COUNT(*) FROM jobs WHERE applied_at IS NOT NULL"),
            "responded": reached(("responded", "assessment", "interview", "offer", "hired")),
            "interview": reached(("interview", "offer", "hired")),
            "offer": reached(("offer", "hired")),
            "rejected": reached(("rejected",)),
            "by_region": self.db.execute(
                f"SELECT COALESCE(region,'-') region, COUNT(*) n FROM jobs WHERE status IN "
                f"({','.join('?' * len(applied_plus))}) GROUP BY region ORDER BY n DESC", applied_plus).fetchall(),
            "by_source": self.db.execute(
                f"SELECT source, COUNT(*) n FROM jobs WHERE status IN ({','.join('?' * len(applied_plus))})"
                " GROUP BY source ORDER BY n DESC", applied_plus).fetchall(),
            "avg_rating_applied": q("SELECT ROUND(AVG(rating),2) FROM jobs WHERE applied_at IS NOT NULL"),
        }

    def export_csv(self, path: Path):
        rows = self.db.execute("SELECT * FROM jobs ORDER BY status, score DESC").fetchall()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(rows[0].keys() if rows else ["id"])
            w.writerows([tuple(r) for r in rows])
        return len(rows)
