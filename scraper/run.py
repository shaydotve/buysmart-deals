"""Update and backfill runs. Network fetches stay behind the preview/CDN allowlists."""

from __future__ import annotations

import time
from pathlib import Path

from scraper.archive import load_archive, load_state, merge_page, save_archive, save_state
from scraper.build import build_site
from scraper.fetch import FetchError, fetch_preview_html, is_allowed_image_url
from scraper.images import download_image
from scraper.parse import ParseError, parse_page


def run_update(
    root: Path,
    *,
    pages: int = 2,
    delay: float = 2.0,
    image_delay: float = 0.25,
    fetch=None,
    download=None,
    sleep=None,
) -> dict:
    return _crawl(
        root,
        mode="update",
        pages=pages,
        delay=delay,
        image_delay=image_delay,
        fetch=fetch or fetch_preview_html,
        download=download or download_image,
        sleep=sleep or time.sleep,
        reset=False,
    )


def run_backfill(
    root: Path,
    *,
    pages: int = 25,
    delay: float = 2.0,
    image_delay: float = 0.25,
    reset: bool = False,
    fetch=None,
    download=None,
    sleep=None,
) -> dict:
    return _crawl(
        root,
        mode="backfill",
        pages=pages,
        delay=delay,
        image_delay=image_delay,
        fetch=fetch or fetch_preview_html,
        download=download or download_image,
        sleep=sleep or time.sleep,
        reset=reset,
    )


def _crawl(root, *, mode, pages, delay, image_delay, fetch, download, sleep, reset) -> dict:
    if pages < 1:
        raise ValueError("pages must be at least 1")
    archive = load_archive(root)
    state = load_state(root)
    if mode == "backfill":
        if reset:
            state["backfill_before"] = None
            state["backfill_done"] = False
        if state.get("backfill_done") and not reset:
            summary = _summary(state, {"new": [], "updated": [], "deleted": []})
            summary["skipped"] = True
            print("backfill already complete")
            print(
                "SUMMARY new=0 updated=0 deleted=0 pages=0 changed=false "
                f"backfill_before={state.get('backfill_before')} backfill_done=true"
            )
            return summary

    cursor = None if mode == "update" else state.get("backfill_before")
    totals = {"new": [], "updated": [], "deleted": []}
    fetched = 0
    done = False
    for index in range(pages):
        if index:
            sleep(delay)
        try:
            html = fetch(cursor)
            parsed = parse_page(html)
        except (FetchError, ParseError) as exc:
            print(f"stopped: {exc}")
            raise
        if not parsed.messages:
            print(f"page before={cursor} is empty")
            if mode == "backfill":
                state["backfill_done"] = True
                done = True
            break
        ids = [message["id"] for message in parsed.messages]
        print(
            f"page before={cursor} ids {min(ids)}-{max(ids)} "
            f"messages={len(parsed.messages)} next={parsed.next_before}"
        )
        result = merge_page(archive, parsed.messages, latest=cursor is None)
        for key in totals:
            totals[key].extend(result[key])
        fetched += 1
        nxt = parsed.next_before
        if mode == "backfill":
            if nxt is None or (cursor is not None and nxt >= cursor):
                state["backfill_before"] = nxt
                state["backfill_done"] = True
                done = True
                break
            cursor = nxt
            state["backfill_before"] = cursor
        else:
            if nxt is None:
                break
            cursor = nxt

    force_ids = set(totals["new"]) | set(totals["updated"])
    images_changed = sync_images(
        root,
        archive,
        force_ids,
        download=download,
        delay=image_delay,
        sleep=sleep,
    )
    changed = any(totals.values()) or images_changed or (mode == "backfill" and fetched)
    if changed:
        save_archive(root, archive)
        if mode == "backfill":
            save_state(root, state)
        build_site(root)
    elif mode == "backfill":
        save_state(root, state)

    summary = _summary(state, totals)
    summary["pages"] = fetched
    summary["images_changed"] = images_changed
    summary["changed"] = bool(changed)
    summary["backfill_done"] = bool(state.get("backfill_done"))
    if done:
        summary["backfill_done"] = True
    print(
        "SUMMARY "
        f"new={len(totals['new'])} updated={len(totals['updated'])} "
        f"deleted={len(totals['deleted'])} pages={fetched} "
        f"changed={str(bool(changed)).lower()} "
        f"backfill_before={state.get('backfill_before')} "
        f"backfill_done={str(bool(summary['backfill_done'])).lower()}"
    )
    return summary


def sync_images(root, archive, force_ids, *, download, delay, sleep) -> bool:
    wrote = False
    for post in archive.values():
        if post.get("deleted") or not post.get("is_deal"):
            continue
        force = post["id"] in force_ids
        for image in post.get("images") or []:
            rel = f"images/{image['post_id']}.webp"
            dest = root / "site" / rel
            url = image.get("cdn_url") or ""
            if dest.exists() and not force and image.get("file") == rel:
                continue
            if dest.exists() and not force:
                if image.get("file") != rel:
                    image["file"] = rel
                    wrote = True
                continue
            if not is_allowed_image_url(url):
                print(f"skip non-cdn image on post {post['id']}")
                if image.get("file") is not None:
                    image["file"] = None
                    wrote = True
                continue
            try:
                if delay:
                    sleep(delay)
                download(url, dest)
            except Exception as exc:  # noqa: BLE001 - keep the crawl going
                print(f"image {image['post_id']} failed: {exc}")
                new_file = rel if dest.exists() else None
                if image.get("file") != new_file:
                    image["file"] = new_file
                    wrote = True
                continue
            image["file"] = rel
            wrote = True
    return wrote


def _summary(state: dict, totals: dict) -> dict:
    return {
        "new": len(totals["new"]),
        "updated": len(totals["updated"]),
        "deleted": len(totals["deleted"]),
        "backfill_before": state.get("backfill_before"),
        "backfill_done": bool(state.get("backfill_done")),
        "changed": False,
        "pages": 0,
        "images_changed": False,
        "skipped": False,
    }
