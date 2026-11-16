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


def make_title(text: str, links: list[str]) -> str:
    title = text
    for url in sorted(links, key=len, reverse=True):
        title = title.replace(url, " ")
    title = re.sub(r"\s+", " ", title).strip(" \n\t.,;:|-–—")
    return title


def is_deal(message: dict) -> bool:
    """Product posts with a photo and an outbound link. Pins and text-only posts are not deals."""
    if message.get("is_service"):
        return False
    if not message.get("images"):
        return False
    return bool(message.get("affiliate_links"))
