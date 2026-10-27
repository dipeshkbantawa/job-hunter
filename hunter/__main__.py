"""Job hunter CLI.

    python -m hunter search            # pull remote jobs, score them, write HTML digest
    python -m hunter list              # best unapplied matches
    python -m hunter links --region Australia   # LinkedIn / Indeed / Google / Seek ... searches
    python -m hunter apply --top 10    # walk through top matches in a browser with autofill
    python -m hunter update-cv         # attach your latest CV on each career site
    python -m hunter cv-check          # ATS-friendliness + keyword match vs your jobs
    python -m hunter mark <id> applied
    python -m hunter add <url>         # a job you found yourself (LinkedIn: add --text-file jd.txt)
    python -m hunter live              # are the postings still open?
    python -m hunter cv build          # ATS-safe PDF from cv.yaml
    python -m hunter followups         # who to nudge today
    python -m hunter dashboard         # live tracker dashboard in your browser
Evaluation, tailored CVs, cover letters and messages: open Claude Code here and use /job-hunter.
"""
import argparse
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

import yaml

from . import __version__, links, matcher, sources
from .report import write_report
from .tracker import STATUSES, Tracker

ROOT = Path(__file__).resolve().parent.parent


def load_config(path) -> dict:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"Config not found: {path}\nCopy config.example.yaml to config.yaml and fill it in.")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg.setdefault("profile", {})
    cfg.setdefault("search", {})
    cfg["_root"] = path.resolve().parent
    return cfg


def file_from(cfg, rel):
    if not rel:
        return None
    p = Path(rel)
    p = p if p.is_absolute() else cfg["_root"] / p
    if not p.exists():
        raise SystemExit(f"File not found: {p}")
    return p


def print_rows(rows):
    if not rows:
        print("  (nothing)")
        return
    visa_tag = {"visa+relocation": "VISA+REL", "visa": "VISA", "relocation": "RELOC", "open": "OPEN-INTL",
                "no": "no-visa"}
    print(f"  {'ID':<9}{'SCORE':>5} {'RATE':>4}  {'REGION':<12} {'VISA':<9} {'STATUS':<10} {'POSTED':<11} JOB")
    for r in rows:
        rate = f"{r['rating']:.1f}" if r["rating"] is not None else ""
        print(f"  {r['id'][:8]:<9}{r['score']:>5} {rate:>4}  {(r['region'] or '-')[:12]:<12} "
              f"{visa_tag.get(r['visa'] or '', ''):<9} {r['status']:<10} "
              f"{r['posted'] or '':<11} {r['title'][:52]} @ {r['company'][:26]}")


def blacklisted(cfg, company: str):
    """Your do-not-apply list (config `blacklist`): returns the reason if the company is on it."""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
    for entry in cfg.get("blacklist") or []:
        name, reason = (entry.get("company"), entry.get("reason", "")) if isinstance(entry, dict) else (entry, "")
        if name and norm(name) == norm(company):
            return reason or "on your blacklist"
    return None


def cv_tokens_for(cfg):
    master = cfg["_root"] / "cv.yaml"
    if master.exists():
        from .cvbuild import flatten, load
        return matcher.tokens(flatten(load(master)))
    resume = cfg["profile"].get("resume")
    return matcher.tokens(matcher.load_cv_text(cfg["_root"] / resume) if resume else "")


def job_dir(cfg, row) -> Path:
    """Per-application folder: jd.md, report.md, cv.yaml/pdf, cover.yaml/pdf, answers.md."""
    slug = re.sub(r"[^a-z0-9]+", "-", f"{row['company']}-{row['title']}".lower()).strip("-")[:60]
    d = cfg["_root"] / "applications" / f"{row['id'][:8]}-{slug}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def channel(cfg):
    return (cfg.get("browser") or {}).get("channel", "")


