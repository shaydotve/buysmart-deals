"""CLI: python -m scraper update|backfill|build|smoke"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scraper.archive import load_archive
from scraper.build import build_site
from scraper.run import run_backfill, run_update
from scraper.smoke import main as smoke_main

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scraper", description="Mirror צרכנות נבונה into the static site")
    sub = parser.add_subparsers(dest="command", required=True)

    update = sub.add_parser("update", help="Fetch the newest preview pages")
    update.add_argument("--pages", type=int, default=2)
    update.add_argument("--delay", type=float, default=2.0)
    update.add_argument("--image-delay", type=float, default=0.25)

    backfill = sub.add_parser("backfill", help="Resume a historical crawl toward post 1")
    backfill.add_argument("--pages", type=int, default=25)
    backfill.add_argument("--delay", type=float, default=2.0)
    backfill.add_argument("--image-delay", type=float, default=0.25)
    backfill.add_argument("--reset", action="store_true")

    sub.add_parser("build", help="Rebuild the site from data/archive.jsonl")
    sub.add_parser("smoke", help="Check that the Telegram preview is reachable")

    args = parser.parse_args(argv)
    if args.command == "smoke":
        return smoke_main()
    if args.command == "build":
        manifest = build_site(ROOT)
        print(f"deals={manifest['deal_count']} pages={manifest['page_count']}")
        return 0
    runner = run_update if args.command == "update" else run_backfill
    kwargs = {
        "pages": args.pages,
        "delay": args.delay,
        "image_delay": args.image_delay,
    }
    if args.command == "backfill":
        kwargs["reset"] = args.reset
    summary = runner(ROOT, **kwargs)
    print(f"archive={len(load_archive(ROOT))} changed={str(summary['changed']).lower()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
