"""Listing filters for undergrad co-op/intern roles."""

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
    """Return listing with US/CA locations only and consistent fields."""
    us_ca_locs = filter_us_ca_locations(listing.get("locations", []))
    return {
        "id": listing.get("id", ""),
        "company_name": listing.get("company_name", ""),
        "company_url": listing.get("company_url", ""),
        "title": listing.get("title", "").strip(),
        "url": listing.get("url", ""),
        "locations": us_ca_locs or ["Unknown"],
        "terms": listing.get("terms") or ["Unknown"],
        "active": True,
        "is_visible": True,
        "source": source,
        "date_posted": listing.get("date_posted", 0),
        "date_updated": listing.get("date_updated", 0),
        "category": listing.get("category", ""),
        "sponsorship": listing.get("sponsorship", ""),
    }
