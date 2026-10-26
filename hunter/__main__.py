"""Job hunter CLI.

    python -m hunter search            # pull remote jobs, score them, write HTML digest
    python -m hunter list              # best unapplied matches
    python -m hunter links --region Australia   # LinkedIn / Indeed / Google / Seek ... searches
    python -m hunter apply --top 10    # walk through top matches in a browser with autofill
    python -m hunter update-cv         # attach your latest CV on each career site
    python -m hunter mark <id> applied
"""
import argparse
import sys
import webbrowser
from pathlib import Path

import yaml

from . import links, matcher, sources
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
    print(f"  {'ID':<9}{'SCORE':>5}  {'REGION':<12} {'STATUS':<9} {'POSTED':<11} JOB")
    for r in rows:
        print(f"  {r['id'][:8]:<9}{r['score']:>5}  {(r['region'] or '-')[:12]:<12} {r['status']:<9} "
              f"{r['posted'] or '':<11} {r['title'][:55]} @ {r['company'][:28]}")


def cmd_search(cfg, tracker, args):
    s = cfg["search"]
    print("Fetching jobs...")
    jobs = sources.collect(s)
    cv = matcher.load_cv_text(cfg["_root"] / cfg["profile"]["resume"]) if cfg["profile"].get("resume") else ""
    cv_tokens = matcher.tokens(cv)
    kept = new = 0
    per_region = {}
    for job in jobs:
        if not matcher.passes(job, s):
            continue
        sc, matched = matcher.score(job, s, cv_tokens)
        if sc < s.get("min_score", 0):
            continue
        rank, region = matcher.match_region(job, s) or (None, None)
        kept += 1
        new += tracker.upsert(job, sc, matched, region, rank)
        per_region[region] = per_region.get(region, 0) + 1
    if s.get("regions"):
        tracker.prune_unplaced()
    print(f"\n{len(jobs)} fetched -> {kept} match your filters -> {new} new")
    for name in s.get("regions") or []:
        label = links.region(name)["label"]
        print(f"  {label:<15} {per_region.get(label, 0)}")
    print("\nTop unapplied matches (region priority, then score):")
    rows = tracker.list("new", s.get("min_score", 0), args.limit)
    print_rows(rows)
    out = write_report(cfg["_root"] / "data" / "digest.html", tracker.list(None, s.get("min_score", 0), 500), cfg)
    print(f"\nDigest: {out}")
    if not args.no_open:
        webbrowser.open(out.as_uri())


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
    print_rows(tracker.list(args.status, args.min_score, args.limit, args.region))


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
        rows = (tracker.list("saved", 0, args.top, args.region)
                + tracker.list("new", 0, args.top, args.region))[: args.top]
    if not rows:
        raise SystemExit("Nothing to apply to. Run `python -m hunter search` first.")
    resume = file_from(cfg, cfg["profile"].get("resume"))
    cover = file_from(cfg, cfg["profile"].get("cover_letter"))
    apply_queue(cfg, rows, tracker, resume, cover)


def cmd_update_cv(cfg, tracker, args):
    from .browser import update_cv_sites
    update_cv_sites(cfg, file_from(cfg, args.file or cfg["profile"].get("resume")))


def cmd_stats(cfg, tracker, args):
    for r in tracker.stats():
        print(f"  {r['status']:<10} {r['n']}")


def cmd_export(cfg, tracker, args):
    path = Path(args.path)
    print(f"Exported {tracker.export_csv(path)} rows to {path.resolve()}")


def main():
    ap = argparse.ArgumentParser(prog="hunter", description="Remote job search + application assistant")
    ap.add_argument("-c", "--config", default=str(ROOT / "config.yaml"))
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
    p.set_defaults(fn=cmd_apply)

    p = sub.add_parser("update-cv", help="attach your latest CV on each career site")
    p.add_argument("--file", help="CV file (defaults to profile.resume)")
    p.set_defaults(fn=cmd_update_cv)

    sub.add_parser("stats", help="counts per status").set_defaults(fn=cmd_stats)

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
