"""Shared constants for the channel mirror."""

from __future__ import annotations

import os

CHANNEL_SLUG = "buysmartorgohome"
CHANNEL_NAME = "צרכנות נבונה"
CHANNEL_URL = f"https://t.me/{CHANNEL_SLUG}"
PREVIEW_URL = f"https://t.me/s/{CHANNEL_SLUG}"
SITE_ORIGIN = os.environ.get("SITE_ORIGIN", "https://shaydotve.github.io/buysmart-deals").rstrip("/")
USER_AGENT = (
    "buysmart-deals-mirror/1.0 "
    "(+https://github.com/shaydotve/buysmart-deals; public channel preview)"
)
PAGE_SIZE = 24
DISCLOSURE = (
    "גילוי נאות: חלק מהקישורים באתר הם קישורי שותפים (כולל Amazon). "
    "רכישה דרכם עשויה לזכות את הערוץ בעמלה, בלי תוספת מחיר עבורכם."
)

STORE_LABELS = {
    "amazon": "Amazon",
    "aliexpress": "AliExpress",
    "ksp": "KSP",
    "other": "אחר",
}
