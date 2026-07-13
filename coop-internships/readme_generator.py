"""Generate README listings section grouped by country + CS vs other."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from scrapers.filters import classify_program
from scrapers.location import COUNTRY_ORDER, get_board_country

MARKER_START = "<!-- LISTINGS:START -->"
MARKER_END = "<!-- LISTINGS:END -->"

TORONTO = ZoneInfo("America/Toronto")

PROGRAM_ORDER = {"cs": 0, "other": 1}
PROGRAM_LABELS = {
    "cs": "CS / Software",
    "other": "Other programs",
}


def format_date(timestamp: int) -> str:
    if not timestamp:
        return "—"
    return datetime.fromtimestamp(timestamp, tz=TORONTO).strftime("%Y-%m-%d")


def _escape_md(text: str) -> str:
    return text.replace("|", "\\|")


def _format_locations(listing: dict) -> str:
    locs = listing.get("locations") or []
    if not locs:
        return "—"
    # Keep table readable: show up to 2 locations
    shown = locs[:2]
    text = ", ".join(shown)
    if len(locs) > 2:
        text += f" (+{len(locs) - 2})"
    return _escape_md(text)


def generate_listings_section(listings: list[dict]) -> str:
    active = [l for l in listings if l.get("active") and l.get("is_visible", True)]
    inactive_count = len(listings) - len(active)
    now = datetime.now(TORONTO).strftime("%Y-%m-%d %H:%M ET")

    boards: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for listing in active:
        country = get_board_country(listing)
        program = listing.get("program") or classify_program(listing)
        if program not in PROGRAM_LABELS:
            program = "other"
        boards[(country, program)].append(listing)

    cs_count = sum(1 for l in active if (l.get("program") or classify_program(l)) == "cs")
    other_count = len(active) - cs_count

    lines = [
        MARKER_START,
        "",
        f"**{len(active)} active US/Canada co-op & intern listings** · "
        f"{cs_count} CS/software · {other_count} other programs · "
        f"{inactive_count} inactive · Last updated: {now}",
        "",
        "Grouped by **country** (Canada / US), then **CS/software** vs **other programs**. "
        "Term/season is omitted unless clearly needed — many feeds stamp seasons incorrectly.",
        "",
    ]

    if not active:
        lines.append("No active listings. Run `python main.py sync`.")
        lines.extend(["", MARKER_END])
        return "\n".join(lines)

    # Country major sections, then CS then other within each country
    countries_present = sorted(
        {c for (c, _) in boards},
        key=lambda c: COUNTRY_ORDER.get(c, 99),
    )

    for country in countries_present:
        lines.append(f"## {country}")
        lines.append("")

        for program in ("cs", "other"):
            board_listings = boards.get((country, program), [])
            if not board_listings:
                continue

            label = PROGRAM_LABELS[program]
            lines.append(f"### {label} ({len(board_listings)})")
            lines.append("")
            lines.append("| Company | Role | Location | Posted | Apply |")
            lines.append("| ------- | ---- | -------- | ------ | ----- |")

            for listing in sorted(
                board_listings,
                key=lambda x: (x.get("company_name", ""), x.get("title", "")),
            ):
                company = _escape_md(listing.get("company_name", "—"))
                title = _escape_md(listing.get("title", "—"))
                location = _format_locations(listing)
                posted = format_date(listing.get("date_posted", 0))
                url = listing.get("url", "")
                apply_link = f"[Apply]({url})" if url else "—"
                lines.append(
                    f"| {company} | {title} | {location} | {posted} | {apply_link} |"
                )

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
