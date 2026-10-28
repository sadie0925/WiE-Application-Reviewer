"""Listing filters for undergrad co-op/intern roles + CS vs other classification."""

from __future__ import annotations

import re
import time

from scrapers.location import filter_us_ca_locations, is_us_or_canada_location

INCLUDE_PATTERN = re.compile(
    r"\b(intern(ship)?|co-?op|undergraduate\s+intern)\b",
    re.IGNORECASE,
)

EXCLUDE_PATTERN = re.compile(
    r"\b("
    r"phd|doctorate|postdoc|post-doc|"
    r"recruiter|recruiting|head\s+of|"
    r"people\s+strategy|inside\s+sales|"
    r"early\s+career(?!\s+(engineer|developer|intern))"
    r")\b",
    re.IGNORECASE,
)

NEW_GRAD_TITLE_PATTERN = re.compile(
    r"\b(new\s*grad(?:uate)?|new-grad|university\s+grad(?:uate)?)\b",
    re.IGNORECASE,
)

# Title / category signals for CS & closely related tech software roles
CS_TITLE_PATTERN = re.compile(
    r"\b("
    r"software|swe|sde|developer|programmer|programming|"
    r"computer\s*science|comp(?:uter)?\s*sci|"
    r"full[\s-]?stack|front[\s-]?end|back[\s-]?end|"
    r"mobile\s*(?:app|engineer|developer)|ios|android|"
    r"machine\s*learning|deep\s*learning|\bml\b|\bai\b|artificial\s*intelligence|"
    r"data\s*(?:scientist|science|engineer|engineering|analyst|analytics)|"
    r"devops|sre|site\s*reliability|"
    r"cyber\s*security|security\s*engineer|infosec|"
    r"cloud\s*(?:engineer|developer)|platform\s*engineer|"
    r"firmware|embedded\s*software|compiler|"
    r"quant(?:itative)?\s*(?:developer|engineer|technologist)|"
    r"web\s*developer|app(?:lication)?\s*developer|"
    r"systems?\s*(?:software|engineer)|infrastructure\s*(?:engineer|software)"
    r")\b",
    re.IGNORECASE,
)

CS_CATEGORIES = {
    "software",
    "software engineering",
    "ai/ml/data",
    "data science, ai & machine learning",
    "quant",
    "quantitative finance",
}

# Clear non-CS title signals — win over a mis-tagged Simplify category
OTHER_TITLE_PATTERN = re.compile(
    r"\b("
    r"mechanical|electrical|civil|chemical|biomedical|aerospace|"
    r"forestry|agriculture|agricultur|"
    r"marketing|sales|finance(?!\s*(?:tech|software|engineer|developer))|"
    r"accounting|audit|hr\b|human\s*resources|recruit|"
    r"supply\s*chain|operations(?!\s*(?:research|engineer|software))|"
    r"business\s*(?:analyst|strategy|development|operations)|"
    r"project\s*manager|program\s*manager|"
    r"relationship\s*manager|customer\s*connections|"
    r"optical\s*modem|hardware(?!\s*software)|asic|fpga|"
    r"rf\b|radio\s*frequency|photonics|nanofabrication|"
    r"product\s*(?:manager|management|marketing|intern|ops|operations)"
    r")\b",
    re.IGNORECASE,
)


def is_intern_title(title: str) -> bool:
    if EXCLUDE_PATTERN.search(title) or NEW_GRAD_TITLE_PATTERN.search(title):
        return False
    return bool(INCLUDE_PATTERN.search(title))


def is_undergrad_degrees(degrees: list | None) -> bool:
    if not degrees:
        return True

    lower = [str(d).lower() for d in degrees]
    if any("phd" in d or "doctorate" in d for d in lower):
        if not any("bachelor" in d for d in lower):
            return False
    if any("master" in d for d in lower) and not any("bachelor" in d for d in lower):
        return False
    return True


def classify_program(listing: dict) -> str:
    """Return 'cs' or 'other' for README sectioning.

    Prefer title signals. CS covers software/CS/data/AI/ML/quant-dev roles.
    Clear non-CS title keywords beat a mis-tagged feed category.
    """
    title = listing.get("title") or ""
    if OTHER_TITLE_PATTERN.search(title) and not CS_TITLE_PATTERN.search(title):
        return "other"
    if CS_TITLE_PATTERN.search(title):
        return "cs"

    category = str(listing.get("category") or "").strip().lower()
    if category in CS_CATEGORIES:
        return "cs"

    return "other"


def passes_new_grad_filters(listing: dict) -> bool:
    """Software new-grad roles from the same feed. Internships stay on the intern path."""
    if not listing.get("active") or listing.get("is_visible") is False:
        return False
    title = listing.get("title") or ""
    if not NEW_GRAD_TITLE_PATTERN.search(title):
        return False
    if EXCLUDE_PATTERN.search(title) or INCLUDE_PATTERN.search(title):
        return False
    if not any(is_us_or_canada_location(loc) for loc in listing.get("locations") or []):
        return False
    return True


def listing_added_at(listing: dict) -> int:
    try:
        posted = int(listing.get("date_posted") or 0)
    except (TypeError, ValueError):
        posted = 0
    if posted > 0:
        return posted
    try:
        return int(listing.get("date_updated") or 0)
    except (TypeError, ValueError):
        return 0


