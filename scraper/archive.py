"""Archive merge: content hashes, edits, and deleted posts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

_RECORD_FIELDS = (
    "id",
    "telegram_url",
    "datetime_utc",
    "author",
    "edited",
    "is_album",
    "reply_to",
    "text",
    "title",
    "affiliate_links",
    "store",
    "coupons",
    "prices",
    "price_prefix",
    "price_value",
    "price_label",
    "local_price_prefix",
    "local_price_value",
    "local_price_label",
    "images",
    "is_deal",
    "deleted",
    "content_hash",
    "first_seen_at",
    "updated_at",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def content_hash(message: dict) -> str:
    payload = {
        "text": message.get("text") or "",
        "links": message.get("affiliate_links") or [],
        "image_ids": [image["post_id"] for image in message.get("images") or []],
        "edited": bool(message.get("edited")),
        "datetime_utc": message.get("datetime_utc"),
        "reply_to": message.get("reply_to"),
        "coupons": message.get("coupons") or [],
        "price_label": message.get("price_label"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def archive_path(root: Path) -> Path:
    return root / "data" / "archive.jsonl"


def state_path(root: Path) -> Path:
    return root / "data" / "state.json"


def load_archive(root: Path) -> dict[int, dict]:
    path = archive_path(root)
    posts: dict[int, dict] = {}
    if not path.exists():
        return posts
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        posts[int(record["id"])] = record
    return posts


def save_archive(root: Path, posts: dict[int, dict]) -> None:
    path = archive_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({key: posts[post_id].get(key) for key in _RECORD_FIELDS}, ensure_ascii=False, separators=(",", ":"))
        for post_id in sorted(posts)
    ]
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")


def load_state(root: Path) -> dict:
    path = state_path(root)
    if not path.exists():
        return {"backfill_before": None, "backfill_done": False}
    state = json.loads(path.read_text(encoding="utf-8"))
    state.setdefault("backfill_before", None)
    state.setdefault("backfill_done", False)
    return state


def save_state(root: Path, state: dict) -> None:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "backfill_before": state.get("backfill_before"),
        "backfill_done": bool(state.get("backfill_done")),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def merge_page(archive: dict[int, dict], messages: list[dict], now: str | None = None, *, latest: bool = False) -> dict:
    """Insert, update, and mark deletions inside one preview page.

    Service messages are skipped but still count toward the id window, so a
    deleted deal between them can be detected. Album photo ids are not separate posts.
    On the latest page, an id newer than every message currently published is gone.
    """
    now = now or utcnow()
    result = {"new": [], "updated": [], "deleted": [], "unchanged": []}
    if not messages:
        return result

    page_ids = [message["id"] for message in messages]
    low, high = min(page_ids), max(page_ids)
    present: set[int] = set()
    album_ids: set[int] = set()
    for message in messages:
        for image in message.get("images") or []:
            album_ids.add(image["post_id"])
        if message.get("is_service"):
            continue
        present.add(message["id"])
        record = _record_from_message(message, now)
        previous = archive.get(message["id"])
        if previous is None:
            archive[message["id"]] = record
            result["new"].append(message["id"])
            continue
        record["first_seen_at"] = previous.get("first_seen_at") or record["first_seen_at"]
        _keep_image_files(previous, record)
        if previous.get("content_hash") != record["content_hash"] or previous.get("deleted"):
            archive[message["id"]] = record
            result["updated"].append(message["id"])
        else:
            result["unchanged"].append(message["id"])

    for post_id, post in archive.items():
        if post_id in present or post_id in album_ids or post.get("deleted"):
            continue
        inside = low <= post_id <= high
        newer_than_latest = latest and post_id > high
        if inside or newer_than_latest:
            post["deleted"] = True
            post["updated_at"] = now
            result["deleted"].append(post_id)
    return result


def _record_from_message(message: dict, now: str) -> dict:
    record = {
        "id": message["id"],
        "telegram_url": message["telegram_url"],
        "datetime_utc": message.get("datetime_utc"),
        "author": message.get("author"),
        "edited": bool(message.get("edited")),
        "is_album": bool(message.get("is_album")),
        "reply_to": message.get("reply_to"),
        "text": message.get("text") or "",
        "title": message.get("title") or "",
        "affiliate_links": list(message.get("affiliate_links") or []),
        "store": message.get("store"),
        "coupons": list(message.get("coupons") or []),
        "prices": list(message.get("prices") or []),
        "price_prefix": message.get("price_prefix"),
        "price_value": message.get("price_value"),
        "price_label": message.get("price_label"),
        "local_price_prefix": message.get("local_price_prefix"),
        "local_price_value": message.get("local_price_value"),
        "local_price_label": message.get("local_price_label"),
        "images": [
            {"post_id": image["post_id"], "cdn_url": image["cdn_url"], "file": image.get("file")}
            for image in message.get("images") or []
        ],
        "is_deal": bool(message.get("is_deal")),
        "deleted": False,
        "first_seen_at": now,
        "updated_at": now,
    }
    record["content_hash"] = content_hash(record)
    return record


def _keep_image_files(previous: dict, record: dict) -> None:
    previous_files = {
        image["post_id"]: image.get("file")
        for image in previous.get("images") or []
        if image.get("cdn_url")
    }
    previous_urls = {image["post_id"]: image.get("cdn_url") for image in previous.get("images") or []}
    for image in record["images"]:
        if previous_urls.get(image["post_id"]) == image["cdn_url"]:
            image["file"] = previous_files.get(image["post_id"])
