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
_US_TEXT = re.compile(
    r"\b(usa|u\.s\.a?\.?|united states)\b|(?:^|[\s,/(])us(?:$|[\s,).])",
    re.IGNORECASE,
)
_BARE_REMOTE = re.compile(
    r"^remote(?:[\s\-/]*(?:only|ok|friendly|eligible|work|position|role))?$",
    re.IGNORECASE,
)


def location_countries(location: str) -> set[str]:
    """Countries a single location string belongs to.

    Bare "Remote" is listed in both Canada and the US. "Remote in USA" is US
    only. "Remote in UK" is neither.
    """
    if not location or not location.strip():
        return set()

    loc = location.strip()
    lower = loc.lower()
    found: set[str] = set()

    if "canada" in lower:
        found.add("Canada")
    if _US_TEXT.search(lower):
        found.add("United States")

    for part in [p.strip() for p in loc.split(",") if p.strip()]:
        token = part.upper().replace(".", "")
        if token in US_STATES or token in {"US", "USA"}:
            found.add("United States")
        elif token in CA_PROVINCES or token == "CANADA":
            found.add("Canada")

    if found:
        return found

    if any(city in lower for city in CA_CITIES):
        return {"Canada"}

    if REMOTE_PATTERN.search(lower):
        if "north america" in lower or _BARE_REMOTE.match(lower):
            return {"Canada", "United States"}
        return set()

    return set()


def _region_code(location: str) -> str | None:
    """Return the last comma-separated region token (state/province) if present."""
    parts = [p.strip() for p in location.split(",") if p.strip()]
    if len(parts) < 2:
        return None
    return parts[-1].upper().replace(".", "")


def is_us_or_canada_location(location: str) -> bool:
    return bool(location_countries(location))


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


def listing_countries(listing: dict) -> set[str]:
    """Country pages this listing belongs on.

    A posting with both a Canadian and a US location is listed on both pages.
    Bare "Remote" (no country) is listed on both. "Remote in UK" is not listed.
    """
    found: set[str] = set()
    for loc in listing.get("locations") or []:
        found |= location_countries(loc)
    return found


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
