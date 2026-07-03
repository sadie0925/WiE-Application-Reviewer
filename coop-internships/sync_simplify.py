"""Sync listings from the public Simplify Jobs community feed."""

from __future__ import annotations

import hashlib
import json
import time

import requests

from scrapers.filters import normalize_filtered_listing, passes_listing_filters

SIMPLIFY_LISTINGS_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/"
    "dev/.github/scripts/listings.json"
)
SOURCE_TAG = "simplify"
REQUEST_TIMEOUT = 120


def fetch_simplify_listings(url: str = SIMPLIFY_LISTINGS_URL) -> list[dict]:
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "WiE-Coop-Listings/1.0 (github; educational)"},
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError("Simplify feed did not return a JSON array")
    return data


def filter_simplify_listings(raw: list[dict]) -> list[dict]:
    results = []
    seen_urls = set()

    for item in raw:
        if not passes_listing_filters(item):
            continue

        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        results.append(normalize_filtered_listing(item, SOURCE_TAG))

    results.sort(key=lambda x: (x["company_name"], x["title"]))
    return results


def listings_fingerprint(listings: list[dict]) -> str:
    """Stable hash to detect real changes and skip unnecessary commits."""
    payload = json.dumps(
        [
            {
                "url": l.get("url"),
                "title": l.get("title"),
                "active": l.get("active"),
                "locations": l.get("locations"),
            }
            for l in sorted(listings, key=lambda x: x.get("url", ""))
        ],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def merge_with_community(
    simplify_listings: list[dict],
    existing: list[dict],
) -> list[dict]:
    """Keep community/manual entries; replace all Simplify-sourced rows."""
    community = [
        item
        for item in existing
        if item.get("source") not in (SOURCE_TAG,) and not str(item.get("source", "")).startswith("scraper:")
    ]

    by_url = {item["url"]: item for item in community if item.get("url")}
    for item in simplify_listings:
        by_url[item["url"]] = item

    merged = list(by_url.values())
    merged.sort(key=lambda x: (not x.get("active", False), x.get("company_name", ""), x.get("title", "")))
    return merged


def sync(url: str = SIMPLIFY_LISTINGS_URL) -> tuple[list[dict], dict]:
    """Fetch, filter, and return listings plus stats."""
    started = time.time()
    raw = fetch_simplify_listings(url)
    filtered = filter_simplify_listings(raw)
    elapsed = round(time.time() - started, 1)

    stats = {
        "raw_count": len(raw),
        "filtered_count": len(filtered),
        "elapsed_seconds": elapsed,
        "fingerprint": listings_fingerprint(filtered),
    }
    return filtered, stats
