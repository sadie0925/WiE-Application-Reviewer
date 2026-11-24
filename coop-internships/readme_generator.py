"""Write the listings index and one page per board. Same listings, split for reading."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from hackathons import drop_past_deadlines
from scrapers.filters import classify_program, hourly_wage_label, work_auth_label, work_term_label
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
        "blurb": "Other co-ops and internships in Canada (not software).",
        "country": "Canada",
        "program": "other",
        "track": "intern",
    },
    {
        "filename": "us-other.md",
        "title": "United States — Other internships",
        "blurb": "Other co-ops and internships in the United States (not software).",
        "country": "United States",
        "program": "other",
        "track": "intern",
    },
    {
        "filename": "canada-new-grad.md",
        "title": "Canada — Software new grad",
        "blurb": "Software engineering new-grad and entry-level roles in Canada.",
        "country": "Canada",
        "program": "cs",
        "track": "new_grad",
    },
    {
        "filename": "us-new-grad.md",
        "title": "United States — Software new grad",
        "blurb": "Software engineering new-grad and entry-level roles in the United States.",
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
    # "\$" stops GitHub from rendering "$20–$50" as a math formula.
    return text.replace("|", "\\|").replace("$", "\\$")


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


HOT_PATH = Path(__file__).parent / "hot-companies.json"
_COMPANY_SUFFIX = re.compile(r"[,.]?\s+(inc|llc|ltd|corp|corporation|co|company|group|holdings|technologies|labs)\.?$", re.I)


def _company_key(name: str) -> str:
    key = re.sub(r"\s+", " ", (name or "").strip().lower())
    while True:
        trimmed = _COMPANY_SUFFIX.sub("", key).strip()
        if trimmed == key:
            return key
        key = trimmed


def _load_hot() -> tuple[set[str], float]:
    try:
        data = json.loads(HOT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(), 50.0
    names = {_company_key(name) for name in data.get("companies") or [] if isinstance(name, str)}
    return names, float(data.get("pay_over_per_hour") or 50)


_HOT_NAMES, _HOT_PAY = _load_hot()


def _is_hot(listing: dict, pay: str) -> bool:
    """🔥 for a popular tech / quant company, or a role paying over $50/hr."""
    name = listing.get("company_name") or ""
    if _company_key(name) in _HOT_NAMES or name.strip().lower() in _HOT_NAMES:
        return True
    amounts = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", pay)]
    return bool(amounts) and pay.endswith("/hr") and max(amounts) > _HOT_PAY


def _table(listings: list[dict]) -> list[str]:
    lines = [
        "| Company | Role | Location | Term | Work auth | Pay | Added | Apply |",
        "| ------- | ---- | -------- | ---- | --------- | --- | ----- | ----- |",
    ]
    for listing in sorted(listings, key=_sort_key):
        company = _escape_md(listing.get("company_name", "—"))
        title = _escape_md(listing.get("title", "—"))
        location = _format_locations(listing)
        term = _escape_md(work_term_label(listing))
        auth = _escape_md(work_auth_label(listing))
        raw_pay = hourly_wage_label(listing)
        pay = _escape_md(raw_pay)
        if _is_hot(listing, raw_pay):
            company = f"🔥 {company}"
        added = format_date(int(listing.get("date_posted") or 0))
        url = listing.get("url", "")
        apply_link = f"[Apply]({url})" if url else "—"
        lines.append(
            f"| {company} | {title} | {location} | {term} | {auth} | {pay} | {added} | {apply_link} |"
        )
    return lines


def _render_board(board: dict, listings: list[dict], now: str, max_age_days: int) -> str:
    rows = [item for item in listings if _matches(item, board)]
    age_note = (
        f"removed when closed or after {max_age_days} days"
        if board.get("track") == "intern"
        else "removed when closed or after 60 days"
    )
    lines = [
        f"# {board['title']}",
        "",
        board["blurb"],
        "",
        f"**{len(rows)} open** · newest first · {age_note} · Updated {now}",
        "",
        "**Term**: Fall, Winter/Spring, or Summer"
        + (" (new-grad roles only show one when the posting gives a start season)" if board.get("track") == "new_grad" else "")
        + ". **Work auth**: citizenship, clearance, or visa limits the posting states. "
        "**Pay**: per hour; salaries are converted at 2,080 hours a year. "
        "🔥 = popular tech or quant company, or pays over \\$50/hr. "
        "A blank cell means the posting doesn't say.",
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
    """Show only application/registration close. Blank when the organizer did not publish one."""
    if event.get("deadline_kind") != "application":
        return ""
    raw = event.get("deadline_at") or ""
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(TORONTO).strftime("%Y-%m-%d")
    except ValueError:
        return raw


def _format_when(event: dict) -> str:
    if event.get("month_only") and event.get("when"):
        return event["when"]  # organizer has only announced the month
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
        "Upcoming hackathons and innovation challenges, Waterloo clubs first. "
        "**Deadline** is when applications close (blank if the organizer hasn't posted one). "
        "Events are removed once applications close or the event starts.",
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


def _render_programs_board(programs: list[dict], now: str) -> str:
    lines = [
        "# Early undergrad programs",
        "",
        "Fellowships, insight programs, and first- and second-year programs for software students. "
        "Removed once applications close. A blank cell means the company doesn't say.",
        "",
        f"**{len(programs)} open** · soonest deadline first · Updated {now}",
        "",
        "[All boards](../README.md)",
        "",
    ]
    if not programs:
        lines.extend(["No open programs on this board right now.", ""])
        return "\n".join(lines)
    lines.extend([
        "| Company | Program | Location | Term | Deadline | Pay | Who | Link |",
        "| ------- | ------- | -------- | ---- | -------- | --- | --- | ---- |",
    ])
    for program in programs:
        company = _escape_md(program.get("company") or "—")
        name = _escape_md(program.get("name") or "—")
        location = _escape_md(program.get("location") or "")
        term = _escape_md(program.get("term") or "")
        deadline = _escape_md(_format_deadline(program))
        pay = _escape_md(program.get("pay") or "")
        audience = _escape_md(program.get("audience") or "")
        url = program.get("url") or ""
        link = f"[Open]({url})" if url else "—"
        lines.append(
            f"| {company} | {name} | {location} | {term} | {deadline} | {pay} | {audience} | {link} |"
        )
    lines.append("")
    return "\n".join(lines)


def _load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _load_hackathons(readme_path: Path) -> list[dict]:
    return _load_json_list(readme_path.parent / "hackathons.json")


def _load_programs(readme_path: Path) -> list[dict]:
    return _load_json_list(readme_path.parent / "programs.json")


def update_readme(
    readme_path,
    listings: list[dict],
    hackathons: list[dict] | None = None,
    programs: list[dict] | None = None,
) -> None:
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

    if programs is None:
        programs = _load_programs(readme_path)
    programs = drop_past_deadlines(programs)
    (boards_dir / "programs.md").write_text(_render_programs_board(programs, now), encoding="utf-8")

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
        f"Internships are removed after **{max_age_days} days** and new-grad roles after **60 days**, "
        "or sooner if the posting closes. "
        "Roles open in both countries appear on both country pages.",
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
    lines.append(
        f"| [Early undergrad programs](boards/programs.md) | {len(programs)} |"
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
