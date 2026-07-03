"""Generate README listings section from listings.json."""

from datetime import datetime, timezone

MARKER_START = "<!-- LISTINGS:START -->"
MARKER_END = "<!-- LISTINGS:END -->"


def format_date(timestamp: int) -> str:
    if not timestamp:
        return "—"
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")


def generate_listings_section(listings: list[dict]) -> str:
    active = [l for l in listings if l.get("active") and l.get("is_visible", True)]
    inactive_count = len(listings) - len(active)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        MARKER_START,
        "",
        f"**{len(active)} active listings** · {inactive_count} inactive · Last updated: {now}",
        "",
        "## Active Listings",
        "",
        "| Company | Role | Location | Term | Posted | Apply |",
        "| ------- | ---- | -------- | ---- | ------ | ----- |",
    ]

    for listing in active:
        company = listing.get("company_name", "—")
        title = listing.get("title", "—").replace("|", "\\|")
        locations = ", ".join(listing.get("locations", [])) or "—"
        terms = ", ".join(listing.get("terms", [])) or "—"
        posted = format_date(listing.get("date_posted", 0))
        url = listing.get("url", "")
        apply_link = f"[Apply]({url})" if url else "—"
        lines.append(f"| {company} | {title} | {locations} | {terms} | {posted} | {apply_link} |")

    if not active:
        lines.append("| — | No active listings yet. Run the scraper! | — | — | — | — |")

    lines.extend(["", MARKER_END])
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
