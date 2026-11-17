"""Store, price, coupon, and title extraction from post text."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_DASH = r"[-־–]"
_LOCAL_RE = re.compile(
    rf"(?:בארץ\s+עולה\s+כ{_DASH}|עולה\s+בארץ\s+כ{_DASH}|בארץ\s+כ{_DASH})\s*"
    r"([0-9][0-9.,]*)\s*₪"
)
_MAIN_RE = re.compile(
    rf"(רק ב{_DASH}|החל מ{_DASH})\s*([0-9][0-9.,]*)\s*([\$₪])"
)
_EXTRA_RE = re.compile(
    rf"(?<![\w])ב{_DASH}\s*([0-9][0-9.,]*)\s*([\$₪])"
)
_COUPON_RE = re.compile(
    r"(?:קוד\s+קופון|ואחריו\s+קופון|קוד\s+הנחה|קופון)\s+"
    r"([A-Za-z0-9][A-Za-z0-9-]{3,})"
)


def classify_store(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if "aliexpress" in labels:
        return "aliexpress"
    if host == "ksp.co.il" or host.endswith(".ksp.co.il"):
        return "ksp"
    if "amazon" in labels or "amzn" in labels:
        return "amazon"
    return "other"


def _norm_prefix(prefix: str) -> str:
    if prefix.startswith("החל מ"):
        return "החל מ-"
    if prefix.startswith("רק ב"):
        return "רק ב-"
    return "רק ב-"


def _symbol(raw: str) -> str:
    return "$" if raw == "$" else "₪"


def _currency(raw: str) -> str:
    return "USD" if raw == "$" else "ILS"


def _numeric(amount: str) -> float:
    return float(amount.replace(",", ""))


def extract_prices(text: str) -> dict:
    """Return headline price, local comparison, and every product price found."""
    local = None
    working = text
    found = _LOCAL_RE.search(text)
    if found:
        amount = found.group(1)
        local = {
            "amount": amount,
            "prefix": "בארץ כ-",
            "value": f"{amount}₪",
            "label": f"בארץ כ-{amount}₪",
        }
        working = _LOCAL_RE.sub(" ", working, count=1)

    prices: list[dict] = []
    for match in _MAIN_RE.finditer(working):
        prefix = _norm_prefix(match.group(1))
        amount = match.group(2)
        sym = match.group(3)
        value = f"{amount}{_symbol(sym)}"
        prices.append(
            {
                "amount": amount,
                "currency": _currency(sym),
                "prefix": prefix,
                "value": value,
                "label": f"{prefix}{value}",
                "kind": "main",
            }
        )

    stripped = _MAIN_RE.sub(" ", working)
    for match in _EXTRA_RE.finditer(stripped):
        amount = match.group(1)
        sym = match.group(2)
        value = f"{amount}{_symbol(sym)}"
        prices.append(
            {
                "amount": amount,
                "currency": _currency(sym),
                "prefix": "ב-",
                "value": value,
                "label": f"ב-{value}",
                "kind": "extra",
            }
        )

    headline = _headline(prices)
    return {"prices": prices, "headline": headline, "local": local}


def _headline(prices: list[dict]) -> dict | None:
    if not prices:
        return None
    mains = [price for price in prices if price["kind"] == "main"]
    if mains:
        explicit = [price for price in mains if price["prefix"] == "רק ב-"]
        chosen = explicit[0] if explicit else mains[0]
        return chosen
    if len(prices) == 1:
        price = prices[0]
        return {
            **price,
            "prefix": "רק ב-",
            "label": f"רק ב-{price['value']}",
        }
    lowest = min(prices, key=lambda price: _numeric(price["amount"]))
    return {
        **lowest,
        "prefix": "החל מ-",
        "label": f"החל מ-{lowest['value']}",
    }


def extract_coupons(text: str, code_tag_coupons: list[str] | None = None) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(token: str) -> None:
        cleaned = token.strip().strip(".,:;!)]}*`'\"”׳").strip("\u200e\u200f")
        if len(cleaned) < 4 or cleaned in seen:
            return
        if not re.search(r"[A-Za-z]", cleaned):
            return
        seen.add(cleaned)
        found.append(cleaned)

    for token in code_tag_coupons or []:
        add(token)
    for match in _COUPON_RE.finditer(text):
        add(match.group(1))
    return found


# Two lines on a ~390px phone, wide enough for a full product name
# such as "Anker Soundcore Space Q45" and never cut mid-word.
MAX_TITLE_CHARS = 78

_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\uFE0F"
    "\u200D"
    "]+"
)
_PRODUCT_PRICE_RE = re.compile(
    r"(?:רק ב-|החל מ-|(?<![\w])ב-)\s*[0-9][0-9.,]*\s*(?:\$|₪|£|€)"
)
_HYPE_PREFIXES = {
    "ירידת מחיר",
    "הכי זול שהיה",
    "מגה דיל",
    "דיל מטורף",
    "שימו לב",
    "מבצע",
}
_STORE_HEBREW = {
    "aliexpress": "עלי אקספרס",
    "amazon": "אמזון",
    "ksp": "KSP",
    "other": "החנות",
}


def has_product_price(text: str) -> bool:
    """True when the post names a product price, including £ and €."""
    return _PRODUCT_PRICE_RE.search(text or "") is not None


def is_product_link(url: str) -> bool:
    """A link that points at one product, not a store-wide coupon page."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path or ""
    labels = host.split(".")
    if "ksp" in labels and any(piece in path for piece in ("/item/", "/appkey/", "/mob/")):
        return True
    if "aliexpress" in labels and "/item/" in path:
        return True
    if host == "link.amazon":
        token = path.strip("/").split("/")[0]
        return len(token) >= 8 and token.isalnum()
    if "amazon" in labels and ("/dp/" in path or "/gp/product/" in path):
        return True
    return False


