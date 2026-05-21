from __future__ import annotations

import re
import unicodedata

EXTERIOR_ALIASES = {
    "factory new": "Factory New",
    "fn": "Factory New",
    "minimal wear": "Minimal Wear",
    "mw": "Minimal Wear",
    "field-tested": "Field-Tested",
    "field tested": "Field-Tested",
    "ft": "Field-Tested",
    "well-worn": "Well-Worn",
    "well worn": "Well-Worn",
    "ww": "Well-Worn",
    "battle-scarred": "Battle-Scarred",
    "battle scarred": "Battle-Scarred",
    "bs": "Battle-Scarred",
}

EXTERIOR_RE = re.compile(
    r"\((Factory New|Minimal Wear|Field-Tested|Field Tested|Well-Worn|Well Worn|Battle-Scarred|Battle Scarred|FN|MW|FT|WW|BS)\)",
    re.IGNORECASE,
)


def _clean_unicode(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\u2122", "™")
    normalized = normalized.replace("\u2605", "★")
    normalized = normalized.replace("\xa0", " ")
    return normalized


def _title_item(value: str) -> str:
    parts = []
    for token in value.split(" "):
        if token.upper() in {"AK-47", "AWP", "M4A1-S", "USP-S", "SSG", "MP7", "MP9", "P250", "P90"}:
            parts.append(token.upper())
        elif token in {"|", "★"}:
            parts.append(token)
        elif token.lower() in {"of", "the", "and"}:
            parts.append(token.lower())
        elif token:
            parts.append(token[:1].upper() + token[1:].lower())
    return " ".join(parts)


def normalize_item_name(item_name: str) -> str:
    value = _clean_unicode(item_name).strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\bStat\s*Trak\s*(?:TM|™)?\b", "StatTrak™", value, flags=re.IGNORECASE)
    value = re.sub(r"\bStatTrak\s*(?:TM|™)?\b", "StatTrak™", value, flags=re.IGNORECASE)
    value = re.sub(r"StatTrak™\s*(?:TM|™)", "StatTrak™", value)
    value = re.sub(r"\s*\|\s*", " | ", value)

    exterior_match = EXTERIOR_RE.search(value)
    exterior = None
    if exterior_match:
        raw_exterior = exterior_match.group(1).lower().replace("-", " ")
        exterior = EXTERIOR_ALIASES.get(
            raw_exterior,
            EXTERIOR_ALIASES.get(raw_exterior.replace(" ", "-"), exterior_match.group(1)),
        )
        value = EXTERIOR_RE.sub("", value).strip()

    is_stattrak = "StatTrak™" in value
    is_souvenir = bool(re.search(r"\bSouvenir\b", value, re.IGNORECASE))
    value = value.replace("StatTrak™", "").strip()
    value = re.sub(r"\bSouvenir\b", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\s+", " ", value)

    if value.startswith("★ "):
        body = "★ " + _title_item(value[2:])
    else:
        body = _title_item(value)

    prefixes = []
    if is_souvenir:
        prefixes.append("Souvenir")
    if is_stattrak:
        prefixes.append("StatTrak™")
    result = " ".join(prefixes + [body]).strip()
    if exterior:
        result = f"{result} ({exterior})"
    return re.sub(r"\s+", " ", result)


def extract_exterior(normalized_name: str) -> str | None:
    match = EXTERIOR_RE.search(normalized_name)
    return match.group(1) if match else None


def detect_category(normalized_name: str) -> str | None:
    lower = normalized_name.lower()
    if "case" in lower:
        return "case"
    if "capsule" in lower:
        return "capsule"
    if "sticker" in lower:
        return "sticker"
    if "gloves" in lower or "hand wraps" in lower:
        return "gloves"
    if normalized_name.startswith("★"):
        return "knife"
    if " | " in normalized_name:
        return "weapon"
    return "agent" if "|" not in normalized_name else None


def detect_weapon_type(normalized_name: str) -> str | None:
    without_prefix = normalized_name.replace("StatTrak™ ", "").replace("Souvenir ", "")
    if " | " not in without_prefix:
        return None
    return without_prefix.split(" | ", 1)[0].replace("★ ", "").strip()
