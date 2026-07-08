from __future__ import annotations

import re
from typing import Any, Iterable


_URL_RE = re.compile(r"https?://[^\s\"'<>\\)]+", re.I)
_IMAGE_EXT_RE = re.compile(r"\.(?:png|jpe?g|webp|gif|bmp)(?:[?#].*)?$", re.I)
_VIDEO_EXT_RE = re.compile(r"\.(?:mp4|mov|webm|m3u8)(?:[?#].*)?$", re.I)
_VIDEO_HINT_RE = re.compile(r"(?:longcat_ai_genvideo|genvideo)", re.I)


def walk_values(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        for item in value.values():
            yield from walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_values(item)
    else:
        yield value


def extract_urls(value: Any) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for item in walk_values(value):
        if not isinstance(item, str):
            continue
        for url in _URL_RE.findall(item):
            clean = url.rstrip(".,;]")
            if clean not in seen:
                seen.add(clean)
                urls.append(clean)
    return urls


def classify_media_urls(value: Any, kind: str | None = None) -> list[str]:
    urls = extract_urls(value)
    selected: list[str] = []
    for url in urls:
        lowered = url.lower()
        is_image = bool(_IMAGE_EXT_RE.search(url))
        is_video = bool(_VIDEO_EXT_RE.search(url) or _VIDEO_HINT_RE.search(url))
        if kind == "image" and not is_image:
            continue
        if kind == "video" and not is_video:
            continue
        selected.append(url)
    if kind:
        return selected
    return selected or urls


def first_media_url(value: Any, kind: str | None = None) -> str:
    urls = classify_media_urls(value, kind)
    return urls[0] if urls else ""
