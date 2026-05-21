from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from app.normalizer.item_normalizer import normalize_item_name

STAR = "\u2605"
TRADEMARK = "\u2122"

EXTERIOR_SUFFIX_RE = re.compile(
    r"\s*\((Factory New|Minimal Wear|Field-Tested|Field Tested|Well-Worn|Well Worn|Battle-Scarred|Battle Scarred|FN|MW|FT|WW|BS)\)\s*$",
    re.IGNORECASE,
)


def split_configured_titles(value: str | None) -> list[str]:
    if not value:
        return []
    raw_parts = re.split(r"[\n;,]+", value)
    titles: list[str] = []
    seen: set[str] = set()
    for raw in raw_parts:
        title = extract_title_from_text(raw)
        key = title.lower()
        if not title or key in seen:
            continue
        seen.add(key)
        titles.append(title)
    return titles


def join_configured_titles(titles: list[str]) -> str:
    seen: set[str] = set()
    result: list[str] = []
    for title in titles:
        clean = extract_title_from_text(title)
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return "\n".join(result)


def extract_title_from_text(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        return text

    parsed = urlparse(text)
    query = parse_qs(parsed.query)
    title = query.get("title", [""])[0].strip()
    if title:
        return title

    for part in reversed([unquote(chunk).strip() for chunk in parsed.path.split("/") if chunk.strip()]):
        if _looks_like_item_title(part):
            return part
    return text


def expand_dmarket_title_variants(title: str) -> list[str]:
    clean = extract_title_from_text(title)
    variants: list[str] = []

    def add(value: str) -> None:
        value = re.sub(r"\s+", " ", value).strip()
        if value and value.lower() not in {item.lower() for item in variants}:
            variants.append(value)

    add(clean)
    try:
        add(normalize_item_name(clean))
    except Exception:
        pass

    for current in list(variants):
        add(strip_exterior(current))
        without_star = strip_decorative_star(current)
        add(without_star)
        add(strip_exterior(without_star))
        if _looks_like_star_item(without_star):
            with_star = add_decorative_star(without_star)
            add(with_star)
            add(strip_exterior(with_star))

    return variants


def strip_exterior(title: str) -> str:
    return EXTERIOR_SUFFIX_RE.sub("", title).strip()


def strip_decorative_star(title: str) -> str:
    value = re.sub(rf"^\s*{re.escape(STAR)}\s+", "", title).strip()
    value = re.sub(rf"^(StatTrak{re.escape(TRADEMARK)}\s+){re.escape(STAR)}\s+", r"\1", value).strip()
    return value


def add_decorative_star(title: str) -> str:
    value = strip_decorative_star(title)
    stattrak_prefix = f"StatTrak{TRADEMARK} "
    if value.startswith(stattrak_prefix):
        return f"{STAR} {stattrak_prefix}{value[len(stattrak_prefix):].strip()}"
    return f"{STAR} {value}"


def _looks_like_item_title(value: str) -> bool:
    lower = value.lower()
    return " | " in value or "(" in value or "knife" in lower or "gloves" in lower or "wraps" in lower


def _looks_like_star_item(value: str) -> bool:
    lower = value.lower()
    star_terms = (
        "knife",
        "bayonet",
        "karambit",
        "gloves",
        "hand wraps",
        "moto gloves",
        "specialist gloves",
        "sport gloves",
        "driver gloves",
    )
    return any(term in lower for term in star_terms)