def cmd_search(cfg, tracker, args):
    s = cfg["search"]
    print("Fetching jobs...")
    jobs = sources.collect(s)
    cv_tokens = cv_tokens_for(cfg)
    kept = new = offers = refused = 0
    per_region = {}
    for job in jobs:
        if not matcher.passes(job, s) or blacklisted(cfg, job.company):
            continue
        sc, matched = matcher.score(job, s, cv_tokens)
        if sc < s.get("min_score", 0):
            continue
        rank, region = matcher.match_region(job, s) or (None, None)
        visa = matcher.visa_status(job)
        if visa == "no" and region != "Remote" and s.get("drop_no_sponsorship", True):
            refused += 1   # on-site abroad but the ad rules out sponsoring you
            tracker.forget_new(job.id)
            continue
        offers += visa not in ("", "no")
        kept += 1
        new += tracker.upsert(job, sc, matched, region, rank, visa)
        per_region[region] = per_region.get(region, 0) + 1
    if s.get("regions"):
        tracker.prune_unplaced()
    print(f"\n{len(jobs)} fetched -> {kept} match your filters -> {new} new")
    for name in s.get("regions") or []:
        label = links.region(name)["label"]
        print(f"  {label:<15} {per_region.get(label, 0)}")
    print(f"  visa/relocation offered: {offers}   dropped (ad says no sponsorship): {refused}")
    print("\nTop unapplied matches (region priority, then score):")
    rows = tracker.list("new", s.get("min_score", 0), args.limit)
    print_rows(rows)
    cmd_digest(cfg, tracker, args)


def cmd_digest(cfg, tracker, args):
    due = {r["id"]: f"{kind} ({days}d)" for r, days, kind in tracker.due_followups()}
    rows = tracker.list(None, 0, 1000)
    out = write_report(cfg["_root"] / "data" / "digest.html", rows, cfg, due)
    print(f"\nDigest: {out}")
    if not getattr(args, "no_open", False):
        webbrowser.open(out.as_uri())


def cmd_dashboard(cfg, tracker, args):
    from .dashboard import serve
    serve(cfg, tracker, args.port, not args.no_open)


def cmd_links(cfg, tracker, args):
    s = cfg["search"]
    regions = [args.region] if args.region else s.get("regions") or ["Remote"]
    for reg in regions:
        print(f"\n=== {links.region(reg)['label']}")
        for kw in args.keywords or s.get("keywords") or []:
            print(f"  {kw}")
            for name, url in links.board_links(kw, reg, s.get("max_age_days", 7)).items():
                print(f"    {name:<20} {url}")
                if args.open and name in ("LinkedIn", "Indeed", "Google Jobs"):
                    webbrowser.open(url)
        for c in links.company_pages(cfg, reg):
            print(f"  {'company: ' + c['name']:<22} {c['url']}")


def cmd_list(cfg, tracker, args):
    print_rows(tracker.list(args.status, args.min_score, args.limit, args.region, args.visa))


def cmd_open(cfg, tracker, args):
    webbrowser.open(tracker.get(args.id)["url"])


def cmd_mark(cfg, tracker, args):
    row = tracker.get(args.id)
    tracker.set_status(row["id"], args.status, args.note or "")
    print(f"{row['title']} @ {row['company']} -> {args.status}")


def cmd_apply(cfg, tracker, args):
    from .browser import apply_queue
    if args.ids:
        rows = [tracker.get(i) for i in args.ids]
    else:
        rows = (tracker.list("saved", 0, args.top, args.region, args.visa)
                + tracker.list("new", 0, args.top, args.region, args.visa))[: args.top]
    if not rows:
        raise SystemExit("Nothing to apply to. Run `python -m hunter search` first.")
    resume = file_from(cfg, cfg["profile"].get("resume"))
    cover = file_from(cfg, cfg["profile"].get("cover_letter"))
    apply_queue(cfg, rows, tracker, resume, cover)


def cmd_update_cv(cfg, tracker, args):
    from .browser import update_cv_sites
    update_cv_sites(cfg, file_from(cfg, args.file or cfg["profile"].get("resume")))


def cmd_cv_check(cfg, tracker, args):
    from . import atscheck
    path = file_from(cfg, args.file or cfg["profile"].get("resume"))
    if not path:
        raise SystemExit("No CV: set profile.resume in config.yaml or pass --file")
    res = atscheck.check(path)
    print(f"\nATS check: {path.name}\n")
    for level, title, detail in sorted(res.checks, key=lambda c: ("FAIL", "WARN", "OK").index(c[0])):
        print(f"  [{level:<4}] {title}")
        if detail and level != "OK":
            print(f"         {detail}")
    print(f"\n  Format score: {res.score}/100   (FAIL -15, WARN -5)")

    if args.job:
        rows = [tracker.get(args.job)]
        target = f"{rows[0]['title']} @ {rows[0]['company']}"
    else:
        rows = [r for r in tracker.list(None, 0, args.top, args.region) if r["description"]]
        target = f"your top {len(rows)} tracked jobs" + (f" in {args.region}" if args.region else "")
    texts = [r["description"] for r in rows if r["description"]]
    if not texts:
        print("\n  (No job descriptions stored yet - run `search` first for the keyword check.)")
        return
    gap = atscheck.keyword_gap(res.text, texts, cfg["search"].get("skills") or [])
    have = [g for g in gap if g[2]]
    miss = [g for g in gap if not g[2]]
    total = sum(n for _, n, _ in gap) or 1
    cover = round(100 * sum(n for _, n, ok in gap if ok) / total)
    print(f"\nKeyword match vs {target}: {cover}% of keyword mentions are in your CV")
    print("  In your CV:      " + ", ".join(f"{t} ({n})" for t, n, _ in have[:20]))
    print("  Missing (jobs):  " + ", ".join(f"{t} ({n})" for t, n, _ in miss[:20]))
    print("  Add the missing ones you genuinely have, using the job ad's exact wording.")


