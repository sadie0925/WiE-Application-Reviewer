"""Listing filters for undergrad co-op/intern roles + CS vs other classification."""

from __future__ import annotations

import re

from scrapers.location import filter_us_ca_locations, is_us_or_canada_location

INCLUDE_PATTERN = re.compile(
    r"\b(intern(ship)?|co-?op|undergraduate\s+intern)\b",
    re.IGNORECASE,
)

EXCLUDE_PATTERN = re.compile(
    r"\b("
    r"phd|doctorate|postdoc|post-doc|"
    r"new\s*grad|new-grad|"
    r"recruiter|recruiting|head\s+of|"
    r"people\s+strategy|inside\s+sales|"
    r"early\s+career(?!\s+(engineer|developer|intern))"
    r")\b",
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
    if EXCLUDE_PATTERN.search(title):
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


def normalize_filtered_listing(listing: dict, source: str) -> dict:
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
    }
    normalized["program"] = classify_program(normalized)
    return normalized
