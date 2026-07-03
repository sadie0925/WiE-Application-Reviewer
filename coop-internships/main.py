#!/usr/bin/env python3
"""CLI for syncing co-op/internship listings and updating README."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from readme_generator import update_readme
from scrapers import scrape_company
from scrapers.location import filter_us_ca_locations
from sync_simplify import (
    listings_fingerprint,
    merge_with_community,
    sync,
)

ROOT = Path(__file__).parent
LISTINGS_PATH = ROOT / "listings.json"
COMPANIES_PATH = ROOT / "companies.json"
HASH_PATH = ROOT / ".listings-hash"


def load_json(path: Path) -> list | dict:
    if not path.exists():
        return [] if path.name == "listings.json" else {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_hash() -> str:
    if HASH_PATH.exists():
        return HASH_PATH.read_text(encoding="utf-8").strip()
    return ""


def save_hash(value: str) -> None:
    HASH_PATH.write_text(value + "\n", encoding="utf-8")


def cmd_sync(args) -> int:
    """Sync from Simplify public feed (primary, low-load)."""
    existing = load_json(LISTINGS_PATH)
    if not isinstance(existing, list):
        existing = []

    print("Fetching Simplify community feed (1 HTTP request)...")
    simplify_listings, stats = sync()

    merged = merge_with_community(simplify_listings, existing)
    new_hash = listings_fingerprint(merged)
    old_hash = load_hash()

    print(
        f"  Raw: {stats['raw_count']} → Filtered: {stats['filtered_count']} "
        f"US/Canada undergrad roles ({stats['elapsed_seconds']}s)"
    )
    print(f"  Total in listings.json: {len(merged)}")

    if new_hash == old_hash and not args.force:
        print("No changes detected — skipping write.")
        return 0

    save_json(LISTINGS_PATH, merged)
    save_hash(new_hash)
    print("listings.json updated.")
    return 0


def cmd_scrape(args) -> int:
    """Optional supplemental scrape of companies.json (batched, rate-limited)."""
    companies = load_json(COMPANIES_PATH)
    if not isinstance(companies, list) or not companies:
        print("No companies in companies.json — use `sync` instead.")
        return 0

    existing = load_json(LISTINGS_PATH)
    if not isinstance(existing, list):
        existing = []

    batch_size = args.batch_size
    state_path = ROOT / ".scrape-state.json"
    state = load_json(state_path) if state_path.exists() else {"offset": 0}
    offset = int(state.get("offset", 0)) % len(companies)
    batch = companies[offset : offset + batch_size]
    next_offset = (offset + batch_size) % len(companies)

    all_scraped = []
    for i, company in enumerate(batch):
        try:
            results = scrape_company(company)
            us_ca = [
                r for r in results
                if filter_us_ca_locations(r.get("locations", []))
            ]
            print(f"  {company['name']}: {len(us_ca)} US/CA intern roles")
            all_scraped.extend(us_ca)
        except Exception as exc:
            print(f"  ERROR {company['name']}: {exc}", file=sys.stderr)
        if i < len(batch) - 1:
            time.sleep(args.delay)

    by_url = {item["url"]: item for item in existing if item.get("url")}
    now = int(time.time())
    for listing in all_scraped:
        url = listing.get("url")
        if url:
            listing["date_updated"] = now
            by_url[url] = listing

    merged = list(by_url.values())
    save_json(LISTINGS_PATH, merged)
    save_hash(listings_fingerprint(merged))
    save_json(state_path, {"offset": next_offset})
    print(f"Batch done ({len(batch)} companies). Next offset: {next_offset}")
    return 0


def cmd_readme() -> int:
    listings = load_json(LISTINGS_PATH)
    readme_path = ROOT / "README.md"
    update_readme(readme_path, listings if isinstance(listings, list) else [])
    print(f"Updated listings section in {readme_path}")
    return 0


def cmd_add_manual(args) -> int:
    existing = load_json(LISTINGS_PATH)
    if not isinstance(existing, list):
        existing = []

    now = int(time.time())
    from scrapers.base import make_listing_id
    from scrapers.location import filter_us_ca_locations

    locations = filter_us_ca_locations(
        [loc.strip() for loc in args.locations.split(",") if loc.strip()]
    )
    if not locations:
        print("Error: no US/Canada locations in submission", file=sys.stderr)
        return 1

    listing = {
        "id": make_listing_id(args.url),
        "company_name": args.company,
        "company_url": "",
        "title": args.title,
        "url": args.url,
        "locations": locations,
        "terms": [t.strip() for t in args.terms.split(",") if t.strip()],
        "active": True,
        "is_visible": True,
        "source": args.contributor,
        "date_posted": now,
        "date_updated": now,
    }

    by_url = {item["url"]: item for item in existing if item.get("url")}
    by_url[listing["url"]] = listing
    merged = list(by_url.values())
    save_json(LISTINGS_PATH, merged)
    save_hash(listings_fingerprint(merged))
    print(f"Added listing: {listing['title']} at {listing['company_name']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Co-op & internship listings updater")
    sub = parser.add_subparsers(dest="command", required=True)

    sync_parser = sub.add_parser("sync", help="Sync from Simplify feed (primary)")
    sync_parser.add_argument("--force", action="store_true", help="Write even if unchanged")

    scrape_parser = sub.add_parser("scrape", help="Supplemental batched company scrape")
    scrape_parser.add_argument("--batch-size", type=int, default=5)
    scrape_parser.add_argument("--delay", type=float, default=2.0, help="Seconds between companies")

    sub.add_parser("readme", help="Regenerate README.md from listings.json")

    add_parser = sub.add_parser("add", help="Add a community-submitted listing")
    add_parser.add_argument("--company", required=True)
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--url", required=True)
    add_parser.add_argument("--locations", required=True, help="Comma-separated US/CA locations")
    add_parser.add_argument("--terms", default="Unknown")
    add_parser.add_argument("--contributor", default="community")

    args = parser.parse_args()

    if args.command == "sync":
        return cmd_sync(args)
    if args.command == "scrape":
        return cmd_scrape(args)
    if args.command == "readme":
        return cmd_readme()
    if args.command == "add":
        return cmd_add_manual(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
