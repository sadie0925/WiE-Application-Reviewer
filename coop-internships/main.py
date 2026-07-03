#!/usr/bin/env python3
"""CLI for scraping co-op/internship listings and updating README."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from readme_generator import update_readme
from scrapers import scrape_company

ROOT = Path(__file__).parent
LISTINGS_PATH = ROOT / "listings.json"
COMPANIES_PATH = ROOT / "companies.json"


def load_json(path: Path) -> list | dict:
    if not path.exists():
        return [] if path.name == "listings.json" else {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def merge_listings(existing: list[dict], scraped: list[dict]) -> tuple[list[dict], int, int]:
    """Merge scraped listings into existing by URL. Returns (merged, added, updated)."""
    by_url = {item["url"]: item for item in existing if item.get("url")}
    now = int(time.time())
    added = 0
    updated = 0

    scraped_urls = set()
    for listing in scraped:
        url = listing.get("url")
        if not url:
            continue
        scraped_urls.add(url)

        if url in by_url:
            entry = by_url[url]
            entry["title"] = listing["title"]
            entry["locations"] = listing["locations"]
            entry["terms"] = listing["terms"]
            entry["active"] = True
            entry["date_updated"] = now
            updated += 1
        else:
            by_url[url] = listing
            added += 1

    # Mark scraper-sourced listings as inactive if not seen this run
    for entry in by_url.values():
        source = entry.get("source", "")
        if source.startswith("scraper:") and entry.get("url") not in scraped_urls:
            if entry.get("active"):
                entry["active"] = False
                entry["date_updated"] = now

    merged = sorted(
        by_url.values(),
        key=lambda x: (not x.get("active", False), x.get("company_name", ""), x.get("title", "")),
    )
    return merged, added, updated


def cmd_scrape() -> int:
    companies = load_json(COMPANIES_PATH)
    existing = load_json(LISTINGS_PATH)
    if not isinstance(existing, list):
        existing = []

    all_scraped = []
    errors = []

    for company in companies:
        try:
            results = scrape_company(company)
            print(f"  {company['name']}: {len(results)} intern/co-op roles")
            all_scraped.extend(results)
        except Exception as exc:
            msg = f"{company['name']}: {exc}"
            print(f"  ERROR {msg}", file=sys.stderr)
            errors.append(msg)

    merged, added, updated = merge_listings(existing, all_scraped)
    save_json(LISTINGS_PATH, merged)

    print(f"\nDone. {len(all_scraped)} scraped, {added} new, {updated} updated, {len(merged)} total.")
    return 1 if errors else 0


def cmd_readme() -> int:
    listings = load_json(LISTINGS_PATH)
    readme_path = ROOT / "README.md"
    update_readme(readme_path, listings if isinstance(listings, list) else [])
    print(f"Updated listings section in {readme_path}")
    return 0


def cmd_add_manual(args) -> int:
    """Add a community-submitted listing (used by GitHub Action)."""
    existing = load_json(LISTINGS_PATH)
    if not isinstance(existing, list):
        existing = []

    now = int(time.time())
    from scrapers.base import make_listing_id

    listing = {
        "id": make_listing_id(args.url),
        "company_name": args.company,
        "company_url": "",
        "title": args.title,
        "url": args.url,
        "locations": [loc.strip() for loc in args.locations.split(",") if loc.strip()],
        "terms": [t.strip() for t in args.terms.split(",") if t.strip()],
        "active": True,
        "is_visible": True,
        "source": args.contributor,
        "date_posted": now,
        "date_updated": now,
    }

    by_url = {item["url"]: item for item in existing if item.get("url")}
    by_url[listing["url"]] = listing
    save_json(LISTINGS_PATH, list(by_url.values()))
    print(f"Added listing: {listing['title']} at {listing['company_name']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Co-op & internship listings updater")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scrape", help="Run scrapers and update listings.json")
    sub.add_parser("readme", help="Regenerate README.md from listings.json")

    add_parser = sub.add_parser("add", help="Add a community-submitted listing")
    add_parser.add_argument("--company", required=True)
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--url", required=True)
    add_parser.add_argument("--locations", required=True, help="Comma-separated")
    add_parser.add_argument("--terms", default="Unknown")
    add_parser.add_argument("--contributor", default="community")

    args = parser.parse_args()

    if args.command == "scrape":
        return cmd_scrape()
    if args.command == "readme":
        return cmd_readme()
    if args.command == "add":
        return cmd_add_manual(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
