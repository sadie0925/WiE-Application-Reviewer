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


def _region_code(location: str) -> str | None:
    """Return the last comma-separated region token (state/province) if present."""
    parts = [p.strip() for p in location.split(",") if p.strip()]
    if len(parts) < 2:
        return None
    return parts[-1].upper().replace(".", "")


def is_us_or_canada_location(location: str) -> bool:
    if not location or not location.strip():
        return False

    loc = location.strip()
    lower = loc.lower()

    if REMOTE_PATTERN.search(lower):
        return True
    if "canada" in lower or "united states" in lower or ", usa" in lower:
        return True

    region = _region_code(loc)
    if region:
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
    """Classify a location into a country board (no city/province sub-boards)."""
    lower = location.lower()
    if REMOTE_PATTERN.search(lower):
        if "canada" in lower:
            return "Remote (Canada)"
        if any(x in lower for x in ("united states", ", usa", " us)")):
            return "Remote (US)"
        # Ambiguous remote → keep as generic Remote
        return "Remote"

    if "canada" in lower:
        return "Canada"

    region = _region_code(location)
    if region:
        # Prefer explicit state/province codes over city-name heuristics
        # (e.g. "Vancouver, WA" must be US, not Canada).
        if region in US_STATES or region in ("US", "USA"):
            return "United States"
        if region in CA_PROVINCES or region == "CANADA":
            return "Canada"

    if "united states" in lower or ", usa" in lower:
        return "United States"

    for city in CA_CITIES:
        if city in lower:
            return "Canada"

    return "United States"


def get_board_country(listing: dict) -> str:
    """Return the country board key for README grouping (no city split)."""
    locations = filter_us_ca_locations(listing.get("locations", []))
    if not locations:
        return "Unknown"
    return classify_country(locations[0])


# Back-compat alias used by older call sites
def get_primary_location(listing: dict) -> tuple[str, str]:
    country = get_board_country(listing)
    return (country, country)


COUNTRY_ORDER = {
    "Canada": 0,
    "United States": 1,
    "Remote (Canada)": 2,
    "Remote (US)": 3,
    "Remote": 4,
    "Unknown": 5,
}
