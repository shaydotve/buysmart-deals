"""HTTP fetchers that refuse anything except the channel preview and image CDN."""

from __future__ import annotations

import urllib.error
import urllib.request
from urllib.parse import parse_qs, urljoin, urlparse

from scraper.config import CHANNEL_SLUG, PREVIEW_URL, USER_AGENT

_IMAGE_MAX_BYTES = 8_000_000
_REDIRECTS = {301, 302, 303, 307, 308}


class FetchError(RuntimeError):
    """A request was refused or failed."""


def preview_url(before: int | None = None) -> str:
    if before is None:
        return PREVIEW_URL
    if not isinstance(before, int) or isinstance(before, bool) or before <= 0:
        raise FetchError("before must be a positive integer")
    return f"{PREVIEW_URL}?before={before}"


def is_allowed_preview_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "t.me":
        return False
    if parsed.path.rstrip("/") != f"/s/{CHANNEL_SLUG}":
        return False
    if parsed.fragment:
        return False
    if not parsed.query:
        return True
    params = parse_qs(parsed.query, keep_blank_values=True)
    if set(params) != {"before"}:
        return False
    values = params["before"]
    return len(values) == 1 and values[0].isdigit() and int(values[0]) > 0


def is_allowed_image_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = parsed.netloc.lower().split(":")[0]
    return host == "telesco.pe" or host.endswith(".telesco.pe")


def fetch_preview_html(before: int | None = None, *, timeout: float = 45) -> str:
    url = preview_url(before)
    _status, _final, body = _fetch(url, is_allowed_preview_url, timeout=timeout, limit=2_000_000)
    return body.decode("utf-8", "replace")


def fetch_image_bytes(url: str, *, timeout: float = 45) -> bytes:
    _status, _final, body = _fetch(url, is_allowed_image_url, timeout=timeout, limit=_IMAGE_MAX_BYTES)
    return body


def _fetch(url: str, allow, *, timeout: float, limit: int) -> tuple[int, str, bytes]:
    current = url
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            return _fetch_once(current if _attempt == 0 else url, allow, timeout=timeout, limit=limit)
        except FetchError:
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
    raise FetchError(f"request failed for host {urlparse(url).netloc}: {last_error}")


def _fetch_once(url: str, allow, *, timeout: float, limit: int) -> tuple[int, str, bytes]:
    current = url
    for _hop in range(6):
        if not allow(current):
            raise FetchError(f"refusing to request {current}")
        request = urllib.request.Request(
            current,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,image/*;q=0.8,*/*;q=0.5",
                "Accept-Language": "he,en;q=0.8",
            },
            method="GET",
        )
        opener = urllib.request.build_opener(_NoRedirect())
        try:
            with opener.open(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                final_url = response.geturl()
                if not allow(final_url):
                    raise FetchError(f"refusing final url {final_url}")
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise FetchError("response is too large")
                return status, final_url, data
        except urllib.error.HTTPError as exc:
            if exc.code in _REDIRECTS:
                location = exc.headers.get("Location")
                if not location:
                    raise FetchError(f"redirect without location from {current}") from exc
                target = urljoin(current, location)
                if not allow(target):
                    raise FetchError(f"refusing redirect to {target}") from exc
                current = target
                continue
            raise FetchError(f"HTTP {exc.code} from {urlparse(current).netloc}") from exc
    raise FetchError("too many redirects")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None
