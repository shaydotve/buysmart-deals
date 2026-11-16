from scraper.extract import classify_store, extract_coupons, extract_prices, make_title


def test_price_patterns_from_the_channel():
    bike = extract_prices("אופניים, רק ב-3,155₪ ומשלוח חינם! הדגם הזה עולה בארץ כ-5,500₪")
    assert bike["headline"]["label"] == "רק ב-3,155₪"
    assert bike["headline"]["currency"] == "ILS"
    assert bike["local"]["label"] == "בארץ כ-5,500₪"
    assert all(price["amount"] != "5,500" for price in bike["prices"])

    phone = extract_prices("סמארטפון, רק ב-611$ ומשלוח חינם!")
    assert phone["headline"]["label"] == "רק ב-611$"
    assert phone["headline"]["currency"] == "USD"

    jacket = extract_prices("ג'קט, החל מ-47.5$ ומשלוח חינם בהזמנה מעל 49$!")
    assert jacket["headline"]["label"] == "החל מ-47.5$"
    assert [price["amount"] for price in jacket["prices"]] == ["47.5"]

    local_first = extract_prices("מנקה חלונות, רק ב-152$ כולל מיסים! בארץ עולה כ-2,900₪")
    assert local_first["headline"]["label"] == "רק ב-152$"
    assert local_first["local"]["label"] == "בארץ כ-2,900₪"


def test_album_prices_use_starting_from_the_lowest():
    album = extract_prices("צבע ורוד ב-58.7$\nצבע Earl Grey ב-59.8$\nבארץ עולה כ-450₪")
    assert album["headline"]["label"] == "החל מ-58.7$"
    assert album["local"]["label"] == "בארץ כ-450₪"
    assert [price["amount"] for price in album["prices"]] == ["58.7", "59.8"]


def test_single_bare_price_uses_rak_be():
    parsed = extract_prices("צבע שחור ב-20$")
    assert parsed["headline"]["label"] == "רק ב-20$"


def test_shipping_threshold_is_not_the_product_price():
    parsed = extract_prices("רק ב-36$ ומשלוח חינם בהזמנה מעל 49$!")
    assert parsed["headline"]["label"] == "רק ב-36$"
    assert [price["amount"] for price in parsed["prices"]] == ["36"]


def test_coupons_from_code_tags_and_plain_text():
    text = "תזינו קוד קופון ILNN04 ואחריו קופון ILAFF05."
    assert extract_coupons(text, []) == ["ILNN04", "ILAFF05"]
    assert extract_coupons("תזינו קוד קופון SUPERIL6", ["SUPERIL6"]) == ["SUPERIL6"]
    assert extract_coupons("הקוד הנחה ADI30 תהנו", []) == ["ADI30"]


def test_discount_amount_is_not_a_coupon():
    text = "סמנו קופון 2$ הנחה בדף המוצר"
    assert extract_coupons(text, []) == []


def test_store_domains():
    assert classify_store("https://s.click.aliexpress.com/e/_c4t9HZS7") == "aliexpress"
    assert classify_store("https://link.amazon/B01NS74Xr") == "amazon"
    assert classify_store("https://amzn.to/2DLEdds") == "amazon"
    assert classify_store("https://ksp.co.il/appkey/10342/item/364518?utm_source=whatsapp") == "ksp"
    assert classify_store("https://ksp.co.il/t/abc") == "ksp"
    assert classify_store("https://ksp.co.il/mob/item/12") == "ksp"
    assert classify_store("https://www.adidas.co.il/he/men-outlet") == "other"
    assert classify_store("https://bit.ly/abc") == "other"
    assert classify_store("https://lnk.ink/abc") == "other"
    assert classify_store("https://tidd.ly/abc") == "other"
    assert classify_store("https://notamazon.com/deal") == "other"


def test_title_drops_the_raw_url():
    url = "https://s.click.aliexpress.com/e/_c4t9HZS7"
    title = make_title(f"{url}\nירידת מחיר! אופניים", [url])
    assert title == "ירידת מחיר! אופניים"
    assert url not in title