def is_coupon_only(text: str, coupons: list[str] | None, links: list[str] | None) -> bool:
    """Coupon roundups stay on the site, without a לדיל button.

    A post is coupon-only when it has coupon codes and no product price
    (רק ב- / החל מ- / ב- followed by $, ₪, £, or €), and none of its links
    point at a specific product. Campaign shorteners such as
    s.click.aliexpress.com and amzn.to are treated as generic when there
    is no product price, which is how the channel posts store-wide coupon
    lists. A priced product that also has a coupon keeps the button.
    """
    if not coupons:
        return False
    if has_product_price(text or ""):
        return False
    if any(is_product_link(url) for url in links or []):
        return False
    return True


def make_title(text: str, links: list[str], coupons: list[str] | None = None, store: str | None = None) -> str:
    """Short Hebrew title that fits in about two lines, with no ellipsis."""
    cleaned = _clean_title_text(text, links)
    if is_coupon_only(text, coupons, links):
        return _roundup_title(cleaned, store)
    cleaned = _cut_price_clause(cleaned)
    cleaned = _drop_hype_prefix(cleaned)
    cleaned = _cut_price_clause(cleaned)
    cleaned = re.sub(r"\s+ו?עם$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \n\t.,;:|-–—!/")
    return _cap_title(cleaned)


def _clean_title_text(text: str, links: list[str]) -> str:
    cleaned = text or ""
    for url in sorted(set(links or []), key=len, reverse=True):
        cleaned = cleaned.replace(url, " ")
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = _EMOJI_RE.sub("", cleaned)
    cleaned = cleaned.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _cut_price_clause(text: str) -> str:
    cuts = []
    for marker in ("רק ב-", "ועם משלוח", "ומשלוח", "משלוח חינם"):
        index = text.find(marker)
        if index > 0:
            cuts.append(index)
    match = re.search(r"החל מ-\s*[0-9]", text)
    if match and match.start() > 0:
        cuts.append(match.start())
    if not cuts:
        return text
    return text[: min(cuts)].strip()


def _drop_hype_prefix(text: str) -> str:
    while "!" in text:
        head, rest = text.split("!", 1)
        head_s = head.strip()
        rest_s = rest.strip(" !")
        if rest_s and (head_s in _HYPE_PREFIXES or len(head_s) <= 18):
            text = rest_s
            continue
        break
    return text


def _cap_title(text: str, limit: int = MAX_TITLE_CHARS) -> str:
    text = text.strip(" \n\t.,;:|-–—!/")
    if len(text) <= limit:
        return text
    window = text[:limit]
    if " " not in window:
        return text.split(" ", 1)[0]
    return window.rsplit(" ", 1)[0].strip(" \n\t.,;:|-–—!/")


def _roundup_title(text: str, store: str | None) -> str:
    name = _STORE_HEBREW.get(store or "other", "החנות")
    if "יום הרווקים" in text or "11.11" in text:
        return f"יום הרווקים: קופונים חדשים ל{name}"
    if "העשירי לחודש" in text or "מאסטרקארד" in text or "מאסטר קארד" in text:
        return f"העשירי לחודש: קופון ל{name}"
    if "פריים דיי" in text:
        return f"פריים דיי: קופונים ל{name}"
    head = text.split("!")[0].strip()
    if head:
        return _cap_title(head, 60)
    return f"קופונים ל{name}"


def is_deal(message: dict) -> bool:
    """Product posts with a photo and an outbound link. Pins and text-only posts are not deals."""
    if message.get("is_service"):
        return False
    if not message.get("images"):
        return False
    return bool(message.get("affiliate_links"))
