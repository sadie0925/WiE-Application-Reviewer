#!/usr/bin/env python3
"""CLI for syncing co-op/internship listings and updating README."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from hackathons import fetch_hackathons
from readme_generator import update_readme
from scrapers import scrape_company
from scrapers.filters import NEW_GRAD_TITLE_PATTERN, classify_program, purge_listings
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
README_PATH = ROOT / "README.md"
HACKATHONS_PATH = ROOT / "hackathons.json"


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


def annotate_programs(listings: list[dict]) -> list[dict]:
    """Ensure every listing has a cs/other program tag and intern vs new-grad track."""
    for listing in listings:
        listing["program"] = classify_program(listing)
        title = listing.get("title") or ""
        if listing.get("track") not in {"intern", "new_grad"}:
            listing["track"] = (
                "new_grad" if NEW_GRAD_TITLE_PATTERN.search(title) else "intern"
            )
        # Drop unreliable season metadata from feed
        listing.pop("terms", None)
    return listings


def finalize_listings(listings: list[dict]) -> tuple[list[dict], dict]:
    """Tag listings, then drop closed ones and anything older than max_age_days."""
    config_path = ROOT / "config.json"
    max_age_days = 30
    if config_path.exists():
        try:
            max_age_days = int(json.loads(config_path.read_text(encoding="utf-8")).get("max_age_days", 30))
        except (ValueError, TypeError, json.JSONDecodeError):
            max_age_days = 30
    prepared = annotate_programs(listings)
    kept, stats = purge_listings(prepared, max_age_days=max_age_days)
    kept.sort(
        key=lambda item: (
            -(int(item.get("date_posted") or 0)),
            (item.get("company_name") or "").lower(),
            (item.get("title") or "").lower(),
        )
    )
    stats["max_age_days"] = max_age_days
    return kept, stats


def save_hackathons(events: list[dict]) -> None:
    save_json(HACKATHONS_PATH, events)


def regenerate_readme(listings: list[dict], hackathons: list[dict] | None = None) -> None:
    update_readme(README_PATH, listings, hackathons)
    print(f"Updated listings section in {README_PATH}")


def cmd_sync(args) -> int:
    """Sync from Simplify public feed (primary, low-load)."""
    existing = load_json(LISTINGS_PATH)
    if not isinstance(existing, list):
        existing = []

    print("Fetching Simplify community feed (1 HTTP request)...")
    simplify_listings, stats = sync()

    merged, purge_stats = finalize_listings(merge_with_community(simplify_listings, existing))
    print("Fetching hackathons (MLH + Devpost)...")
    try:
        hackathon_events = fetch_hackathons()
    except Exception as exc:
        print(f"  Hackathon fetch failed: {exc}", file=sys.stderr)
        hackathon_events = []
        if HACKATHONS_PATH.exists():
            saved = load_json(HACKATHONS_PATH)
            hackathon_events = saved if isinstance(saved, list) else []
    uw_count = sum(1 for item in hackathon_events if item.get("tier") == "uw")
    print(f"  Hackathons: {len(hackathon_events)} ({uw_count} Waterloo clubs/committees first)")

    new_hash = listings_fingerprint(merged) + "|" + json.dumps(
        [(item.get("name"), item.get("url"), item.get("tier"), item.get("deadline_at"), item.get("deadline_kind")) for item in hackathon_events],
        sort_keys=True,
    )
    old_hash = load_hash()

    print(
        f"  Raw: {stats['raw_count']} → Filtered: {stats['filtered_count']} "
        f"from the existing Simplify feed ({stats['elapsed_seconds']}s)"
    )
    print(
        f"  Removed {purge_stats['closed']} closed, {purge_stats['expired']} older than "
        f"{purge_stats['max_age_days']} days"
    )
    print(f"  Open listings: {len(merged)}")

    if new_hash != old_hash or args.force:
        save_json(LISTINGS_PATH, merged)
        save_hackathons(hackathon_events)
        save_hash(new_hash)
        regenerate_readme(merged, hackathon_events)
        print("listings.json and boards updated.")
    else:
        print("No listing changes — left the boards as they are.")
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
            listing["program"] = classify_program(listing)
            listing["track"] = (
                "new_grad" if NEW_GRAD_TITLE_PATTERN.search(listing.get("title") or "") else "intern"
            )
            listing.pop("terms", None)
            by_url[url] = listing

    merged, _purge_stats = finalize_listings(list(by_url.values()))
    save_json(LISTINGS_PATH, merged)
    save_hash(listings_fingerprint(merged))
    save_json(state_path, {"offset": next_offset})
    regenerate_readme(merged)
    print(f"Batch done ({len(batch)} companies). Next offset: {next_offset}")
    return 0


def cmd_readme() -> int:
    listings = load_json(LISTINGS_PATH)
    if not isinstance(listings, list):
        listings = []
    listings, purge_stats = finalize_listings(listings)
    save_json(LISTINGS_PATH, listings)
    save_hash(listings_fingerprint(listings))
    print(
        f"Removed {purge_stats['closed']} closed, {purge_stats['expired']} older than "
        f"{purge_stats['max_age_days']} days"
    )
    regenerate_readme(listings)
    return 0


def cmd_add_manual(args) -> int:
    existing = load_json(LISTINGS_PATH)
    if not isinstance(existing, list):
        existing = []

    now = int(time.time())
    from scrapers.base import make_listing_id

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
        "active": True,
        "is_visible": True,
        "source": args.contributor,
        "date_posted": now,
        "date_updated": now,
        "category": "",
    }
    listing["program"] = classify_program(listing)
    listing["track"] = (
        "new_grad" if NEW_GRAD_TITLE_PATTERN.search(listing["title"]) else "intern"
    )

    by_url = {item["url"]: item for item in existing if item.get("url")}
    by_url[listing["url"]] = listing
    merged, _purge_stats = finalize_listings(list(by_url.values()))
    save_json(LISTINGS_PATH, merged)
    save_hash(listings_fingerprint(merged))
    regenerate_readme(merged)
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
