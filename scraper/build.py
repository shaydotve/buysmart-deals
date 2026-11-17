"""Write the static site from the archive: feed pages, deal HTML, sitemap, robots."""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from scraper.config import CHANNEL_NAME, CHANNEL_URL, DISCLOSURE, PAGE_SIZE, SITE_ORIGIN, STORE_LABELS
from scraper.extract import is_coupon_only, is_deal, make_title

_MONTHS = (
    "ינואר",
    "פברואר",
    "מרץ",
    "אפריל",
    "מאי",
    "יוני",
    "יולי",
    "אוגוסט",
    "ספטמבר",
    "אוקטובר",
    "נובמבר",
    "דצמבר",
)


def build_site(root: Path) -> dict:
    from scraper.archive import load_archive

    archive = load_archive(root)
    deals = [post for post in archive.values() if _public_deal(post)]
    deals.sort(key=lambda post: (post.get("datetime_utc") or "", post["id"]), reverse=True)

    pages_dir = root / "site" / "data" / "pages"
    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)

    cards = [_card(post) for post in deals]
    page_count = 0
    for index in range(0, len(cards), PAGE_SIZE):
        chunk = cards[index : index + PAGE_SIZE]
        payload = {"page": page_count, "deals": chunk}
        _write_json(pages_dir / f"{page_count:03d}.json", payload)
        page_count += 1

    stores = []
    for key in ("amazon", "aliexpress", "ksp", "other"):
        if any(card["store"] == key for card in cards):
            stores.append(key)
    newest = deals[0]["datetime_utc"] if deals else None
    manifest = {
        "generated_at": newest,
        "channel_url": CHANNEL_URL,
        "channel_name": CHANNEL_NAME,
        "page_size": PAGE_SIZE,
        "page_count": page_count,
        "deal_count": len(deals),
        "stores": stores,
        "origin": SITE_ORIGIN,
    }
    _write_json(root / "site" / "data" / "manifest.json", manifest)

    deal_root = root / "site" / "deal"
    live_ids = {post["id"] for post in deals}
    if deal_root.exists():
        for child in deal_root.iterdir():
            if child.is_dir() and (not child.name.isdigit() or int(child.name) not in live_ids):
                shutil.rmtree(child)
    for post in deals:
        page = deal_root / str(post["id"]) / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(render_deal(post), encoding="utf-8")

    _clean_images(root, deals)
    (root / "site" / "robots.txt").write_text(_robots(), encoding="utf-8")
    (root / "site" / "sitemap.xml").write_text(_sitemap(deals), encoding="utf-8")
    return manifest


def _public_deal(post: dict) -> bool:
    if post.get("deleted"):
        return False
    return is_deal(post)


def _card(post: dict) -> dict:
    files = [image.get("file") for image in post.get("images") or [] if image.get("file")]
    return {
        "id": post["id"],
        "date": post.get("datetime_utc"),
        "store": post.get("store") or "other",
        "store_label": STORE_LABELS.get(post.get("store") or "other", "אחר"),
        "title": _display_title(post),
        "text": post.get("text") or "",
        "price_prefix": post.get("price_prefix"),
        "price_value": post.get("price_value"),
        "price_label": post.get("price_label"),
        "local_prefix": post.get("local_price_prefix"),
        "local_value": post.get("local_price_value"),
        "local_label": post.get("local_price_label"),
        "coupons": post.get("coupons") or [],
        "image": files[0] if files else None,
        "image_count": len(files),
        "coupon_only": _coupon_only(post),
        "link": None if _coupon_only(post) else (post.get("affiliate_links") or [None])[0],
        "links": post.get("affiliate_links") or [],
        "edited": bool(post.get("edited")),
        "reply_to": post.get("reply_to"),
    }


def _display_title(post: dict) -> str:
    return make_title(
        post.get("text") or "",
        post.get("affiliate_links") or [],
        coupons=post.get("coupons") or [],
        store=post.get("store"),
    )


def _coupon_only(post: dict) -> bool:
    return is_coupon_only(
        post.get("text") or "",
        post.get("coupons") or [],
        post.get("affiliate_links") or [],
    )


