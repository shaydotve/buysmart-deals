"""One-page reachability check. Does not download images or open affiliate links."""

from __future__ import annotations

from scraper.fetch import fetch_preview_html
from scraper.parse import parse_page


def main() -> int:
    html = fetch_preview_html(None)
    page = parse_page(html)
    count = len(page.messages)
    print(f"ok messages={count} next_before={page.next_before}")
    if count < 1:
        print("Telegram preview returned no messages")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
