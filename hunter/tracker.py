"""SQLite application tracker so you never apply twice or lose track."""
import csv
import sqlite3
from datetime import datetime
from pathlib import Path

STATUSES = ("new", "saved", "applied", "interview", "offer", "rejected", "skipped")

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
        for col, typ in (("region", "TEXT"), ("region_rank", "INTEGER"), ("description", "TEXT"), ("visa", "TEXT")):
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
        applied = datetime.now().isoformat(timespec="seconds") if status == "applied" else None
        self.db.execute(
            "UPDATE jobs SET status=?, applied_at=COALESCE(?, applied_at),"
            " notes=CASE WHEN ?='' THEN notes ELSE TRIM(notes || ' | ' || ?, ' |') END WHERE id=?",
            (status, applied, note, note, job_id))
        self.db.commit()

    def stats(self):
        return self.db.execute("SELECT status, COUNT(*) n FROM jobs GROUP BY status ORDER BY n DESC").fetchall()

    def export_csv(self, path: Path):
        rows = self.db.execute("SELECT * FROM jobs ORDER BY status, score DESC").fetchall()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(rows[0].keys() if rows else ["id"])
            w.writerows([tuple(r) for r in rows])
        return len(rows)