def purge_listings(
    listings: list[dict],
    *,
    max_age_days: int = 30,
    now: float | None = None,
) -> tuple[list[dict], dict]:
    """Drop closed applications and anything added more than max_age_days ago."""
    current = time.time() if now is None else now
    max_age_seconds = max_age_days * 24 * 60 * 60
    kept: list[dict] = []
    stats = {"closed": 0, "expired": 0, "kept": 0}
    for listing in listings:
        if listing.get("active") is False or listing.get("is_visible") is False:
            stats["closed"] += 1
            continue
        if listing.get("track") == "new_grad" and listing.get("program") != "cs":
            stats["closed"] += 1
            continue
        added = listing_added_at(listing)
        if added <= 0 or (current - added) > max_age_seconds:
            stats["expired"] += 1
            continue
        kept.append(listing)
    stats["kept"] = len(kept)
    return kept, stats


def passes_listing_filters(listing: dict, *, require_active: bool = True) -> bool:
    if require_active:
        if not listing.get("active"):
            return False
        if listing.get("is_visible") is False:
            return False

    title = listing.get("title", "")
    if not is_intern_title(title):
        return False
    if not is_undergrad_degrees(listing.get("degrees")):
        return False

    locations = listing.get("locations", [])
    if not any(is_us_or_canada_location(loc) for loc in locations):
        return False

    return True


def normalize_filtered_listing(listing: dict, source: str, track: str = "intern") -> dict:
    """Return listing with US/CA locations only and consistent fields.

    Terms are intentionally omitted: Simplify often stamps a season that is not
    stated in the job title, and fetching every job description would be too costly.
    """
    us_ca_locs = filter_us_ca_locations(listing.get("locations", []))
    normalized = {
        "id": listing.get("id", ""),
        "company_name": listing.get("company_name", ""),
        "company_url": listing.get("company_url", ""),
        "title": listing.get("title", "").strip(),
        "url": listing.get("url", ""),
        "locations": us_ca_locs or ["Unknown"],
        "active": True,
        "is_visible": True,
        "source": source,
        "date_posted": listing.get("date_posted", 0),
        "date_updated": listing.get("date_updated", 0),
        "category": listing.get("category", ""),
        "sponsorship": listing.get("sponsorship", ""),
        "track": track,
    }
    description = (listing.get("description") or "").strip()
    if description:
        normalized["description"] = description
    normalized["program"] = classify_program(normalized)
    return normalized


# Waterloo's spring term is May–August. US postings call that summer.
_SEASON_WORD = re.compile(
    r"\b(winter|spring|fall|autumn|summer)\b(?:\s+(20\d{2}))?",
    re.IGNORECASE,
)
_SEASON_LABEL = {
    "winter": "Winter",
    "spring": "Spring",
    "fall": "Fall",
    "autumn": "Fall",
    "summer": "Spring",
}
_SEASON_ORDER = {"Winter": 0, "Spring": 1, "Fall": 2}

_SPONSORSHIP_LABELS = {
    "Offers Sponsorship": "Sponsors",
    "Does Not Offer Sponsorship": "No sponsorship",
    "U.S. Citizenship is Required": "US citizenship",
}
_RESTRICTION_PATTERNS = (
    (re.compile(r"\b(ts/?\s*sci|top\s+secret|secret\s+clearance|security\s+clearance|(?:u\.?s\.?|us)\s+clearance)\b", re.I), "US clearance"),
    (re.compile(r"\bu\.?s\.?\s+persons?\b", re.I), "US person"),
    (re.compile(r"\b(u\.?s\.?\s+citizens?|us\s+citizens?|citizenship(?:\s+is)?\s+required|must\s+be\s+a\s+citizen)\b", re.I), "US citizenship"),
    (re.compile(r"\b(?:u\.?s\.?\s+)?permanent\s+residents?\b", re.I), "PR only"),
    (re.compile(r"\b(authorized\s+to\s+work|work\s+authorization|without\s+restriction|legally\s+authorized\s+to\s+work)\b", re.I), "Work auth required"),
    (re.compile(r"\b(no\s+sponsorship|does\s+not\s+sponsor|not\s+offer\s+sponsorship|will\s+not\s+sponsor|unable\s+to\s+sponsor)\b", re.I), "No sponsorship"),
    (re.compile(r"\b(offers?\s+sponsorship|visa\s+sponsorship|will\s+sponsor|sponsorship\s+available)\b", re.I), "Sponsors"),
)


def work_term_label(listing: dict) -> str:
    """Waterloo term from the title or description. Blank when neither says one.

    Summer is reported as Spring. "Summer Games" is a program name, not a term.
    """
    text = f"{listing.get('title') or ''}\n{listing.get('description') or ''}"
    found = []
    seen = set()
    for match in _SEASON_WORD.finditer(text):
        word = match.group(1).lower()
        after = text[match.end(): match.end() + 16]
        if word == "summer" and re.match(r"\s+games\b", after, re.IGNORECASE):
            continue
        if word == "summer":
            window = text[max(0, match.start() - 40): match.end() + 40]
            seasonal = match.group(2) or re.search(
                r"\b(intern|internship|co-?op|term|student|analyst)\b",
                window,
                re.IGNORECASE,
            )
            if not seasonal:
                continue
        label = _SEASON_LABEL[word]
        year = match.group(2) or ""
        key = (label, year)
        if key in seen:
            continue
        seen.add(key)
        found.append((year or "0000", _SEASON_ORDER[label], f"{label} {year}".strip()))
    found.sort()
    return ", ".join(item[2] for item in found)


def work_auth_label(listing: dict) -> str:
    """Sponsorship or a restriction that blocks many UW students. Blank if unstated."""
    labels = []
    sponsorship = (listing.get("sponsorship") or "").strip()
    if sponsorship in _SPONSORSHIP_LABELS:
        labels.append(_SPONSORSHIP_LABELS[sponsorship])
    text = f"{listing.get('title') or ''}\n{listing.get('description') or ''}"
    for pattern, label in _RESTRICTION_PATTERNS:
        if pattern.search(text) and label not in labels:
            labels.append(label)
    return ", ".join(labels)