def render_deal(post: dict) -> str:
    title = _display_title(post) or CHANNEL_NAME
    short = isolate_prices(title)
    page_title = f"{short} · {CHANNEL_NAME}"
    description = post.get("price_label") or short
    if post.get("local_price_label"):
        description = f"{description} · {post['local_price_label']}"
    canonical = f"{SITE_ORIGIN}/deal/{post['id']}/"
    files = [image["file"] for image in post.get("images") or [] if image.get("file")]
    image_abs = f"{SITE_ORIGIN}/{files[0]}" if files else f"{SITE_ORIGIN}/logo/logo-1024.png"
    og_image = (
        f'  <meta property="og:image" content="{html.escape(image_abs, quote=True)}">\n'
        f'  <meta property="og:image:alt" content="{html.escape(CHANNEL_NAME)}">\n'
        f'  <meta name="twitter:image" content="{html.escape(image_abs, quote=True)}">\n'
    )
    card = "summary_large_image"
    when = hebrew_date(post.get("datetime_utc"))
    datetime_attr = html.escape(post.get("datetime_utc") or "", quote=True)
    store = STORE_LABELS.get(post.get("store") or "other", "אחר")
    price_html = _price_block(post)
    local_html = ""
    if post.get("local_price_label"):
        local_html = (
            f'<p class="local">בארץ כ-<bdi dir="ltr">{html.escape(post.get("local_price_value") or "")}</bdi></p>'
        )
    coupons_html = _coupon_buttons(post.get("coupons") or [])
    text_html = linkify(post.get("text") or "", post.get("affiliate_links") or [])
    buttons = "" if _coupon_only(post) else _deal_buttons(post.get("affiliate_links") or [])
    gallery = _gallery(files, short)
    edited = '<span class="edited">עודכן</span>' if post.get("edited") else ""
    reply = ""
    if post.get("reply_to"):
        reply = (
            f'<p class="reply"><a href="{html.escape(post["reply_to"], quote=True)}">'
            "עדכון לפוסט קודם בטלגרם</a></p>"
        )
    return f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <link rel="canonical" href="{html.escape(canonical, quote=True)}">
  <meta property="og:type" content="article">
  <meta property="og:locale" content="he_IL">
  <meta property="og:site_name" content="{html.escape(CHANNEL_NAME)}">
  <meta property="og:title" content="{html.escape(page_title)}">
  <meta property="og:description" content="{html.escape(description)}">
  <meta property="og:url" content="{html.escape(canonical, quote=True)}">
{og_image}  <meta name="twitter:card" content="{card}">
  <meta name="twitter:title" content="{html.escape(page_title)}">
  <meta name="twitter:description" content="{html.escape(description)}">
  <meta name="theme-color" content="#ffffff">
  <link rel="icon" href="../../logo/logo-mark.svg" type="image/svg+xml">
  <link rel="icon" href="../../logo/logo-mark-64.png" type="image/png" sizes="64x64">
  <link rel="apple-touch-icon" href="../../logo/logo-mark-64.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;600&amp;display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../../css/style.css">
  <script>
    (function () {{
      try {{
        var theme = localStorage.getItem("theme");
        var queryTheme = new URLSearchParams(location.search).get("theme");
        if (queryTheme === "light" || queryTheme === "dark") theme = queryTheme;
        if (theme === "light" || theme === "dark") document.documentElement.setAttribute("data-theme", theme);
        var dark = theme === "dark" || (theme !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute("content", dark ? "#161616" : "#ffffff");
      }} catch (error) {{}}
    }})();
  </script>
</head>
<body>
  <header class="site-header">
    <div class="page header-inner">
      <div class="header-row">
        <a class="logo" href="../../">
          <picture>
            <source srcset="../../logo/logo.svg" type="image/svg+xml">
            <img src="../../logo/logo-512.png" alt="צרכנות נבונה" width="72" height="72">
          </picture>
        </a>
        <div class="header-actions">
          <a class="icon-btn" href="{CHANNEL_URL}" target="_blank" rel="noopener noreferrer" aria-label="ערוץ הטלגרם">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9.4 15.6 9.2 19c.4 0 .6-.2.8-.4l2-1.9 4.1 3c.8.4 1.3.2 1.5-.7l2.7-12.6c.2-1-.4-1.4-1.1-1.2L4.3 10.1c-1 .4-1 1-.2 1.2l4.2 1.3 9.7-6.1c.5-.3.9-.1.5.2"/></svg>
          </a>
          <button class="icon-btn" id="theme-toggle" type="button" aria-label="החלפת מצב תצוגה"></button>
        </div>
      </div>
      <p class="disclosure">{html.escape(DISCLOSURE)}</p>
    </div>
  </header>
  <main class="page deal">
    <p><a class="back" href="../../">לכל הדילים</a></p>
    {gallery}
    <div class="deal-head">
      <div class="meta">
        <span class="store">{html.escape(store)}</span>
        <time datetime="{datetime_attr}">{html.escape(when)}</time>
        {edited}
      </div>
      <h1>{html.escape(short)}</h1>
      {price_html}
      {local_html}
      {coupons_html}
    </div>
    <div class="deal-text">{text_html}</div>
    {reply}
    <div class="deal-actions">
      {buttons}
      <p class="disclosure">{html.escape(DISCLOSURE)}</p>
      <p><a class="telegram-link" href="{html.escape(post['telegram_url'], quote=True)}">לפוסט המקורי בטלגרם</a></p>
    </div>
  </main>
  <footer class="site-footer">
    <div class="page">
      <p>{html.escape(DISCLOSURE)}</p>
      <p><a href="{CHANNEL_URL}">ערוץ צרכנות נבונה בטלגרם</a></p>
    </div>
  </footer>
  <div id="toast" class="toast" role="status" aria-live="polite"></div>
  <script src="../../js/common.js"></script>
  <script src="../../js/deal.js"></script>
</body>
</html>
"""


def _price_block(post: dict) -> str:
    if not post.get("price_label"):
        return ""
    prefix = html.escape(post.get("price_prefix") or "")
    value = html.escape(post.get("price_value") or "")
    return f'<p class="price">{prefix}<bdi dir="ltr">{value}</bdi></p>'


def _coupon_buttons(coupons: list[str]) -> str:
    if not coupons:
        return ""
    buttons = []
    for coupon in coupons:
        safe = html.escape(coupon)
        buttons.append(
            f'<button class="coupon" type="button" data-code="{safe}">'
            f'<span class="coupon-code">{safe}</span><span class="coupon-hint">העתקה</span></button>'
        )
    return '<div class="coupons">' + "".join(buttons) + "</div>"


def _deal_buttons(links: list[str]) -> str:
    if not links:
        return ""
    parts = []
    for index, link in enumerate(links):
        safe = html.escape(link, quote=True)
        label = "לדיל" if index == 0 else f"לדיל {index + 1}"
        parts.append(
            f'<a class="cta" href="{safe}" target="_blank" rel="sponsored noopener noreferrer">{label}</a>'
        )
    return '<div class="cta-stack">' + "".join(parts) + "</div>"


def _gallery(files: list[str], alt: str) -> str:
    if not files:
        return ""
    safe_alt = html.escape(alt, quote=True)
    hero = html.escape(files[0], quote=True)
    thumbs = ""
    if len(files) > 1:
        buttons = []
        for index, file_name in enumerate(files):
            src = html.escape(file_name, quote=True)
            current = ' aria-current="true"' if index == 0 else ""
            buttons.append(
                f'<button type="button" data-src="../../{src}"{current}>'
                f'<img src="../../{src}" alt=""></button>'
            )
        thumbs = '<div class="thumbs">' + "".join(buttons) + "</div>"
    return (
        f'<figure class="hero"><img id="hero-img" src="../../{hero}" alt="{safe_alt}">'
        f"</figure>{thumbs}"
    )


def isolate_prices(text: str) -> str:
    """Keep amounts like 27.2$ in order inside RTL sentences."""
    return re.sub(r"[0-9][0-9.,]*\s*(?:\$|₪)", lambda match: "\u2066" + match.group(0) + "\u2069", text)


def linkify(text: str, links: list[str]) -> str:
    escaped = html.escape(isolate_prices(text))
    for url in sorted(set(links), key=len, reverse=True):
        safe = html.escape(url, quote=True)
        anchor = (
            f'<a href="{safe}" target="_blank" rel="sponsored noopener noreferrer">{safe}</a>'
        )
        escaped = escaped.replace(safe, anchor)
    return escaped.replace("\n", "<br>\n")


def hebrew_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    month = _MONTHS[parsed.month - 1]
    return f"{parsed.day} ב{month} {parsed.year}"


def _robots() -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {SITE_ORIGIN}/sitemap.xml\n"


def _sitemap(deals: list[dict]) -> str:
    urls = [
        "  <url>",
        f"    <loc>{_xml(SITE_ORIGIN + '/')}</loc>",
        "  </url>",
    ]
    for post in deals:
        lastmod = ""
        if post.get("datetime_utc"):
            day = post["datetime_utc"][:10]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                lastmod = f"\n    <lastmod>{day}</lastmod>"
        urls.append(
            "  <url>\n"
            f"    <loc>{_xml(SITE_ORIGIN + '/deal/' + str(post['id']) + '/')}</loc>"
            f"{lastmod}\n"
            "  </url>"
        )
    body = "\n".join(urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def _xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _clean_images(root: Path, deals: list[dict]) -> None:
    image_dir = root / "site" / "images"
    if not image_dir.exists():
        return
    keep = set()
    for post in deals:
        for image in post.get("images") or []:
            if image.get("file"):
                keep.add(Path(image["file"]).name)
    for path in image_dir.glob("*.webp"):
        if path.name not in keep:
            path.unlink()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