def _add_posting(cfg, tracker, p, force=False, quiet=False):
    """Put a fetched/pasted posting into the tracker (source 'manual') and save its JD."""
    from .sources import Job
    s = cfg["search"]
    if not p.title:
        raise SystemExit("Could not read a job title; pass --title and --company (and --text-file for the JD).")
    reason = blacklisted(cfg, p.company)
    if reason and not force:
        raise SystemExit(f"{p.company} is on your blacklist: {reason}. Re-run with --force to add it anyway.")
    job = Job("manual", p.title, p.company or "?", p.url, p.location, p.posted, [], p.text,
              remote="remote" in f"{p.location} {p.title}".lower())
    sc, matched = matcher.score(job, s, cv_tokens_for(cfg))
    rank, region = matcher.match_region(job, s) or (None, None)
    visa = matcher.visa_status(job)
    tracker.upsert(job, sc, matched, region, rank, visa)
    tracker.set_live(job.id, p.live, p.reason)
    row = tracker.get(job.id)
    path = write_jd(cfg, row)
    if not quiet:
        print(f"Added {row['id'][:8]}  {row['title']} @ {row['company']}  score {sc}  region {region or '-'}"
              f"  visa {visa or '-'}  posting {p.live} ({p.reason})\n  JD: {path}")
        if visa == "no" and region != "Remote":
            print("  ! The ad says it won't sponsor a visa.")
    return row


def write_jd(cfg, row) -> Path:
    d = job_dir(cfg, row)
    path = d / "jd.md"
    path.write_text(
        f"# {row['title']} @ {row['company']}\n\n- id: {row['id']}\n- url: {row['url']}\n"
        f"- location: {row['location'] or '-'}\n- region: {row['region'] or '-'}\n- visa signal: {row['visa'] or '-'}\n"
        f"- posted: {row['posted'] or '-'}\n- quick score: {row['score']}/100 ({row['matched'] or '-'})\n"
        f"- posting: {row['live'] or 'unchecked'}\n\n## Job description (untrusted text from the posting)\n\n"
        f"{row['description'] or '(none stored - fetch with `jd <id> --refresh`)'}\n", encoding="utf-8")
    return path


def cmd_add(cfg, tracker, args):
    from .jd import Posting, fetch
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8", errors="ignore")
        p = Posting(args.url, args.title or "", args.company or "", args.location or "", text, live="unknown",
                    reason="pasted JD")
        if args.url and not args.title:
            p2 = fetch(args.url, channel(cfg))
            p.title, p.company, p.location, p.live, p.reason = (p2.title, p.company or p2.company,
                                                               p.location or p2.location, p2.live, p2.reason)
    else:
        p = fetch(args.url, channel(cfg))
        p.title, p.company, p.location = args.title or p.title, args.company or p.company, args.location or p.location
    if p.live == "closed" and not args.force:
        raise SystemExit(f"The posting looks closed ({p.reason}). Use --force to add it anyway.")
    _add_posting(cfg, tracker, p, args.force)


