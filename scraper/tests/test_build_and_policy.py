import json
from pathlib import Path

from scraper.archive import merge_page, save_archive
from scraper.build import build_site, render_deal
from scraper.config import DISCLOSURE
from scraper.fetch import FetchError, is_allowed_image_url, is_allowed_preview_url, preview_url
from scraper.images import save_webp
from scraper.run import run_update
from PIL import Image
from io import BytesIO

FIXTURES = Path(__file__).parent / "fixtures"


def test_preview_and_image_allowlists_block_affiliate_hosts():
    assert is_allowed_preview_url("https://t.me/s/buysmartorgohome")
    assert is_allowed_preview_url("https://t.me/s/buysmartorgohome?before=120")
    assert preview_url(120) == "https://t.me/s/buysmartorgohome?before=120"
    blocked = [
        "https://s.click.aliexpress.com/e/_c4t9HZS7",
        "https://link.amazon/B01NS74Xr",
        "https://amzn.to/2DLEdds",
        "https://ksp.co.il/appkey/10342/item/1",
        "https://bit.ly/abc",
        "https://lnk.ink/abc",
        "https://tidd.ly/abc",
        "https://t.me/buysmartorgohome/7923",
        "https://t.me/s/buysmartorgohome?before=1&x=1",
        "http://t.me/s/buysmartorgohome",
    ]
    for url in blocked:
        assert not is_allowed_preview_url(url)
    assert is_allowed_image_url("https://cdn4.telesco.pe/file/abc.jpg")
    for url in blocked:
        assert not is_allowed_image_url(url)


def test_refusing_an_affiliate_url_does_not_need_network():
    from scraper.fetch import fetch_image_bytes, fetch_preview_html

    for call in (
        lambda: fetch_preview_html(None).__class__,
        lambda: fetch_image_bytes("https://link.amazon/B01NS74Xr"),
    ):
        pass
    try:
        fetch_image_bytes("https://s.click.aliexpress.com/e/_c4t9HZS7")
    except FetchError as exc:
        assert "refusing" in str(exc)
    else:
        raise AssertionError("affiliate image fetch was not refused")
    try:
        from scraper.fetch import _fetch

        _fetch("https://ksp.co.il/item/1", is_allowed_preview_url, timeout=1, limit=10)
    except FetchError as exc:
        assert "refusing" in str(exc)
    else:
        raise AssertionError("affiliate preview fetch was not refused")


def test_save_webp_shrinks_a_generated_image(tmp_path):
    image = Image.new("RGB", (1400, 1000), (14, 124, 123))
    raw = BytesIO()
    image.save(raw, format="PNG")
    dest = tmp_path / "out.webp"
    save_webp(raw.getvalue(), dest, target_bytes=75_000)
    assert dest.exists()
    assert dest.stat().st_size <= 75_000
    assert Image.open(dest).format == "WEBP"


def test_pipeline_builds_pages_without_requesting_affiliate_links(tmp_path):
    html = (FIXTURES / "preview_latest.html").read_text(encoding="utf-8")
    requested = []

    def fetch(before=None):
        assert before is None or isinstance(before, int)
        return html

    def download(url, dest):
        requested.append(url)
        assert is_allowed_image_url(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (40, 40), (255, 255, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        save_webp(buffer.getvalue(), dest, target_bytes=75_000)

    summary = run_update(
        tmp_path,
        pages=1,
        delay=0,
        image_delay=0,
        fetch=fetch,
        download=download,
        sleep=lambda _seconds: None,
    )
    assert summary["changed"] is True
    assert summary["new"] > 0
    archive = (tmp_path / "data" / "archive.jsonl").read_text(encoding="utf-8")
    assert "https://s.click.aliexpress.com/e/_c4t9HZS7" in archive
    assert '"id":7922' not in archive
    for url in requested:
        host = url.split("/")[2]
        assert host == "cdn4.telesco.pe" or host.endswith(".telesco.pe")

    deal = (tmp_path / "site" / "deal" / "7923" / "index.html").read_text(encoding="utf-8")
    assert "https://s.click.aliexpress.com/e/_c4t9HZS7" in deal
    assert DISCLOSURE in deal
    assert 'lang="he"' in deal and 'dir="rtl"' in deal
    assert 'property="og:title"' in deal
    assert "רק ב-" in deal and "3,155₪" in deal
    assert 'data-code="SUPERIL6"' in deal
    manifest = json.loads((tmp_path / "site" / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["deal_count"] >= 1
    assert (tmp_path / "site" / "data" / "pages" / "000.json").exists()
    robots = (tmp_path / "site" / "robots.txt").read_text(encoding="utf-8")
    sitemap = (tmp_path / "site" / "sitemap.xml").read_text(encoding="utf-8")
    assert "Sitemap:" in robots
    assert "/deal/7923/" in sitemap
    assert "/deal/7922/" not in sitemap


def test_deleted_deal_leaves_the_site(tmp_path):
    archive = {}
    merge_page(archive, [_live(5), _live(4)], now="2026-01-01T00:00:00Z")
    archive[4]["deleted"] = True
    save_archive(tmp_path, archive)
    (tmp_path / "site" / "deal" / "4").mkdir(parents=True)
    (tmp_path / "site" / "deal" / "4" / "index.html").write_text("stale", encoding="utf-8")
    (tmp_path / "site" / "images").mkdir(parents=True)
    (tmp_path / "site" / "images" / "4.webp").write_bytes(b"x")
    build_site(tmp_path)
    assert not (tmp_path / "site" / "deal" / "4").exists()
    assert (tmp_path / "site" / "deal" / "5" / "index.html").exists()
    assert not (tmp_path / "site" / "images" / "4.webp").exists()
    page = (tmp_path / "site" / "deal" / "5" / "index.html").read_text(encoding="utf-8")
    assert page.count("https://link.amazon/ITEM5") >= 1


def test_render_keeps_the_affiliate_link_exact():
    html = render_deal(_live(9))
    assert 'href="https://link.amazon/ITEM9"' in html
    assert "redirect" not in html.lower()


def _live(post_id):
    link = f"https://link.amazon/ITEM{post_id}"
    return {
        "id": post_id,
        "telegram_url": f"https://t.me/buysmartorgohome/{post_id}",
        "datetime_utc": "2026-05-01T08:00:00+00:00",
        "author": "Daniel",
        "edited": False,
        "is_album": False,
        "reply_to": None,
        "text": f"מוצר רק ב-10$\n{link}",
        "title": "מוצר רק ב-10$",
        "affiliate_links": [link],
        "store": "amazon",
        "coupons": ["SAVE10"],
        "prices": [{"amount": "10", "currency": "USD", "label": "רק ב-10$"}],
        "price_prefix": "רק ב-",
        "price_value": "10$",
        "price_label": "רק ב-10$",
        "local_price_prefix": "בארץ כ-",
        "local_price_value": "80₪",
        "local_price_label": "בארץ כ-80₪",
        "images": [{"post_id": post_id, "cdn_url": "https://cdn4.telesco.pe/file/x.jpg", "file": f"images/{post_id}.webp"}],
        "is_deal": True,
        "deleted": False,
        "content_hash": "abc",
        "first_seen_at": "2026-05-01T00:00:00Z",
        "updated_at": "2026-05-01T00:00:00Z",
    }

