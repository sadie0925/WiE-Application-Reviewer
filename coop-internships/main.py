#!/usr/bin/env python3
"""CLI for syncing co-op/internship listings and updating README."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from details import apply_details, fetch_missing, load_cache, save_cache
from hackathons import fetch_hackathons
from programs import fetch_programs
from readme_generator import update_readme
from scrapers import scrape_company
from scrapers.filters import (
    NEW_GRAD_TITLE_PATTERN,
    classify_program,
    is_software_new_grad,
    listing_added_at,
    purge_listings,
)
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
PROGRAMS_PATH = ROOT / "programs.json"


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
        title = listing.get("title") or ""
        if listing.get("track") not in {"intern", "new_grad"}:
            listing["track"] = (
                "new_grad" if NEW_GRAD_TITLE_PATTERN.search(title) else "intern"
            )
        if listing["track"] == "new_grad":
            # New-grad boards are software engineering only; the rest is purged.
            listing["program"] = "cs" if is_software_new_grad(listing) else "other"
        else:
            listing["program"] = classify_program(listing)
    return listings


def _load_limits() -> tuple[int, int]:
    config_path = ROOT / "config.json"
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        return int(cfg.get("max_age_days", 30)), int(cfg.get("new_grad_max_age_days", 60))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 30, 60


def enrich_with_details(listings: list[dict], *, fetch: bool) -> None:
    """Attach pay / work auth / term / job function from each Simplify posting page.

    The GitHub feeds have none of this, so without it those columns stay blank.
    Only postings not already in details-cache.json are fetched.
    """
    cache = load_cache()
    if fetch:
        intern_days, new_grad_days = _load_limits()
        now = time.time()
        live = []
        for item in listings:
            if item.get("active") is False or item.get("is_visible") is False:
                continue
            days = new_grad_days if item.get("track") == "new_grad" else intern_days
            if now - listing_added_at(item) <= days * 86400:
                live.append(item)
        try:
            fetched = fetch_missing(live, cache)
            print(f"  Fetched posting details for {fetched} new listings")
        except Exception as exc:  # never block the board update on this
            print(f"  Posting detail fetch failed: {exc}", file=sys.stderr)
        save_cache(cache, {item.get("id") for item in live if item.get("id")})
    apply_details(listings, cache)


def finalize_listings(listings: list[dict]) -> tuple[list[dict], dict]:
    """Tag listings, then drop closed ones and anything older than max_age_days."""
    config_path = ROOT / "config.json"
    max_age_days = 30
    new_grad_max_age_days = 60
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            max_age_days = int(cfg.get("max_age_days", 30))
            new_grad_max_age_days = int(cfg.get("new_grad_max_age_days", 60))
        except (ValueError, TypeError, json.JSONDecodeError):
            max_age_days = 30
            new_grad_max_age_days = 60
    enrich_with_details(listings, fetch=False)
    prepared = annotate_programs(listings)
    kept, stats = purge_listings(
        prepared,
        max_age_days=max_age_days,
        new_grad_max_age_days=new_grad_max_age_days,
    )
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


def regenerate_readme(
    listings: list[dict],
    hackathons: list[dict] | None = None,
    programs: list[dict] | None = None,
) -> None:
    update_readme(README_PATH, listings, hackathons, programs)
    print(f"Updated listings section in {README_PATH}")


def cmd_sync(args) -> int:
    """Sync from Simplify public feed (primary, low-load)."""
    existing = load_json(LISTINGS_PATH)
    if not isinstance(existing, list):
        existing = []

    print("Fetching Simplify community feed (1 HTTP request)...")
    simplify_listings, stats = sync()

    combined = merge_with_community(simplify_listings, existing)
    print("Fetching pay / work auth / term from posting pages (new listings only)...")
    enrich_with_details(combined, fetch=True)
    merged, purge_stats = finalize_listings(combined)
    print("Fetching hackathons (MLH, Devpost, and Waterloo sources)...")
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

    print("Fetching early undergrad programs from company career pages...")
    try:
        program_rows = fetch_programs()
    except Exception as exc:
        print(f"  Program fetch failed: {exc}", file=sys.stderr)
        program_rows = []
        if PROGRAMS_PATH.exists():
            saved = load_json(PROGRAMS_PATH)
            program_rows = saved if isinstance(saved, list) else []
    print(f"  Early programs still open: {len(program_rows)}")

    new_hash = listings_fingerprint(merged) + "|" + json.dumps(
        {
            "hackathons": [
                (item.get("name"), item.get("url"), item.get("tier"), item.get("deadline_at"), item.get("deadline_kind"))
                for item in hackathon_events
            ],
            "programs": [
                (item.get("company"), item.get("name"), item.get("url"), item.get("deadline_at"), item.get("pay"), item.get("audience"))
                for item in program_rows
            ],
        },
        sort_keys=True,
    )
    old_hash = load_hash()

    print(
        f"  Raw: {stats['raw_count']} → Filtered: {stats['filtered_count']} "
        f"({stats.get('intern_count', '?')} intern, {stats.get('new_grad_count', '?')} new-grad) "
        f"in {stats['elapsed_seconds']}s"
    )
    print(
        f"  Removed {purge_stats['closed']} closed, {purge_stats['expired']} older than "
        f"{purge_stats['max_age_days']} days"
    )
    print(f"  Open listings: {len(merged)}")

    if new_hash != old_hash or args.force:
        save_json(LISTINGS_PATH, merged)
        save_hackathons(hackathon_events)
        save_json(PROGRAMS_PATH, program_rows)
        save_hash(new_hash)
        regenerate_readme(merged, hackathon_events, program_rows)
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
