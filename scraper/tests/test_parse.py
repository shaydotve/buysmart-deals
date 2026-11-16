from pathlib import Path

from scraper.parse import parse_page

FIXTURES = Path(__file__).parent / "fixtures"


def _by_id(page):
    return {message["id"]: message for message in page.messages}


def test_latest_preview_fixture():
    page = parse_page((FIXTURES / "preview_latest.html").read_text(encoding="utf-8"))
    posts = _by_id(page)
    assert page.next_before == 7922
    assert 7922 in posts and posts[7922]["is_service"] and not posts[7922]["is_deal"]

    bike = posts[7923]
    assert bike["store"] == "aliexpress"
    assert bike["edited"] is True
    assert bike["affiliate_links"] == ["https://s.click.aliexpress.com/e/_c4t9HZS7"]
    assert bike["coupons"] == ["SUPERIL6"]
    assert bike["price_label"] == "רק ב-3,155₪"
    assert bike["local_price_label"] == "בארץ כ-5,500₪"
    assert bike["is_deal"] is True
    assert len(bike["images"]) == 1
    assert bike["images"][0]["post_id"] == 7923
    assert bike["images"][0]["cdn_url"].startswith("https://cdn4.telesco.pe/file/KGKq7Bc2")

    charger = posts[7925]
    assert charger["edited"] is False
    assert charger["coupons"] == ["ILNN04", "ILAFF05"]
    assert charger["price_label"] == "רק ב-27.2$"
    assert charger["affiliate_links"] == ["https://s.click.aliexpress.com/e/_c3Nal2p1"]

    phone = posts[7924]
    assert phone["price_label"] == "רק ב-611$"
    assert phone["coupons"] == ["XU2PHG7P46LE", "SUPERIL6"]
    assert phone["local_price_label"] == "בארץ כ-2,900₪"

    reply = posts[7933]
    assert reply["store"] == "amazon"
    assert reply["reply_to"] == "https://t.me/buysmartorgohome/7918"
    assert reply["price_label"] == "רק ב-152$"
    assert reply["local_price_label"] == "בארץ כ-760₪"
    assert reply["affiliate_links"] == ["https://link.amazon/B01NS74Xr"]
    assert len(reply["images"]) == 1
    assert "t3dK12sY" in reply["images"][0]["cdn_url"]
    assert "EZq7Ie7" not in reply["images"][0]["cdn_url"]

    jacket = posts[7938]
    assert jacket["price_label"] == "החל מ-47.5$"
    assert jacket["store"] == "amazon"

    candles = posts[7939]
    assert candles["coupons"] == []
    assert "2$" not in " ".join(candles["coupons"])

    album = posts[7940]
    assert album["is_album"] is True
    assert [image["post_id"] for image in album["images"]] == [7940, 7941]
    assert album["affiliate_links"] == [
        "https://link.amazon/B0cSAew0P",
        "https://link.amazon/B06ytbLfD",
    ]
    assert album["price_label"] == "החל מ-58.7$"
    assert album["local_price_label"] == "בארץ כ-450₪"
    assert album["is_deal"] is True


def test_extra_posts_ksp_text_only_and_exact_query():
    page = parse_page((FIXTURES / "preview_extra.html").read_text(encoding="utf-8"))
    posts = _by_id(page)

    ksp = posts[7912]
    assert ksp["store"] == "ksp"
    assert ksp["affiliate_links"] == [
        "https://ksp.co.il/appkey/10342/item/364518?utm_source=whatsapp"
    ]
    assert ksp["price_label"] == "רק ב-179₪"
    assert ksp["coupons"] == []
    assert ksp["is_deal"] is True
    assert len(ksp["images"]) == 1

    assert posts[9]["images"] and posts[9]["is_deal"] is False
    assert posts[10]["images"] == [] and posts[10]["is_deal"] is False
    assert posts[11]["affiliate_links"] == ["https://amzn.to/2DLEdds"]
    assert posts[11]["is_deal"] is False
    assert posts[11]["store"] == "amazon"

    adidas = posts[28]
    assert adidas["affiliate_links"] == ["https://www.adidas.co.il/he/men-outlet"]
    assert adidas["store"] == "other"
    assert "ADI30" in adidas["coupons"]


def test_query_string_is_not_rewritten():
    html = """
    <div class="tgme_channel_history"></div>
    <div class="tgme_widget_message" data-post="buysmartorgohome/50">
      <a class="tgme_widget_message_photo_wrap" href="https://t.me/buysmartorgohome/50"
         style="background-image:url('https://cdn4.telesco.pe/file/abc.jpg')"></a>
      <div class="tgme_widget_message_text js-message_text">
        <a href="https://ksp.co.il/t/abc?a=1&amp;b=2">https://ksp.co.il/t/abc?a=1&amp;b=2</a><br>רק ב-10₪
      </div>
      <div class="js-message_footer"><time datetime="2024-01-02T03:04:05+00:00"></time></div>
    </div>
    """
    post = parse_page(html).messages[0]
    assert post["affiliate_links"] == ["https://ksp.co.il/t/abc?a=1&b=2"]
    assert post["is_deal"] is True


def test_non_preview_html_is_rejected():
    try:
        parse_page("<html><body>captcha</body></html>")
    except Exception as exc:
        assert "Telegram" in str(exc)
    else:
        raise AssertionError("expected parse error")
