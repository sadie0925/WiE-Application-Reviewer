"""Write the listings index and one markdown page per board."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scrapers.filters import classify_program
from scrapers.location import listing_countries, location_countries

MARKER_START = "<!-- LISTINGS:START -->"
MARKER_END = "<!-- LISTINGS:END -->"

TORONTO = ZoneInfo("America/Toronto")

# Newest postings first. Company name only breaks ties on the same day.
def _sort_key(listing: dict) -> tuple:
    posted = int(listing.get("date_posted") or 0)
    return (
        -posted,
        (listing.get("company_name") or "").lower(),
        (listing.get("title") or "").lower(),
    )


BOARDS = (
    {
        "filename": "canada-software.md",
        "title": "Canada — Software internships",
        "blurb": "Software, data, and AI co-ops and internships in Canada.",
        "country": "Canada",
        "program": "cs",
        "track": "intern",
    },
    {
        "filename": "us-software.md",
        "title": "United States — Software internships",
        "blurb": "Software, data, and AI co-ops and internships in the United States.",
        "country": "United States",
        "program": "cs",
        "track": "intern",
    },
    {
        "filename": "canada-other.md",
        "title": "Canada — Other internships",
        "blurb": "Co-ops and internships in Canada that are not software engineering.",
        "country": "Canada",
        "program": "other",
        "track": "intern",
    },
    {
        "filename": "us-other.md",
        "title": "United States — Other internships",
        "blurb": "Co-ops and internships in the United States that are not software engineering.",
        "country": "United States",
        "program": "other",
        "track": "intern",
    },
    {
        "filename": "canada-new-grad.md",
        "title": "Canada — Software new grad",
        "blurb": "Full-time software new-grad roles in Canada.",
        "country": "Canada",
        "program": "cs",
        "track": "new_grad",
    },
    {
        "filename": "us-new-grad.md",
        "title": "United States — Software new grad",
        "blurb": "Full-time software new-grad roles in the United States.",
        "country": "United States",
        "program": "cs",
        "track": "new_grad",
    },
)


def _max_age_days() -> int:
    path = Path(__file__).parent / "config.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("max_age_days", 30))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 30


def format_date(timestamp: int) -> str:
    if not timestamp:
        return "—"
    return datetime.fromtimestamp(timestamp, tz=TORONTO).strftime("%Y-%m-%d")


def _escape_md(text: str) -> str:
    return text.replace("|", "\\|")


def _format_locations(listing: dict, country: str | None = None) -> str:
    locs = list(listing.get("locations") or [])
    if not locs:
        return "—"
    if country:
        def _rank(loc: str) -> int:
            countries = location_countries(loc)
            if country in countries and len(countries) == 1:
                return 0
            if country in countries:
                return 1
            return 2

        locs.sort(key=_rank)
    shown = locs[:2]
    text = ", ".join(shown)
    if len(locs) > 2:
        text += f" (+{len(locs) - 2})"
    return _escape_md(text)


def _matches(listing: dict, board: dict) -> bool:
    if not listing.get("active") or listing.get("is_visible") is False:
        return False
    program = listing.get("program") or classify_program(listing)
    track = listing.get("track") or "intern"
    if program != board["program"] or track != board["track"]:
        return False
    return board["country"] in listing_countries(listing)


def _table(listings: list[dict], country: str) -> list[str]:
    lines = [
        "| Company | Role | Location | Added | Apply |",
        "| ------- | ---- | -------- | ----- | ----- |",
    ]
    for listing in sorted(listings, key=_sort_key):
        company = _escape_md(listing.get("company_name", "—"))
        title = _escape_md(listing.get("title", "—"))
        location = _format_locations(listing, country)
        added = format_date(int(listing.get("date_posted") or 0))
        url = listing.get("url", "")
        apply_link = f"[Apply]({url})" if url else "—"
        lines.append(f"| {company} | {title} | {location} | {added} | {apply_link} |")
    return lines


def _render_board(board: dict, listings: list[dict], now: str, max_age_days: int) -> str:
    rows = [item for item in listings if _matches(item, board)]
    lines = [
        f"# {board['title']}",
        "",
        board["blurb"],
        "",
        f"**{len(rows)} open** · newest first · "
        f"removed when the application closes or after {max_age_days} days · "
        f"Updated {now}",
        "",
        "[All boards](../README.md)",
        "",
    ]
    if rows:
        lines.extend(_table(rows, board["country"]))
    else:
        lines.append("No open listings on this board right now.")
    lines.append("")
    return "\n".join(lines)


def generate_listings_section(counts: list[tuple[dict, int]], total: int, now: str, max_age_days: int) -> str:
    lines = [
        MARKER_START,
        "",
        f"**{total} open listings** across the boards below · newest first · "
        f"Updated {now}",
        "",
        f"A listing is removed when Simplify marks the application closed, "
        f"or when it was added more than **{max_age_days} days** ago. "
        "Roles posted in both countries show up on both pages.",
        "",
        "| Board | Open |",
        "| ----- | ---- |",
    ]
    for board, count in counts:
        lines.append(f"| [{board['title']}](boards/{board['filename']}) | {count} |")
    lines.extend(["", MARKER_END])
    return "\n".join(lines)


def update_readme(readme_path, listings: list[dict]) -> None:
    readme_path = Path(readme_path)
    boards_dir = readme_path.parent / "boards"
    boards_dir.mkdir(exist_ok=True)

    active = [item for item in listings if item.get("active") and item.get("is_visible", True)]
    now = datetime.now(TORONTO).strftime("%Y-%m-%d %H:%M ET")
    max_age_days = _max_age_days()

    counts: list[tuple[dict, int]] = []
    for board in BOARDS:
        matched = [item for item in active if _matches(item, board)]
        counts.append((board, len(matched)))
        page = _render_board(board, active, now, max_age_days)
        (boards_dir / board["filename"]).write_text(page, encoding="utf-8")

    # A role in both countries is counted on each page, so sum(counts) can exceed total.
    section = generate_listings_section(counts, len(active), now, max_age_days)
    content = readme_path.read_text(encoding="utf-8")

    if MARKER_START in content and MARKER_END in content:
        before = content[: content.index(MARKER_START)]
        after = content[content.index(MARKER_END) + len(MARKER_END) :]
        readme_path.write_text(before + section + after, encoding="utf-8")
    else:
        readme_path.write_text(content.rstrip() + "\n\n" + section + "\n", encoding="utf-8")

    print(f"Updated {readme_path.name} and {len(BOARDS)} boards in {boards_dir}")
    for board, count in counts:
        print(f"  {board['filename']}: {count}")