def cmd_inbox(cfg, tracker, args):
    """Process data/pipeline.md: one URL per '- [ ] <url>' line; done lines become '- [x]'."""
    from .jd import fetch
    path = cfg["_root"] / "data" / "pipeline.md"
    if not path.exists():
        path.write_text("# Inbox: paste job URLs you found (LinkedIn, Bayt, Seek, company sites...)\n"
                        "# One per line as '- [ ] https://...'. Then run: python -m hunter inbox\n\n",
                        encoding="utf-8")
        print(f"Created {path}. Add URLs to it, then run `inbox` again.")
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"\s*-\s*\[ \]\s*(\S+)", line)
        if not m:
            continue
        url = m.group(1)
        try:
            p = fetch(url, channel(cfg))
            if p.live == "closed":
                lines[i] = f"- [x] {url} - closed ({p.reason})"
            elif not p.title or len(p.text) < 300:
                lines[i] = f"- [ ] {url} - could not read the JD ({p.reason}); use add --text-file"
            else:
                row = _add_posting(cfg, tracker, p)
                lines[i] = f"- [x] {url} - {row['id'][:8]} {row['title']} @ {row['company']}"
        except SystemExit as e:
            lines[i] = f"- [x] {url} - skipped: {e}"
        print(lines[i])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_jd(cfg, tracker, args):
    row = tracker.get(args.id)
    if args.refresh or not row["description"]:
        from .jd import fetch
        p = fetch(row["url"], channel(cfg), row["company"] if row["source"] == "greenhouse" else "")
        if p.text:
            tracker.db.execute("UPDATE jobs SET description=? WHERE id=?", (p.text[:8000], row["id"]))
            tracker.db.commit()
        tracker.set_live(row["id"], p.live, p.reason)
        row = tracker.get(row["id"])
    print(write_jd(cfg, row))


def cmd_live(cfg, tracker, args):
    from .jd import fetch
    if args.ids:
        rows = [tracker.get(i) for i in args.ids]
    else:
        rows = [r for st in ("evaluated", "saved", "new") for r in tracker.list(st, 0, args.limit)][: args.limit]
    for r in rows:
        p = fetch(r["url"], channel(cfg), r["company"] if r["source"] == "greenhouse" else "")
        tracker.set_live(r["id"], p.live, p.reason)
        print(f"  {r['id'][:8]}  {p.live:<8} {r['title'][:50]} @ {r['company'][:24]}  ({p.reason})")


def cmd_retag(cfg, tracker, args):
    """Re-read stored job ads for visa / foreign-worker signals (after the detection rules change)."""
    from types import SimpleNamespace
    changed = 0
    for r in tracker.list(None, 0, 100000):
        if not r["description"]:
            continue
        visa = matcher.visa_status(SimpleNamespace(description=r["description"]))
        if visa != (r["visa"] or ""):
            tracker.set_visa(r["id"], visa)
            changed += 1
            print(f"  {r['id'][:8]}  {r['visa'] or '-':<15} -> {visa or '-':<15} {r['title'][:50]} @ {r['company']}")
    print(f"Re-tagged {changed} job(s).")


def cmd_record(cfg, tracker, args):
    row = tracker.get(args.id)
    if args.rating is not None and not 1 <= args.rating <= 5:
        raise SystemExit("--rating is 1.0-5.0")
    tracker.record(row["id"], args.rating, args.report, args.cv, args.cover)
    row = tracker.get(row["id"])
    print(f"{row['title']} @ {row['company']}: rating {row['rating']}  status {row['status']}")
    if row["rating"] is not None and row["rating"] < 4.0:
        print("  Rated below 4.0: career-ops' rule is to skip unless you have a specific reason to apply.")


def cmd_cv(cfg, tracker, args):
    from . import atscheck, cvbuild
    master_path = cfg["_root"] / "cv.yaml"
    data_path = Path(args.data) if args.data else master_path
    if not data_path.is_absolute():
        data_path = cfg["_root"] / data_path
    data = cvbuild.load(data_path)
    if data_path.resolve() != master_path.resolve():
        problems = cvbuild.fact_check(data, cvbuild.load(master_path))
        if problems and not args.skip_fact_check:
            print("Fact check FAILED - the tailored CV says things your master CV doesn't:")
            for pr in problems:
                print(f"  - {pr}")
            raise SystemExit("Fix the tailored cv.yaml (reword only, never invent), or --skip-fact-check if it's true.")
        print("Fact check passed: no numbers, employers, titles, dates or certifications beyond your master CV.")
    name = re.sub(r"\W+", "_", data["name"]).strip("_")
    role = re.sub(r"\W+", "_", (data.get("headline") or "CV").split("|")[0].strip()).strip("_")
    out = Path(args.out) if args.out else (data_path.parent / f"{name}_{role}_CV.pdf" if data_path != master_path
                                           else cfg["_root"] / "output" / f"{name}_{role}_CV.pdf")
    cvbuild.to_pdf(cvbuild.render_cv(data), out, channel(cfg))
    res = atscheck.check(out)
    print(f"PDF: {out}\nATS format score: {res.score}/100, {res.pages} page(s)")
    for level, title, detail in res.checks:
        if level != "OK":
            print(f"  [{level}] {title} {detail}")
    if args.job:
        row = tracker.get(args.job)
        tracker.record(row["id"], cv_pdf=str(out))
        print(f"Linked to {row['id'][:8]} {row['title']} @ {row['company']}")


