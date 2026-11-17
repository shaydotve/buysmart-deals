import json
import subprocess
from pathlib import Path

from scraper.archive import merge_archive_posts, merge_backfill_state, save_archive
from scraper.resolve_rebase import resolve_rebase


def test_merge_keeps_both_posts_and_the_newer_edit():
    base = {1: {"id": 1, "text": "ישן", "updated_at": "2026-01-01T00:00:00Z", "images": []}}
    incoming = {
        1: {"id": 1, "text": "חדש", "updated_at": "2026-01-02T00:00:00Z", "images": []},
        2: {"id": 2, "text": "ישן יותר", "updated_at": "2026-01-01T00:00:00Z", "images": []},
    }
    merged = merge_archive_posts(base, incoming)
    assert merged[1]["text"] == "חדש"
    assert merged[2]["text"] == "ישן יותר"


def test_state_merge_keeps_the_further_cursor():
    assert merge_backfill_state(
        {"backfill_before": 7295, "backfill_done": False},
        {"backfill_before": 6800, "backfill_done": False},
    ) == {"backfill_before": 6800, "backfill_done": False}
    assert merge_backfill_state(
        {"backfill_before": None, "backfill_done": True},
        {"backfill_before": 7295, "backfill_done": False},
    ) == {"backfill_before": None, "backfill_done": True}


def test_rebase_conflict_in_archive_jsonl_is_merged(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    data = repo / "data"
    data.mkdir()
    site = repo / "site"
    site.mkdir()
    (site / "index.html").write_text("home", encoding="utf-8")
    _write_archive(repo, {10: _post(10, "בסיס", "2026-01-01T00:00:00Z")})
    (repo / "data" / "state.json").write_text(
        json.dumps({"backfill_before": 8000, "backfill_done": False}, indent=2) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "checkout", "-b", "backfill")
    _git(repo, "checkout", "main")
    _git(repo, "checkout", "-b", "scraper")
    _write_archive(repo, {10: _post(10, "עודכן על ידי הסקרייפר", "2026-01-03T00:00:00Z")})
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "scrape")
    _git(repo, "checkout", "main")
    _git(repo, "merge", "scraper")
    _git(repo, "checkout", "backfill")
    _write_archive(
        repo,
        {
            10: _post(10, "גרסת באקפיל", "2026-01-01T00:00:00Z"),
            9: _post(9, "דיל ישן", "2026-01-02T00:00:00Z"),
        },
    )
    (repo / "data" / "state.json").write_text(
        json.dumps({"backfill_before": 7295, "backfill_done": False}, indent=2) + "\n",
        encoding="utf-8",
    )
    (repo / "site" / "images").mkdir()
    (repo / "site" / "images" / "9.webp").write_bytes(b"webp")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "backfill")

    rebase = subprocess.run(["git", "rebase", "main"], cwd=repo, capture_output=True, text=True)
    assert rebase.returncode != 0
    assert resolve_rebase(repo) == 0
    continued = subprocess.run(
        ["git", "-c", "core.editor=true", "rebase", "--continue"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert continued.returncode == 0, continued.stderr
    posts = {
        json.loads(line)["id"]: json.loads(line)
        for line in (repo / "data" / "archive.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert posts[10]["text"] == "עודכן על ידי הסקרייפר"
    assert posts[9]["text"] == "דיל ישן"
    state = json.loads((repo / "data" / "state.json").read_text(encoding="utf-8"))
    assert state["backfill_before"] == 7295
    assert state["backfill_done"] is False


def _post(post_id: int, text: str, updated: str) -> dict:
    return {
        "id": post_id,
        "text": text,
        "title": text,
        "affiliate_links": [],
        "store": None,
        "coupons": [],
        "images": [],
        "is_deal": True,
        "coupon_only": False,
        "deleted": False,
        "updated_at": updated,
        "content_hash": "abc",
    }


def _write_archive(repo: Path, posts: dict) -> None:
    save_archive(repo, posts)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout


