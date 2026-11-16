"""Download Telegram CDN photos and store them as compact WebP files."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from scraper.fetch import FetchError, fetch_image_bytes, is_allowed_image_url

_TARGET_BYTES = 75_000


def download_image(url: str, dest: Path) -> None:
    if not is_allowed_image_url(url):
        raise FetchError(f"refusing image url {url}")
    save_webp(fetch_image_bytes(url), dest)


def save_webp(data: bytes, dest: Path, *, target_bytes: int = _TARGET_BYTES) -> None:
    image = Image.open(BytesIO(data))
    image = _to_rgb(image)
    image.thumbnail((960, 960), Image.Resampling.LANCZOS)
    blob = _encode(image, target_bytes)
    if len(blob) > target_bytes:
        smaller = image.copy()
        smaller.thumbnail((720, 720), Image.Resampling.LANCZOS)
        shrunk = _encode(smaller, target_bytes)
        if len(shrunk) < len(blob):
            blob = shrunk
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(blob)


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


def _encode(image: Image.Image, target_bytes: int) -> bytes:
    best = b""
    for quality in (72, 62, 52, 42, 34):
        buffer = BytesIO()
        image.save(buffer, format="WEBP", quality=quality, method=4)
        best = buffer.getvalue()
        if len(best) <= target_bytes:
            return best
    return best