def cmd_cover(cfg, tracker, args):
    from . import cvbuild
    master = cvbuild.load(cfg["_root"] / "cv.yaml")
    data_path = Path(args.data)
    letter = cvbuild.load(data_path)
    extra = sorted(cvbuild._numbers(cvbuild.flatten(letter.get("paragraphs"))) - cvbuild._numbers(cvbuild.flatten(master)))
    extra = [n for n in extra if not re.fullmatch(r"20\d\d|\d{1,2}", n)]
    if extra and not args.skip_fact_check:
        raise SystemExit(f"Fact check FAILED - numbers not in your master CV: {', '.join(extra)}")
    out = data_path.with_suffix(".pdf")
    cvbuild.to_pdf(cvbuild.render_letter(letter, master), out, channel(cfg))
    print(f"Cover letter: {out}")
    if args.job:
        tracker.record(tracker.get(args.job)["id"], cover_pdf=str(out))


def cmd_followups(cfg, tracker, args):
    if args.done:
        row = tracker.get(args.done)
        tracker.followed_up(row["id"])
        print(f"Recorded a follow-up for {row['title']} @ {row['company']} ({(row['followups'] or 0) + 1} so far)")
        return
    due = tracker.due_followups()
    if not due:
        print("  No follow-ups due.")
    for r, days, kind in due:
        print(f"  {r['id'][:8]}  {r['status']:<10} {days:>3}d since contact  {kind:<32} "
              f"{r['title'][:45]} @ {r['company'][:24]}")
    if due:
        print("\n  Draft the messages with Claude Code (`/job-hunter followup`), send them yourself, then record:"
              " python -m hunter followups --done <id>")


def cmd_stats(cfg, tracker, args):
    for r in tracker.stats():
        print(f"  {r['status']:<10} {r['n']}")
    f = tracker.funnel()
    pct = lambda a, b: f"{round(100 * a / b)}%" if b else "-"
    print(f"\n  Funnel: tracked {f['tracked']} -> evaluated {f['evaluated']} -> applied {f['applied']}"
          f" -> responded {f['responded']} ({pct(f['responded'], f['applied'])}) -> interview {f['interview']}"
          f" ({pct(f['interview'], f['applied'])}) -> offer {f['offer']}")
    if f["avg_rating_applied"]:
        print(f"  Average rating of jobs you applied to: {f['avg_rating_applied']}/5")
    if f["by_region"]:
        print("  Applications by region: " + ", ".join(f"{r['region']} {r['n']}" for r in f["by_region"]))
    if f["by_source"]:
        print("  Applications by source: " + ", ".join(f"{r['source']} {r['n']}" for r in f["by_source"]))


def cmd_export(cfg, tracker, args):
    path = Path(args.path)
    print(f"Exported {tracker.export_csv(path)} rows to {path.resolve()}")


