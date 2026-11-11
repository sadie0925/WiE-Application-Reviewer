"""Sync listings from the public Simplify Jobs community feeds.

Internships come from the Summer internship feed. Software new-grad roles come
from the New-Grad Positions feed on their own boards. The internship pipeline
is not replaced.
"""

from __future__ import annotations

import hashlib
import json
import time

import requests

from scrapers.filters import (
    NEW_GRAD_TITLE_PATTERN,
    normalize_filtered_listing,
    passes_listing_filters,
    passes_new_grad_filters,
)

SIMPLIFY_LISTINGS_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/"
    "dev/.github/scripts/listings.json"
)
SIMPLIFY_NEW_GRAD_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/"
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


def filter_intern_listings(raw: list[dict]) -> list[dict]:
    results = []
    seen_urls = set()
    for item in raw:
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        title = item.get("title") or ""
        # Rare new-grad titles that still show up in the intern feed.
        if NEW_GRAD_TITLE_PATTERN.search(title):
            continue
        if not passes_listing_filters(item):
            continue
        seen_urls.add(url)
        results.append(normalize_filtered_listing(item, SOURCE_TAG, "intern"))
    return results


def filter_new_grad_listings(raw: list[dict]) -> list[dict]:
    """Software new-grad roles for undergrads. Master's/PhD-only rows are dropped."""
    results = []
    seen_urls = set()
    for item in raw:
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        if not passes_new_grad_filters(item):
            continue
        normalized = normalize_filtered_listing(item, SOURCE_TAG, "new_grad")
        if normalized.get("program") != "cs":
            continue
        seen_urls.add(url)
        results.append(normalized)
    return results


def filter_simplify_listings(raw: list[dict]) -> list[dict]:
    """Back-compat helper used by tests: intern feed only, plus rare new-grad titles."""
    results = filter_intern_listings(raw)
    seen = {item["url"] for item in results}
    for item in raw:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        title = item.get("title") or ""
        if not NEW_GRAD_TITLE_PATTERN.search(title):
            continue
        if not passes_new_grad_filters(item):
            continue
        normalized = normalize_filtered_listing(item, SOURCE_TAG, "new_grad")
        if normalized.get("program") != "cs":
            continue
        seen.add(url)
        results.append(normalized)
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
                "sponsorship": l.get("sponsorship"),
                "track": l.get("track"),
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


def sync(
    url: str = SIMPLIFY_LISTINGS_URL,
    new_grad_url: str = SIMPLIFY_NEW_GRAD_URL,
) -> tuple[list[dict], dict]:
    """Fetch internship + new-grad feeds, filter, and return listings plus stats."""
    started = time.time()
    intern_raw = fetch_simplify_listings(url)
    interns = filter_intern_listings(intern_raw)

    new_grads: list[dict] = []
    new_grad_raw_count = 0
    try:
        new_grad_raw = fetch_simplify_listings(new_grad_url)
        new_grad_raw_count = len(new_grad_raw)
        new_grads = filter_new_grad_listings(new_grad_raw)
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        print(f"  New-grad feed failed: {exc}")

    # Prefer the dedicated new-grad feed when the same URL appears in both.
    by_url = {item["url"]: item for item in interns if item.get("url")}
    for item in new_grads:
        by_url[item["url"]] = item
    filtered = list(by_url.values())
    elapsed = round(time.time() - started, 1)

    stats = {
        "raw_count": len(intern_raw) + new_grad_raw_count,
        "filtered_count": len(filtered),
        "intern_count": len(interns),
        "new_grad_count": len(new_grads),
        "elapsed_seconds": elapsed,
        "fingerprint": listings_fingerprint(filtered),
    }
    return filtered, stats
