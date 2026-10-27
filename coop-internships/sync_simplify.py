"""Sync listings from the public Simplify Jobs community feeds."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

from scrapers.filters import (
    NEW_GRAD_TITLE_PATTERN,
    normalize_filtered_listing,
    passes_listing_filters,
    passes_new_grad_filters,
)

CONFIG_PATH = Path(__file__).parent / "config.json"
SOURCE_TAG = "simplify"
NEW_GRAD_SOURCE = "simplify-newgrad"
FEED_SOURCES = {SOURCE_TAG, NEW_GRAD_SOURCE}
REQUEST_TIMEOUT = 120

DEFAULT_INTERN_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/"
    "dev/.github/scripts/listings.json"
)
DEFAULT_NEW_GRAD_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/"
    "dev/.github/scripts/listings.json"
)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def fetch_simplify_listings(url: str) -> list[dict]:
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "WiE-Coop-Listings/1.0 (github; educational)"},
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"Feed did not return a JSON array: {url}")
    return data


def _dedupe(listings: list[dict]) -> list[dict]:
    """One row per URL. An internship wins if the same URL is also tagged new-grad."""
    by_url: dict[str, dict] = {}
    for item in listings:
        url = item.get("url") or ""
        if not url:
            continue
        current = by_url.get(url)
        if current is None or item.get("track") == "intern":
            by_url[url] = item
    return list(by_url.values())


def filter_intern_listings(raw: list[dict]) -> list[dict]:
    results = []
    seen_urls = set()

    for item in raw:
        title = item.get("title") or ""
        if NEW_GRAD_TITLE_PATTERN.search(title):
            continue
        if not passes_listing_filters(item):
            continue

        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append(normalize_filtered_listing(item, SOURCE_TAG, "intern"))

    return results


def filter_new_grad_listings(raw: list[dict], source: str) -> list[dict]:
    """Keep US/Canada software new-grad roles. Program is checked by the caller via classify."""
    results = []
    seen_urls = set()

    for item in raw:
        if not passes_new_grad_filters(item):
            continue
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        normalized = normalize_filtered_listing(item, source, "new_grad")
        if normalized.get("program") != "cs":
            continue
        results.append(normalized)

    return results


def listings_fingerprint(listings: list[dict]) -> str:
    """Stable hash to detect real changes and skip unnecessary commits."""
    payload = json.dumps(
        [
            {
                "url": item.get("url"),
                "title": item.get("title"),
                "active": item.get("active"),
                "locations": item.get("locations"),
                "program": item.get("program"),
                "track": item.get("track"),
                "date_posted": item.get("date_posted"),
            }
            for item in sorted(listings, key=lambda x: x.get("url", ""))
        ],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def merge_with_community(
    simplify_listings: list[dict],
    existing: list[dict],
) -> list[dict]:
    """Keep community/manual entries; replace all feed-sourced rows."""
    community = [
        item
        for item in existing
        if item.get("source") not in FEED_SOURCES
        and not str(item.get("source", "")).startswith("scraper:")
    ]

    by_url = {item["url"]: item for item in community if item.get("url")}
    for item in simplify_listings:
        by_url[item["url"]] = item

    return list(by_url.values())


def sync(
    intern_url: str | None = None,
    new_grad_url: str | None = None,
) -> tuple[list[dict], dict]:
    """Fetch internship + new-grad feeds, filter, and return listings plus stats."""
    config = load_config()
    intern_url = intern_url or config.get("simplify_url") or DEFAULT_INTERN_URL
    new_grad_url = new_grad_url or config.get("new_grad_url") or DEFAULT_NEW_GRAD_URL

    started = time.time()
    intern_raw = fetch_simplify_listings(intern_url)
    new_grad_raw = fetch_simplify_listings(new_grad_url)

    interns = filter_intern_listings(intern_raw)
    new_grads = filter_new_grad_listings(new_grad_raw, NEW_GRAD_SOURCE)
    # Intern feed occasionally includes a new-grad title. File those with new-grad.
    titled_new_grads = [
        item for item in intern_raw if NEW_GRAD_TITLE_PATTERN.search(item.get("title") or "")
    ]
    new_grads.extend(filter_new_grad_listings(titled_new_grads, SOURCE_TAG))
    filtered = _dedupe(interns + new_grads)

    elapsed = round(time.time() - started, 1)
    stats = {
        "intern_raw_count": len(intern_raw),
        "new_grad_raw_count": len(new_grad_raw),
        "intern_count": sum(1 for item in filtered if item.get("track") != "new_grad"),
        "new_grad_count": sum(1 for item in filtered if item.get("track") == "new_grad"),
        "filtered_count": len(filtered),
        "elapsed_seconds": elapsed,
        "fingerprint": listings_fingerprint(filtered),
    }
    return filtered, stats
