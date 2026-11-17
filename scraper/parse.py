"""Parse a public Telegram channel preview page."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from scraper.config import CHANNEL_URL
from scraper.extract import (
    classify_store,
    extract_coupons,
    extract_prices,
    is_coupon_only,
    is_deal,
    make_title,
)

_BG_RE = re.compile(r"background-image\s*:\s*url\(\s*(['\"]?)(https://[^)'\"]+)\1\s*\)")
_POST_RE = re.compile(r"/(\d+)$")
_BEFORE_RE = re.compile(r"[?&]before=(\d+)")


class ParseError(ValueError):
    """The document is not a Telegram channel preview."""


@dataclass
class ParsedPage:
    messages: list[dict]
    next_before: int | None


def parse_page(html: str) -> ParsedPage:
    if "tgme_widget_message" not in html and "tgme_channel_history" not in html:
        raise ParseError("response is not a Telegram channel preview")
    soup = BeautifulSoup(html, "html.parser")
    messages = []
    for node in soup.select("div.tgme_widget_message[data-post]"):
        parsed = _parse_message(node)
        if parsed is not None:
            messages.append(parsed)
    return ParsedPage(messages=messages, next_before=_next_before(soup))


def _next_before(soup: BeautifulSoup) -> int | None:
    link = soup.find("link", rel=lambda value: value and "prev" in value)
    if link is None or not link.get("href"):
        return None
    match = _BEFORE_RE.search(link["href"])
    if not match:
        return None
    return int(match.group(1))


def _parse_message(node) -> dict | None:
    match = _POST_RE.search((node.get("data-post") or "").strip())
    if not match:
        return None
    post_id = int(match.group(1))
    classes = node.get("class") or []
    is_service = "service_message" in classes
    footer = node.select_one(".js-message_footer")
    footer_text = footer.get_text(" ", strip=True) if footer else ""
    time_el = footer.select_one("time") if footer else None
    author_el = footer.select_one(".tgme_widget_message_from_author") if footer else None
    reply = node.select_one("a.tgme_widget_message_reply")
    text_node = _message_text_node(node)
    text = _plain_text(text_node) if text_node else ""
    code_coupons = [code.get_text(strip=True) for code in text_node.find_all("code")] if text_node else []
    links = _affiliate_links(text_node)
    images = _images(node, post_id)
    prices = extract_prices(text)
    headline = prices["headline"]
    local = prices["local"]
    coupons = extract_coupons(text, code_coupons)
    store = classify_store(links[0]) if links else None
    message = {
        "id": post_id,
        "telegram_url": f"{CHANNEL_URL}/{post_id}",
        "datetime_utc": time_el.get("datetime") if time_el and time_el.get("datetime") else None,
        "author": author_el.get_text(strip=True) if author_el else None,
        "edited": "edited" in footer_text.lower(),
        "is_service": is_service,
        "is_album": len(images) > 1,
        "reply_to": reply.get("href") if reply and reply.get("href") else None,
        "text": text,
        "title": make_title(text, links, coupons=coupons, store=store),
        "affiliate_links": links,
        "store": store,
        "coupons": coupons,
        "coupon_only": is_coupon_only(text, coupons, links),
        "prices": [
            {"amount": price["amount"], "currency": price["currency"], "label": price["label"]}
            for price in prices["prices"]
        ],
        "price_prefix": headline["prefix"] if headline else None,
        "price_value": headline["value"] if headline else None,
        "price_label": headline["label"] if headline else None,
        "local_price_prefix": local["prefix"] if local else None,
        "local_price_value": local["value"] if local else None,
        "local_price_label": local["label"] if local else None,
        "images": images,
    }
    message["is_deal"] = is_deal(message)
    return message


def _message_text_node(node):
    for div in node.select("div.tgme_widget_message_text"):
        if "js-message_text" in (div.get("class") or []):
            return div
    return None


def _plain_text(node) -> str:
    parts: list[str] = []

    def walk(element) -> None:
        for child in element.children:
            name = getattr(child, "name", None)
            if name == "br":
                parts.append("\n")
            elif name:
                walk(child)
            else:
                parts.append(str(child))

    walk(node)
    text = "".join(parts).replace("\u00a0", " ").replace("\r", "")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    collapsed = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", collapsed).strip()


def _affiliate_links(text_node) -> list[str]:
    if text_node is None:
        return []
    links: list[str] = []
    seen: set[str] = set()
    for anchor in text_node.find_all("a", href=True):
        href = anchor["href"].strip()
        if not _is_affiliate_href(href) or href in seen:
            continue
        seen.add(href)
        links.append(href)
    return links


def _is_affiliate_href(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if host in {"t.me", "telegram.me", "telegram.org"} or host.endswith(".t.me"):
        return False
    return True


def _images(node, fallback_id: int) -> list[dict]:
    images: list[dict] = []
    seen: set[int] = set()
    for anchor in node.select("a.tgme_widget_message_photo_wrap"):
        if anchor.find_parent(class_="tgme_widget_message_reply"):
            continue
        style = anchor.get("style") or ""
        match = _BG_RE.search(style)
        if not match:
            continue
        href = anchor.get("href") or ""
        id_match = re.search(r"/(\d+)", href)
        photo_id = int(id_match.group(1)) if id_match else fallback_id
        if photo_id in seen:
            continue
        seen.add(photo_id)
        images.append(
            {
                "post_id": photo_id,
                "cdn_url": match.group(2),
                "file": None,
            }
        )
    return images
