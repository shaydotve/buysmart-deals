from scraper.archive import content_hash, merge_page


def _message(post_id, text="דיל", link="https://link.amazon/ABC", images=None, **extra):
    images = images if images is not None else [{"post_id": post_id, "cdn_url": f"https://cdn4.telesco.pe/file/{post_id}.jpg", "file": None}]
    message = {
        "id": post_id,
        "telegram_url": f"https://t.me/buysmartorgohome/{post_id}",
        "datetime_utc": "2026-01-01T00:00:00+00:00",
        "author": "Daniel",
        "edited": False,
        "is_service": False,
        "is_album": len(images) > 1,
        "reply_to": None,
        "text": text,
        "title": text,
        "affiliate_links": [link] if link else [],
        "store": "amazon" if link else None,
        "coupons": [],
        "prices": [],
        "price_prefix": "רק ב-",
        "price_value": "10$",
        "price_label": "רק ב-10$",
        "local_price_prefix": None,
        "local_price_value": None,
        "local_price_label": None,
        "images": images,
        "is_deal": bool(images and link),
    }
    message.update(extra)
    return message


def test_merge_adds_updates_and_marks_deleted():
    archive = {}
    first = merge_page(archive, [
        _message(3),
        _message(2),
        _message(1, text="שירות", link=None, images=[], is_service=True, is_deal=False),
    ], now="2026-01-01T00:00:00Z")
    assert first["new"] == [3, 2]
    assert 1 not in archive
    assert archive[3]["first_seen_at"] == "2026-01-01T00:00:00Z"

    again = merge_page(archive, [_message(3), _message(2)], now="2026-01-02T00:00:00Z")
    assert again["new"] == [] and again["updated"] == []
    assert archive[3]["updated_at"] == "2026-01-01T00:00:00Z"

    edited = _message(3, text="דיל מעודכן", edited=True)
    updated = merge_page(archive, [_message(4), edited, _message(2)], now="2026-01-03T00:00:00Z")
    assert 3 in updated["updated"]
    assert archive[3]["text"] == "דיל מעודכן"
    assert archive[3]["first_seen_at"] == "2026-01-01T00:00:00Z"
    assert archive[2]["deleted"] is False
    assert content_hash(archive[3]) != content_hash(_message(3))


def test_gap_inside_a_page_and_a_removed_newest_post_are_deleted():
    archive = {}
    merge_page(archive, [_message(8), _message(7), _message(6)], now="2026-01-01T00:00:00Z")
    merge_page(archive, [_message(8), _message(6)], now="2026-01-02T00:00:00Z")
    assert archive[7]["deleted"] is True
    merge_page(archive, [_message(8), _message(6)], now="2026-01-03T00:00:00Z", latest=True)
    assert archive[8]["deleted"] is False
    merge_page(archive, [_message(6)], now="2026-01-04T00:00:00Z", latest=True)
    assert archive[8]["deleted"] is True


def test_album_photo_ids_are_not_marked_deleted():
    archive = {}
    album = _message(
        20,
        images=[
            {"post_id": 20, "cdn_url": "https://cdn4.telesco.pe/file/a.jpg", "file": None},
            {"post_id": 21, "cdn_url": "https://cdn4.telesco.pe/file/b.jpg", "file": None},
        ],
    )
    merge_page(archive, [album, _message(22)], now="2026-01-01T00:00:00Z")
    assert set(archive) == {20, 22}
    merge_page(archive, [album, _message(22)], now="2026-01-02T00:00:00Z")
    assert archive[20]["deleted"] is False
    assert 21 not in archive


def test_deleted_post_returns():
    archive = {}
    merge_page(archive, [_message(8), _message(7), _message(6)], now="2026-01-01T00:00:00Z")
    merge_page(archive, [_message(8), _message(6)], now="2026-01-02T00:00:00Z")
    assert archive[7]["deleted"] is True
    merge_page(archive, [_message(8), _message(7), _message(6)], now="2026-01-03T00:00:00Z")
    assert archive[7]["deleted"] is False
