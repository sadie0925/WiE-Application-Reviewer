"""Listing filters for undergrad co-op/intern roles + CS vs other classification."""

from __future__ import annotations

import re
import time

from scrapers.location import filter_us_ca_locations, is_us_or_canada_location

INCLUDE_PATTERN = re.compile(
    r"\b(intern(ship)?|co-?op|undergraduate\s+intern)\b",
    re.IGNORECASE,
)

# Roles that are never internships or new-grad software jobs we want to list.
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
    r"\b(new\s*grad(?:uate)?|new-grad|university\s+grad(?:uate)?|fresh\s+grad(?:uate)?)\b",
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


def is_new_grad_degrees(degrees: list | None) -> bool:
    """Allow bachelor's/master's new-grad roles. Reject PhD-only postings."""
    if not degrees:
        return True
    lower = [str(d).lower() for d in degrees]
    has_phd = any("phd" in d or "doctorate" in d for d in lower)
    has_bachelors_or_masters = any("bachelor" in d or "master" in d for d in lower)
    if has_phd and not has_bachelors_or_masters:
        return False
    return True


def passes_new_grad_filters(listing: dict) -> bool:
    """Software-adjacent new-grad roles. Intern/co-op titles stay on the intern boards."""
    if not listing.get("active"):
        return False
    if listing.get("is_visible") is False:
        return False

    title = listing.get("title", "")
    if INCLUDE_PATTERN.search(title):
        return False
    if EXCLUDE_PATTERN.search(title):
        return False
    if not is_new_grad_degrees(listing.get("degrees")):
        return False

    locations = listing.get("locations", [])
    if not any(is_us_or_canada_location(loc) for loc in locations):
        return False
    return True


def listing_added_at(listing: dict) -> int:
    """When the posting was added. Prefer date_posted over later edits."""
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


def is_closed(listing: dict) -> bool:
    if listing.get("active") is False:
        return True
    if listing.get("is_visible") is False:
        return True
    return False


def purge_listings(
    listings: list[dict],
    *,
    max_age_days: int = 30,
    now: float | None = None,
) -> tuple[list[dict], dict]:
    """Drop closed applications and anything added more than max_age_days ago.

    Non-software new-grad roles are dropped too — only software new-grad is published.
    """
    current = time.time() if now is None else now
    max_age_seconds = max_age_days * 24 * 60 * 60
    kept: list[dict] = []
    stats = {"closed": 0, "expired": 0, "other_new_grad": 0, "kept": 0}

    for listing in listings:
        if is_closed(listing):
            stats["closed"] += 1
            continue
        if listing.get("track") == "new_grad" and listing.get("program") != "cs":
            stats["other_new_grad"] += 1
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
    normalized["program"] = classify_program(normalized)
    return normalized
