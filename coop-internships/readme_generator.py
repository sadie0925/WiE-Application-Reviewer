"""Write the listings index and one page per board. Same listings, split for reading."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from hackathons import drop_past_deadlines
from scrapers.filters import classify_program, work_auth_label, work_term_label
from scrapers.location import listing_countries

MARKER_START = "<!-- LISTINGS:START -->"
MARKER_END = "<!-- LISTINGS:END -->"

TORONTO = ZoneInfo("America/Toronto")

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
        "blurb": "Software new-grad roles in Canada from the same feed.",
        "country": "Canada",
        "program": "cs",
        "track": "new_grad",
    },
    {
        "filename": "us-new-grad.md",
        "title": "United States — Software new grad",
        "blurb": "Software new-grad roles in the United States from the same feed.",
        "country": "United States",
        "program": "cs",
        "track": "new_grad",
    },
)


def _sort_key(listing: dict) -> tuple:
    posted = int(listing.get("date_posted") or 0)
    return (
        -posted,
        (listing.get("company_name") or "").lower(),
        (listing.get("title") or "").lower(),
    )


def _max_age_days() -> int:
    path = Path(__file__).parent / "config.json"
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("max_age_days", 30))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 30


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


def _table(listings: list[dict]) -> list[str]:
    lines = [
        "| Company | Role | Location | Term | Work auth | Added | Apply |",
        "| ------- | ---- | -------- | ---- | --------- | ----- | ----- |",
    ]
    for listing in sorted(listings, key=_sort_key):
        company = _escape_md(listing.get("company_name", "—"))
        title = _escape_md(listing.get("title", "—"))
        location = _format_locations(listing)
        term = _escape_md(work_term_label(listing))
        auth = _escape_md(work_auth_label(listing))
        added = format_date(int(listing.get("date_posted") or 0))
        url = listing.get("url", "")
        apply_link = f"[Apply]({url})" if url else "—"
        lines.append(
            f"| {company} | {title} | {location} | {term} | {auth} | {added} | {apply_link} |"
        )
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
        "Term is filled only when the title or description says Winter, Spring, Fall, or Summer. "
        "Summer is shown as Spring, which is Waterloo's May–August term. "
        "Work auth is filled only when the posting says it sponsors a work permit, "
        "or that it requires US citizenship, a US person, permanent residence, "
        "unrestricted work authorization, or a US clearance. Otherwise that cell is blank.",
        "",
        "[All boards](../README.md)",
        "",
    ]
    if rows:
        lines.extend(_table(rows))
    else:
        lines.append("No open listings on this board right now.")
    lines.append("")
    return "\n".join(lines)


def _format_deadline(event: dict) -> str:
    raw = event.get("deadline_at") or ""
    if not raw:
        return "—"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        label = parsed.astimezone(TORONTO).strftime("%Y-%m-%d")
    except ValueError:
        return raw
    if event.get("deadline_kind") == "application":
        return f"{label} applications"
    if event.get("deadline_kind") == "event_start":
        return f"{label} event start"
    return label


def _format_when(event: dict) -> str:
    starts = event.get("starts_at") or ""
    if starts:
        try:
            parsed = datetime.fromisoformat(starts.replace("Z", "+00:00"))
            return parsed.astimezone(TORONTO).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return event.get("when") or "—"


def _render_hackathon_board(events: list[dict], now: str) -> str:
    uw = [item for item in events if item.get("tier") == "uw"]
    major = [item for item in events if item.get("tier") != "uw"]
    lines = [
        "# Hackathons and innovation challenges",
        "",
        "Waterloo clubs and committees are listed first "
        "(EngSoc, UW clubs, WiCS, WiE, design teams, Velocity, the IDEAs Clinic, and Socratica). "
        "Each run also checks Hackathon Radar's Waterloo page, Communitech's events page, "
        "MLH, and Devpost. "
        "Other Canada and US hackathons follow. "
        "A row is removed as soon as its deadline passes. "
        "That deadline is the application close when the organizer publishes one. "
        "If they do not, the event start is used. This is separate from the 30-day job rule.",
        "",
        f"**{len(events)} upcoming** · {len(uw)} Waterloo · {len(major)} other Canada/US · Updated {now}",
        "",
        "[All boards](../README.md)",
        "",
        "## Waterloo clubs and committees",
        "",
    ]
    lines.extend(_hackathon_table(uw))
    lines.extend(["", "## Other Canada and US hackathons", ""])
    lines.extend(_hackathon_table(major))
    lines.append("")
    return "\n".join(lines)


def _hackathon_table(events: list[dict]) -> list[str]:
    if not events:
        return ["None open right now.", ""]
    lines = [
        "| Event | Where | When | Deadline | Link |",
        "| ----- | ----- | ---- | -------- | ---- |",
    ]
    for event in events:
        name = _escape_md(event.get("name") or "—")
        where = _escape_md(event.get("location") or "—")
        when = _escape_md(_format_when(event))
        deadline = _escape_md(_format_deadline(event))
        url = event.get("url") or ""
        link = f"[Open]({url})" if url else "—"
        lines.append(f"| {name} | {where} | {when} | {deadline} | {link} |")
    return lines


def _load_hackathons(readme_path: Path) -> list[dict]:
    path = readme_path.parent / "hackathons.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def update_readme(readme_path, listings: list[dict], hackathons: list[dict] | None = None) -> None:
    readme_path = Path(readme_path)
    boards_dir = readme_path.parent / "boards"
    boards_dir.mkdir(exist_ok=True)

    active = [item for item in listings if item.get("active") and item.get("is_visible", True)]
    now = datetime.now(TORONTO).strftime("%Y-%m-%d %H:%M ET")
    max_age_days = _max_age_days()

    if hackathons is None:
        hackathons = _load_hackathons(readme_path)
    hackathons = drop_past_deadlines(hackathons)
    hackathon_page = _render_hackathon_board(hackathons, now)
    (boards_dir / "hackathons.md").write_text(hackathon_page, encoding="utf-8")

    counts = []
    for board in BOARDS:
        matched = [item for item in active if _matches(item, board)]
        counts.append((board, len(matched)))
        (boards_dir / board["filename"]).write_text(
            _render_board(board, active, now, max_age_days),
            encoding="utf-8",
        )

    lines = [
        MARKER_START,
        "",
        f"**{len(active)} open listings** · newest first · Updated {now}",
        "",
        f"Same Simplify feed as before. A listing is removed when the application is closed, "
        f"or when it was added more than **{max_age_days} days** ago. "
        "Roles in both countries show up on both pages.",
        "",
        "| Board | Open |",
        "| ----- | ---- |",
    ]
    for board, count in counts:
        lines.append(f"| [{board['title']}](boards/{board['filename']}) | {count} |")
    uw_count = sum(1 for item in hackathons if item.get("tier") == "uw")
    lines.append(
        f"| [Hackathons and innovation challenges](boards/hackathons.md) | {len(hackathons)} "
        f"({uw_count} Waterloo first) |"
    )
    lines.extend(["", MARKER_END])
    section = "\n".join(lines)

    content = readme_path.read_text(encoding="utf-8")
    if MARKER_START in content and MARKER_END in content:
        before = content[: content.index(MARKER_START)]
        after = content[content.index(MARKER_END) + len(MARKER_END) :]
        readme_path.write_text(before + section + after, encoding="utf-8")
    else:
        readme_path.write_text(content.rstrip() + "\n\n" + section + "\n", encoding="utf-8")

    print(f"Updated {readme_path.name} and {len(BOARDS)} boards")
    for board, count in counts:
        print(f"  {board['filename']}: {count}")