def main():
    ap = argparse.ArgumentParser(prog="hunter", description="Remote job search + application assistant")
    ap.add_argument("-c", "--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--version", action="version", version=f"job-hunter {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="fetch, filter and score jobs")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--no-open", action="store_true", help="don't open the HTML digest")
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("links", help="print LinkedIn/Indeed/Google search URLs")
    p.add_argument("keywords", nargs="*")
    p.add_argument("--region", help="only this region, e.g. Australia (default: all regions in config)")
    p.add_argument("--open", action="store_true", help="open LinkedIn, Indeed and Google Jobs in your browser")
    p.set_defaults(fn=cmd_links)

    p = sub.add_parser("list", help="list tracked jobs")
    p.add_argument("--status", choices=STATUSES, default="new")
    p.add_argument("--region", help="e.g. Remote, Australia, Singapore")
    p.add_argument("--visa", action="store_true", help="only jobs offering visa sponsorship / relocation")
    p.add_argument("--min-score", type=int, default=0)
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("open", help="open a job in your browser")
    p.add_argument("id")
    p.set_defaults(fn=cmd_open)

    p = sub.add_parser("mark", help="set a job's status")
    p.add_argument("id")
    p.add_argument("status", choices=STATUSES)
    p.add_argument("--note")
    p.set_defaults(fn=cmd_mark)

    p = sub.add_parser("apply", help="guided applying with autofill (you submit)")
    p.add_argument("ids", nargs="*")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--region", help="only jobs in this region")
    p.add_argument("--visa", action="store_true", help="only jobs offering visa sponsorship / relocation")
    p.set_defaults(fn=cmd_apply)

    p = sub.add_parser("update-cv", help="attach your latest CV on each career site")
    p.add_argument("--file", help="CV file (defaults to profile.resume)")
    p.set_defaults(fn=cmd_update_cv)

    p = sub.add_parser("cv-check", help="check your CV is ATS friendly + keyword match vs your jobs")
    p.add_argument("--file", help="CV file (defaults to profile.resume)")
    p.add_argument("--job", help="compare against one job id instead of your top jobs")
    p.add_argument("--top", type=int, default=40, help="how many top tracked jobs to compare against")
    p.add_argument("--region", help="only compare against jobs in this region")
    p.set_defaults(fn=cmd_cv_check)

    p = sub.add_parser("add", help="add a job you found yourself (URL, or URL + pasted JD text)")
    p.add_argument("url")
    p.add_argument("--text-file", help="file with the pasted job description (needed for LinkedIn)")
    p.add_argument("--title")
    p.add_argument("--company")
    p.add_argument("--location")
    p.add_argument("--force", action="store_true", help="add even if closed or blacklisted")
    p.set_defaults(fn=cmd_add)

    sub.add_parser("inbox", help="add every unchecked URL in data/pipeline.md").set_defaults(fn=cmd_inbox)

    p = sub.add_parser("jd", help="write a job's description to applications/<id>/jd.md")
    p.add_argument("id")
    p.add_argument("--refresh", action="store_true", help="fetch the posting again")
    p.set_defaults(fn=cmd_jd)

    p = sub.add_parser("live", help="check postings are still open; closed ones become 'discarded'")
    p.add_argument("ids", nargs="*")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_live)

    sub.add_parser("retag", help="re-check stored ads for visa / foreign-worker signals").set_defaults(fn=cmd_retag)

    p = sub.add_parser("record", help="store an evaluation rating/report and generated documents")
    p.add_argument("id")
    p.add_argument("--rating", type=float, help="1.0-5.0 fit rating")
    p.add_argument("--report")
    p.add_argument("--cv")
    p.add_argument("--cover")
    p.set_defaults(fn=cmd_record)

    p = sub.add_parser("cv", help="build an ATS-safe CV PDF from cv.yaml (or a tailored copy)")
    p.add_argument("action", choices=["build"])
    p.add_argument("--data", help="tailored cv.yaml (default: master cv.yaml)")
    p.add_argument("--out")
    p.add_argument("--job", help="link the PDF to this job id")
    p.add_argument("--skip-fact-check", action="store_true")
    p.set_defaults(fn=cmd_cv)

    p = sub.add_parser("cover", help="build a cover letter PDF from a cover.yaml")
    p.add_argument("action", choices=["build"])
    p.add_argument("--data", required=True)
    p.add_argument("--job")
    p.add_argument("--skip-fact-check", action="store_true")
    p.set_defaults(fn=cmd_cover)

    p = sub.add_parser("followups", help="applications due a follow-up")
    p.add_argument("--done", metavar="ID", help="record that you sent a follow-up")
    p.set_defaults(fn=cmd_followups)

    p = sub.add_parser("digest", help="rebuild data/digest.html from the tracker (no fetching)")
    p.add_argument("--no-open", action="store_true")
    p.set_defaults(fn=cmd_digest)

    p = sub.add_parser("dashboard", help="live tracker dashboard on http://127.0.0.1 (status tabs, reports, status changes)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-open", action="store_true")
    p.set_defaults(fn=cmd_dashboard)

    sub.add_parser("stats", help="counts per status + funnel").set_defaults(fn=cmd_stats)

    p = sub.add_parser("export", help="export tracker to CSV")
    p.add_argument("path", nargs="?", default="applications.csv")
    p.set_defaults(fn=cmd_export)

    args = ap.parse_args()
    cfg = load_config(args.config)
    tracker = Tracker(cfg["_root"] / "data" / "jobs.db")
    try:
        args.fn(cfg, tracker, args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
