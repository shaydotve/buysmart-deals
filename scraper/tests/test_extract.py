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


def test_title_drops_the_raw_url_and_the_hype_prefix():
    url = "https://s.click.aliexpress.com/e/_c4t9HZS7"
    title = make_title(f"{url}\nירידת מחיר! אופניים חשמליים Jager Dorf, רק ב-3,155₪", [url])
    assert title == "אופניים חשמליים Jager Dorf"
    assert url not in title
    assert "…" not in title and "..." not in title


def test_product_title_stops_before_the_price():
    text = (
        "אוזניות קשת אלחוטיות עם ביטול רעשים אדפטיבי Anker Soundcore Space Q45, "
        "רק ב-54.1$ ומשלוח חינם! תזינו קוד קופון ANA3040"
    )
    title = make_title(text, [], coupons=["ANA3040"], store="aliexpress")
    assert title == "אוזניות קשת אלחוטיות עם ביטול רעשים אדפטיבי Anker Soundcore Space Q45"
    assert "רק ב-" not in title
    assert len(title) <= 78


def test_shipping_clause_does_not_leave_a_dangling_vav():
    text = "תיקי גב Osprey Axis בנפח 24 ליטר מתחת לרף המס ועם משלוח חינם! צבע ורוד ב-58.7$"
    assert make_title(text, []) == "תיקי גב Osprey Axis בנפח 24 ליטר מתחת לרף המס"


def test_long_title_caps_on_a_word_boundary_without_ellipsis():
    words = " ".join(["מילה"] * 30)
    title = make_title(words + ", רק ב-10$", [])
    assert "…" not in title and "..." not in title
    assert len(title) <= 78
    assert not title.endswith("מיל")
    assert title.endswith("מילה")


def test_coupon_roundup_title_and_button_flag():
    from scraper.extract import is_coupon_only

    text = (
        "יום הרווקים שמח! עלי אקספרס מחדשים קופונים ומורידים מחירים להמון מוצרים הבוקר! "
        "קופון 2$ בקנייה מעל 15$ ILAFF02"
    )
    link = ["https://s.click.aliexpress.com/e/_c3fhMu5t"]
    coupons = ["ILAFF02"]
    assert is_coupon_only(text, coupons, link)
    assert make_title(text, link, coupons=coupons, store="aliexpress") == "יום הרווקים: קופונים חדשים לעלי אקספרס"

    mastercard = "העשירי לחודש הגיע! החל מ-10 בבוקר, 10% הנחה עם קוד קופון MASTERCARDAY"
    assert is_coupon_only(mastercard, ["MASTERCARDAY"], ["https://amzn.to/3HTImd3"])
    assert make_title(mastercard, ["https://amzn.to/3HTImd3"], coupons=["MASTERCARDAY"], store="amazon") == (
        "העשירי לחודש: קופון לאמזון"
    )


def test_priced_product_keeps_the_deal_button_even_in_pounds():
    from scraper.extract import is_coupon_only

    text = "זוג רמקולים House of Marley, רק ב-125.1£ כולל דמי משלוח"
    assert not is_coupon_only(text, [], ["https://amzn.to/3ZeuTVx"])
    product_with_coupon = "אוזניות Anker, רק ב-54.1$ ומשלוח חינם! קוד קופון ANA3040"
    assert not is_coupon_only(product_with_coupon, ["ANA3040"], ["https://s.click.aliexpress.com/e/_abc"])
    assert make_title(product_with_coupon, [], coupons=["ANA3040"], store="aliexpress") == "אוזניות Anker"
