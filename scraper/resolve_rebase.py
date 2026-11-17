"""Resolve a rebase conflict between a backfill commit and a scraper commit.

Git's line merge of archive.jsonl fails when both sides rewrite the file.
Posts are united by id, and the backfill cursor keeps whichever side has
walked further back. The site HTML is then rebuilt from that archive.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scraper.archive import (
    load_archive,
    merge_archive_posts,
    merge_backfill_state,
    save_archive,
    save_state,
)
from scraper.build import build_site

_ALLOWED = ("data/archive.jsonl", "data/state.json")


def main() -> int:
    root = Path.cwd()
    try:
        return resolve_rebase(root)
    except subprocess.CalledProcessError as exc:
        print(f"git command failed: {exc}")
        return 1


def resolve_rebase(root: Path) -> int:
    unmerged = _unmerged(root)
    if not unmerged:
        return 0
    for path in unmerged:
        if path not in _ALLOWED and not path.startswith("site/"):
            print(f"fatal conflict in {path}")
            return 2

    if "data/archive.jsonl" in unmerged:
        base = _posts_from_stage(root, "data/archive.jsonl", 2)
        incoming = _posts_from_stage(root, "data/archive.jsonl", 3)
        save_archive(root, merge_archive_posts(base, incoming))
    if "data/state.json" in unmerged:
        base_state = _json_from_stage(root, "data/state.json", 2) or {}
        incoming_state = _json_from_stage(root, "data/state.json", 3) or {}
        save_state(root, merge_backfill_state(base_state, incoming_state))

    for path in unmerged:
        if not path.startswith("site/images/"):
            continue
        if _checkout_stage(root, path, "--theirs") or _checkout_stage(root, path, "--ours"):
            subprocess.run(["git", "add", "--", path], cwd=root, check=True)

    build_site(root)
    subprocess.run(["git", "add", "--", "data", "site"], cwd=root, check=True)
    still = _unmerged(root)
    if still:
        print("unresolved after merge: " + ", ".join(still))
        return 2
    print(f"resolved {len(unmerged)} conflicted path(s); archive has {len(load_archive(root))} posts")
    return 0


def _unmerged(root: Path) -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=U"],
        cwd=root,
        text=True,
    )
    return [line for line in output.splitlines() if line.strip()]


def _posts_from_stage(root: Path, path: str, stage: int) -> dict[int, dict]:
    text = _show_stage(root, path, stage)
    posts: dict[int, dict] = {}
    if not text:
        return posts
    for line in text.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        posts[int(record["id"])] = record
    return posts


def _json_from_stage(root: Path, path: str, stage: int) -> dict | None:
    text = _show_stage(root, path, stage)
    if not text:
        return None
    return json.loads(text)


def _show_stage(root: Path, path: str, stage: int) -> str | None:
    result = subprocess.run(
        ["git", "show", f":{stage}:{path}"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _checkout_stage(root: Path, path: str, which: str) -> bool:
    result = subprocess.run(["git", "checkout", which, "--", path], cwd=root, capture_output=True)
    return result.returncode == 0


if __name__ == "__main__":
    sys.exit(main())
