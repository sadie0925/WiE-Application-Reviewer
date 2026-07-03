"""Generate README listings section grouped by location."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from scrapers.location import COUNTRY_ORDER, get_primary_location

MARKER_START = "<!-- LISTINGS:START -->"
MARKER_END = "<!-- LISTINGS:END -->"

TORONTO = ZoneInfo("America/Toronto")


def format_date(timestamp: int) -> str:
    if not timestamp:
        return "—"
    return datetime.fromtimestamp(timestamp, tz=TORONTO).strftime("%Y-%m-%d")

def _escape_md(text: str) -> str:
    return text.replace("|", "\\|")


def generate_listings_section(listings: list[dict]) -> str:
    active = [l for l in listings if l.get("active") and l.get("is_visible", True)]
    inactive_count = len(listings) - len(active)
    now = datetime.now(TORONTO).strftime("%Y-%m-%d %H:%M ET")

    boards: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for listing in active:
        country, location = get_primary_location(listing)
        boards[(country, location)].append(listing)

    lines = [
        MARKER_START,
        "",
        f"**{len(active)} active US/Canada co-op & intern listings** · "
        f"{inactive_count} inactive · Last updated: {now}",
        "",
        "",
    ]

    if not active:
        lines.append("No active listings. Run `python main.py sync`.")
        lines.extend(["", MARKER_END])
        return "\n".join(lines)

    sorted_boards = sorted(
        boards.items(),
        key=lambda item: (
            COUNTRY_ORDER.get(item[0][0], 99),
            -len(item[1]),
            item[0][1],
        ),
    )

    current_country = None
    for (country, location), board_listings in sorted_boards:
        if country != current_country:
            if current_country is not None:
                lines.append("")
            lines.append(f"## {country}")
            lines.append("")
            current_country = country

        lines.append(f"### {location} ({len(board_listings)})")
        lines.append("")
        lines.append("| Company | Role | Term | Posted | Apply |")
        lines.append("| ------- | ---- | ---- | ------ | ----- |")

        for listing in sorted(board_listings, key=lambda x: (x.get("company_name", ""), x.get("title", ""))):
            company = _escape_md(listing.get("company_name", "—"))
            title = _escape_md(listing.get("title", "—"))
            terms = _escape_md(", ".join(listing.get("terms", [])) or "—")
            posted = format_date(listing.get("date_posted", 0))
            url = listing.get("url", "")
            apply_link = f"[Apply]({url})" if url else "—"
            lines.append(f"| {company} | {title} | {terms} | {posted} | {apply_link} |")

        lines.append("")

    lines.append(MARKER_END)
    return "\n".join(lines)


def update_readme(readme_path, listings: list[dict]) -> None:
    section = generate_listings_section(listings)
    content = readme_path.read_text(encoding="utf-8")

    if MARKER_START in content and MARKER_END in content:
        before = content[: content.index(MARKER_START)]
        after = content[content.index(MARKER_END) + len(MARKER_END) :]
        readme_path.write_text(before + section + after, encoding="utf-8")
    else:
        readme_path.write_text(content.rstrip() + "\n\n" + section + "\n", encoding="utf-8")
