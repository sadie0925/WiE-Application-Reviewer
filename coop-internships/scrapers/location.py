"""US and Canada location detection and README board grouping."""

from __future__ import annotations

import re

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

CA_PROVINCES = {"ON", "BC", "AB", "QC", "MB", "SK", "NS", "NB", "NL", "PE", "NT", "YT", "NU"}

CA_CITIES = (
    "toronto", "vancouver", "montreal", "montréal", "ottawa", "calgary",
    "edmonton", "waterloo", "mississauga", "burnaby", "kitchener",
)

REMOTE_PATTERN = re.compile(r"\bremote\b", re.IGNORECASE)


def is_us_or_canada_location(location: str) -> bool:
    if not location or not location.strip():
        return False

    loc = location.strip()
    lower = loc.lower()

    if REMOTE_PATTERN.search(lower):
        return True
    if "canada" in lower or "united states" in lower or ", usa" in lower:
        return True

    parts = [p.strip() for p in loc.split(",")]
    if len(parts) >= 2:
        region = parts[-1].upper().replace(".", "")
        if region in US_STATES or region in CA_PROVINCES:
            return True
        if region in ("US", "USA", "CANADA"):
            return True

    return any(city in lower for city in CA_CITIES)


def filter_us_ca_locations(locations: list[str]) -> list[str]:
    seen = set()
    result = []
    for loc in locations or []:
        if is_us_or_canada_location(loc) and loc not in seen:
            seen.add(loc)
            result.append(loc)
    return result


def classify_country(location: str) -> str:
    lower = location.lower()
    if REMOTE_PATTERN.search(lower):
        if "canada" in lower:
            return "Remote (Canada)"
        if any(x in lower for x in ("us", "usa", "united states")):
            return "Remote (US)"
        return "Remote"

    if "canada" in lower:
        return "Canada"

    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 2:
        region = parts[-1].upper().replace(".", "")
        if region in CA_PROVINCES:
            return "Canada"

    for city in CA_CITIES:
        if city in lower:
            return "Canada"

    return "United States"


def get_primary_location(listing: dict) -> tuple[str, str]:
    """Return (country_board, location_board) for grouping in README."""
    locations = filter_us_ca_locations(listing.get("locations", []))
    if not locations:
        return ("Unknown", "Unknown")

    loc = locations[0]
    country = classify_country(loc)

    if country.startswith("Remote"):
        return (country, country)

    return (country, loc)


COUNTRY_ORDER = {
    "Canada": 0,
    "United States": 1,
    "Remote (Canada)": 2,
    "Remote (US)": 3,
    "Remote": 4,
    "Unknown": 5,
}
