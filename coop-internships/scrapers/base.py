import uuid

from scrapers.filters import classify_program, is_intern_title


def is_intern_role(title: str) -> bool:
    return is_intern_title(title)


def make_listing_id(url: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def normalize_listing(
    *,
    company_name: str,
    title: str,
    url: str,
    locations: list[str],
    source: str,
    now: int,
) -> dict:
    from scrapers.location import filter_us_ca_locations

    us_ca = filter_us_ca_locations(locations)
    listing = {
        "id": make_listing_id(url),
        "company_name": company_name,
        "company_url": "",
        "title": title.strip(),
        "url": url,
        "locations": us_ca or ["Unknown"],
        "active": True,
        "is_visible": True,
        "source": source,
        "date_posted": now,
        "date_updated": now,
        "category": "",
    }
    listing["program"] = classify_program(listing)
    return listing
