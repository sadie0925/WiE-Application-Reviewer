"""Upcoming hackathons and innovation challenges for the boards.

Waterloo clubs and committees are listed first. Other Canada and US
hackathons, including Hack the North and Hack Western, follow.
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

USER_AGENT = "WiE-Coop-Listings/1.0 (github; educational)"
REQUEST_TIMEOUT = 30

# Major Canada/US hackathons. Hack the North is here on purpose, not in the
# Waterloo-club tier, even though it is hosted in Waterloo.
MAJOR_NAME_PATTERNS = re.compile(
    r"\b("
    r"hack\s*the\s*north|hackthenorth|"
    r"hack\s*western|western\s*hackathon|"
    r"hack\s*the\s*6ix|qhacks|mchacks|nwhacks|"
    r"uoft\s*hacks|hack\s*the\s*valley|delta\s*hacks|elle\s*hacks|"
    r"treehacks|pennapps|hackmit|cal\s*hacks|la\s*hacks|"
    r"hackdavis|hackprinceton|hackharvard|"
    r"hack\s*the\s*change|uottahack|hackville|makeuoft|"
    r"hack\s*the\s*globe|shehacks|technova|cuhacking|conuhacks"
    r")\b",
    re.IGNORECASE,
)

UW_STRONG_PATTERNS = re.compile(
    r"\b("
    r"engsoc|engineering\s+society|"
    r"uwaterloo|university\s+of\s+waterloo|"
    r"midnight\s+sun|watonomous|waterloop|uwaft|"
    r"formula\s+electric|concrete\s+toboggan|"
    r"waterloo\s+aerial|uworb|"
    r"uw\s+club|velocity|ideas\s+clinic|socratica|communitech"
    r")\b",
    re.IGNORECASE,
)

UW_WEAK_PATTERNS = re.compile(
    r"\b(wics|wie|women\s+in\s+computer\s+science|women\s+in\s+engineering)\b",
    re.IGNORECASE,
)

WATERLOO_CONTEXT = re.compile(r"\b(waterloo|uwaterloo)\b", re.IGNORECASE)

TORONTO = ZoneInfo("America/Toronto")

# Official public feeds. Instagram is not included; those posts are not a stable feed.
UW_EVENT_FEEDS = (
    "https://uwaterloo.ca/women-in-engineering/events/events.xml",
    "https://uwaterloo.ca/women-in-computer-science/events/events.xml",
    "https://uwaterloo.ca/engineering-ideas-clinic/events/events.xml",
)

HACKATHON_TITLE = re.compile(
    r"\b(hackathon|innovation\s+challenge|designathon|makeathon|buildathon)\b",
    re.IGNORECASE,
)

VELOCITY_INDEX = "https://www.velocityincubator.com/students"
IDEAS_INDEX = "https://uwaterloo.ca/engineering-ideas-clinic/"
RADAR_URL = "https://www.hackathonradar.com/discover/waterloo"
SOCRATICA_CALENDAR = "https://wygo.world/o/socratica"
COMMUNITECH_EVENTS = "https://www.communitech.ca/community/events/"
CHALLENGE_LINK = re.compile(r"challenge|hackathon|buildathon", re.IGNORECASE)
SOCRATICA_KEEP = re.compile(
    r"\b(hackathon|buildathon|innovation|challenge|symposium)\b",
    re.IGNORECASE,
)
LOCAL_SOURCES = {"uwaterloo", "velocity", "ideas-clinic", "socratica", "communitech"}

APPLICATION_DUE = re.compile(
    r"(?:applications?|registration|sign[\s-]?ups?)\s+(?:are\s+)?"
    r"(?:due|close[sd]?|deadline(?:\s+is)?)\s+(?:on\s+|by\s+)?"
    r"([A-Za-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)",
    re.IGNORECASE,
)

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

DEVPOST_SEARCHES = (
    "uwaterloo",
    "waterloo",
    "engsoc",
    "wics waterloo",
    "women in engineering waterloo",
    "hack the north",
    "hack western",
    "midnight sun",
    "watonomous",
)


def _get(url: str, **kwargs) -> requests.Response:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    headers.update(kwargs.pop("headers", {}))
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
    response.raise_for_status()
    return response


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _tier(name: str, location: str, url: str, organization: str = "") -> str | None:
    """Return 'uw' or 'major'. None means skip."""
    blob = " ".join([name, location, url, organization])
    if MAJOR_NAME_PATTERNS.search(name) or MAJOR_NAME_PATTERNS.search(organization):
        return "major"
    if UW_STRONG_PATTERNS.search(blob) and not MAJOR_NAME_PATTERNS.search(blob):
        return "uw"
    weak = UW_WEAK_PATTERNS.search(blob)
    waterloo = WATERLOO_CONTEXT.search(blob) or "uwaterloo.ca" in url.lower()
    if weak and waterloo:
        return "uw"
    return None


def _end_of_day(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 23, 59, 59, tzinfo=TORONTO)


def parse_loose_date(text: str, default_year: int) -> datetime | None:
    """Parse 'November 1st' or 'Nov 1, 2026' as the end of that day in Toronto."""
    cleaned = text.replace("\xa0", " ").replace(".", "")
    match = re.search(
        r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?",
        cleaned,
        re.IGNORECASE,
    )
    if not match:
        return None
    month = MONTHS.get(match.group(1).lower()[:3]) or MONTHS.get(match.group(1).lower())
    if not month:
        return None
    day = int(match.group(2))
    year = int(match.group(3)) if match.group(3) else default_year
    try:
        return _end_of_day(year, month, day)
    except ValueError:
        return None


def parse_application_deadline(page_text: str, default_year: int) -> datetime | None:
    plain = re.sub(r"<[^>]+>", " ", page_text)
    plain = html.unescape(plain).replace("\xa0", " ")
    match = APPLICATION_DUE.search(plain)
    if not match:
        return None
    return parse_loose_date(match.group(1), default_year)


def deadline_of(event: dict) -> datetime | None:
    return _parse_iso(event.get("deadline_at")) or _parse_iso(event.get("starts_at"))


def drop_past_deadlines(events: list[dict], now: datetime | None = None) -> list[dict]:
    """Remove a hackathon as soon as its deadline has passed.

    This is separate from the 30-day job rule. Application close is used when
    we have it. Otherwise the event start is the deadline.
    """
    current = now or datetime.now(timezone.utc)
    kept = []
    for event in events:
        deadline = deadline_of(event)
        if deadline is not None and deadline < current:
            continue
        ends = _parse_iso(event.get("ends_at"))
        if ends is not None and ends < current:
            continue
        kept.append(event)
    return kept


def fetch_mlh_events(now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    years = {current.year, current.year + 1}
    if current.month < 8:
        years.add(current.year - 1)

    events = []
    seen = set()
    for year in sorted(years):
        response = _get(
            f"https://mlh.io/seasons/{year}/events",
            headers={"Accept": "text/html"},
        )
        match = re.search(
            r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
            response.text,
            re.S,
        )
        if not match:
            continue
        payload = json.loads(html.unescape(match.group(1)))
        upcoming = (payload.get("props") or {}).get("upcomingEvents") or []
        for item in upcoming:
            venue = item.get("venueAddress") or {}
            country = (venue.get("country") or "").upper()
            name = item.get("name") or ""
            location = item.get("location") or ""
            url = item.get("websiteUrl") or ""
            if url.startswith("/"):
                url = "https://mlh.io" + url
            tier = _tier(name, location, url)
            if tier is None and country in {"CA", "US"}:
                tier = "major"
            if tier is None:
                continue
            ends = _parse_iso(item.get("endsAt"))
            starts = _parse_iso(item.get("startsAt"))
            # MLH does not publish application close. The row leaves when the event starts.
            if starts is not None and starts < current:
                continue
            if ends is not None and ends < current:
                continue
            key = name.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            events.append(
                {
                    "name": name.strip(),
                    "location": location or "—",
                    "url": url or "https://mlh.io" + (item.get("url") or ""),
                    "starts_at": item.get("startsAt") or "",
                    "ends_at": item.get("endsAt") or "",
                    "deadline_at": item.get("startsAt") or "",
                    "deadline_kind": "event_start",
                    "when": item.get("dateRange") or "",
                    "status": "Upcoming",
                    "tier": tier,
                    "source": "mlh",
                }
            )
    return events


def fetch_devpost_events(now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    events = []
    seen = set()
    for query in DEVPOST_SEARCHES:
        response = _get(
            "https://devpost.com/api/hackathons",
            params={"search": query, "status[]": ["open", "upcoming"]},
        )
        for item in response.json().get("hackathons") or []:
            name = item.get("title") or ""
            organization = item.get("organization_name") or ""
            location = ((item.get("displayed_location") or {}).get("location")) or ""
            url = item.get("url") or ""
            tier = _tier(name, location, url, organization)
            if tier is None:
                continue
            key = name.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            state = (item.get("open_state") or "").lower()
            if state not in {"open", "upcoming"}:
                continue
            period = item.get("submission_period_dates") or ""
            deadline = _submission_period_end(period, current.year)
            events.append(
                {
                    "name": name.strip(),
                    "location": location or "—",
                    "url": url,
                    "starts_at": "",
                    "ends_at": "",
                    "deadline_at": deadline.isoformat() if deadline else "",
                    "deadline_kind": "application" if deadline else "unknown",
                    "when": period,
                    "status": "Open" if state == "open" else "Upcoming",
                    "tier": tier,
                    "source": "devpost",
                }
            )
    return drop_past_deadlines(events, current)


def _submission_period_end(text: str, default_year: int) -> datetime | None:
    """Parse the end of a Devpost range like 'Oct 27 - Nov 27, 2026' or 'Nov 20 – 22, 2026'."""
    if not text:
        return None
    year_match = re.search(r"(20\d{2})", text)
    year = int(year_match.group(1)) if year_match else default_year
    parts = re.split(r"\s+[–-]\s+", text)
    end = parts[-1] if parts else text
    if not re.search(r"[A-Za-z]", end) and parts:
        month = re.match(r"([A-Za-z]+)", parts[0])
        end = f"{month.group(1)} {end}" if month else end
    return parse_loose_date(end, year)


def fetch_uw_events(now: datetime | None = None) -> list[dict]:
    """Hackathons published on Waterloo club and committee websites."""
    current = now or datetime.now(timezone.utc)
    events = []
    seen = set()
    for feed_url in UW_EVENT_FEEDS:
        try:
            response = _get(feed_url, headers={"Accept": "application/rss+xml, application/xml, text/xml"})
            root = ET.fromstring(response.content)
        except (requests.RequestException, ET.ParseError):
            continue
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = html.unescape(item.findtext("description") or "")
            if re.search(r"aged\s+11|high\s+school|grades?\s+\d", description, re.IGNORECASE):
                continue
            if not title or not link or not HACKATHON_TITLE.search(title):
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            start_match = re.search(r'datetime="([^"]+)"', description)
            starts = _parse_iso(start_match.group(1)) if start_match else None
            deadline = None
            deadline_kind = "event_start"
            try:
                page = _get(link, headers={"Accept": "text/html"})
                default_year = starts.year if starts else current.year
                found = parse_application_deadline(page.text, default_year)
                if found:
                    deadline = found
                    deadline_kind = "application"
            except requests.RequestException:
                pass
            if deadline is None and starts is not None:
                deadline = starts
            events.append(
                {
                    "name": title,
                    "location": "University of Waterloo",
                    "url": link,
                    "starts_at": starts.isoformat() if starts else "",
                    "ends_at": "",
                    "deadline_at": deadline.isoformat() if deadline else "",
                    "deadline_kind": deadline_kind,
                    "when": starts.astimezone(TORONTO).strftime("%Y-%m-%d") if starts else "",
                    "status": "Open" if deadline_kind == "application" else "Upcoming",
                    "tier": "uw",
                    "source": "uwaterloo",
                }
            )
    return drop_past_deadlines(events, current)


def _plain(page: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", page, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text))


def _page_title(page: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.IGNORECASE | re.S)
    if not match:
        match = re.search(r"<title[^>]*>(.*?)</title>", page, re.IGNORECASE | re.S)
    if not match:
        return ""
    title = re.sub(r"<[^>]+>", " ", match.group(1))
    title = re.sub(r"\s+", " ", html.unescape(title)).strip()
    return re.split(r"\s+\|\s+", title)[0].strip()


def _date_in_phrase(phrase: str, default_year: int) -> datetime | None:
    match = re.search(
        r"([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?"
        r"(?:\s*[–-]\s*(?:[A-Za-z]+\.?\s+)?\d{1,2}(?:st|nd|rd|th)?)?"
        r"(?:,?\s*(20\d{2}))?",
        phrase,
    )
    if not match:
        return None
    year = int(match.group(3)) if match.group(3) else default_year
    return parse_loose_date(f"{match.group(1)} {match.group(2)}, {year}", year)


def _dated_phrase(text: str, default_year: int) -> datetime | None:
    patterns = (
        r"When:\s*([^.]{0,80})",
        r"Upcoming session\s+([^.]{0,90})",
        r"will take place on\s+([^.]{0,80})",
        r"will be\s+([A-Za-z]+\.?\s+\d{1,2}[^.]{0,40})",
        r"Kick-off event:\s+([^.]{0,80})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        found = _date_in_phrase(match.group(1), default_year)
        if found:
            return found
    return None


def _challenge_event(name: str, location: str, url: str, page: str, source: str, now: datetime) -> dict | None:
    start = _dated_phrase(_plain(page), now.year)
    deadline = parse_application_deadline(page, start.year if start else now.year)
    if deadline is not None:
        deadline_kind = "application"
    elif start is not None:
        deadline = start
        deadline_kind = "event_start"
    else:
        return None
    return {
        "name": name,
        "location": location,
        "url": url,
        "starts_at": start.isoformat() if start else "",
        "ends_at": "",
        "deadline_at": deadline.isoformat(),
        "deadline_kind": deadline_kind,
        "when": start.astimezone(TORONTO).strftime("%Y-%m-%d") if start else "",
        "status": "Open" if deadline_kind == "application" else "Upcoming",
        "tier": "uw",
        "source": source,
    }


def _linked_challenges(index_url: str, location: str, source: str, now: datetime) -> list[dict]:
    response = _get(index_url, headers={"Accept": "text/html"})
    links = []
    seen = set()
    for href in re.findall(r'href="([^"]+)"', response.text):
        if not CHALLENGE_LINK.search(href):
            continue
        if href.startswith("http"):
            url = href
        elif href.startswith("/"):
            url = requests.compat.urljoin(index_url, href)
        else:
            continue
        url = url.split("#")[0].split("?")[0]
        if url in seen or url.rstrip("/") == index_url.rstrip("/"):
            continue
        seen.add(url)
        links.append(url)
    events = []
    for url in links[:12]:
        try:
            page = _get(url, headers={"Accept": "text/html"})
        except requests.RequestException:
            continue
        name = _page_title(page.text)
        if not name:
            continue
        event = _challenge_event(name, location, url, page.text, source, now)
        if event:
            events.append(event)
    return drop_past_deadlines(events, now)


def fetch_velocity_events(now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    try:
        return _linked_challenges(VELOCITY_INDEX, "University of Waterloo", "velocity", current)
    except requests.RequestException:
        return []


def fetch_ideas_clinic_events(now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    try:
        return _linked_challenges(
            IDEAS_INDEX,
            "Pearl Sullivan Engineering IDEAs Clinic",
            "ideas-clinic",
            current,
        )
    except requests.RequestException:
        return []


def fetch_hackathon_radar(now: datetime | None = None) -> list[dict]:
    """Hackathon Radar's public Waterloo page. Past rows are not kept."""
    current = now or datetime.now(timezone.utc)
    try:
        response = _get(RADAR_URL, headers={"Accept": "text/html"})
    except requests.RequestException:
        return []
    events = []
    seen = set()
    blocks = re.finditer(
        r'<h3 class="text-xs[^"]*"[^>]*>([^<]+)</h3>(.*?)(?=<h3 class="text-xs|$)',
        response.text,
        re.S,
    )
    for block in blocks:
        starts = parse_loose_date(html.unescape(block.group(1)), current.year)
        for card in re.finditer(r'href="(/database/hackathon/[^"]+)"([\s\S]*?)</a>', block.group(2)):
            body = card.group(2)
            if ">Past<" in body:
                continue
            name_match = re.search(r"<h3[^>]*>([^<]+)</h3>", body)
            if not name_match:
                continue
            name = html.unescape(name_match.group(1)).strip()
            key = name.lower()
            if not name or key in seen:
                continue
            seen.add(key)
            url = "https://www.hackathonradar.com" + card.group(1)
            tier = _tier(name, "Waterloo", url) or "major"
            deadline = starts
            events.append(
                {
                    "name": name,
                    "location": "Waterloo",
                    "url": url,
                    "starts_at": starts.isoformat() if starts else "",
                    "ends_at": "",
                    "deadline_at": deadline.isoformat() if deadline else "",
                    "deadline_kind": "event_start",
                    "when": starts.astimezone(TORONTO).strftime("%Y-%m-%d") if starts else "",
                    "status": "Upcoming",
                    "tier": tier,
                    "source": "hackathon-radar",
                }
            )
    return drop_past_deadlines(events, current)


def fetch_socratica_events(now: datetime | None = None) -> list[dict]:
    """Socratica's public calendar. The email newsletter has no public archive."""
    current = now or datetime.now(timezone.utc)
    try:
        response = _get(SOCRATICA_CALENDAR, headers={"Accept": "text/html"})
    except requests.RequestException:
        return []
    events = []
    seen = set()
    parts = re.split(r'<div class="font-medium">([^<]+)</div>', response.text)
    for date_text, chunk in zip(parts[1::2], parts[2::2]):
        starts = parse_loose_date(html.unescape(date_text), current.year)
        for card in re.finditer(r'href="(/[^"]+)"[\s\S]*?text-text-title">([^<]+)<', chunk):
            name = html.unescape(card.group(2)).strip()
            if not name or not SOCRATICA_KEEP.search(name):
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            href = card.group(1)
            url = href if href.startswith("http") else "https://wygo.world" + href
            deadline = starts
            events.append(
                {
                    "name": name,
                    "location": "Waterloo",
                    "url": url,
                    "starts_at": starts.isoformat() if starts else "",
                    "ends_at": "",
                    "deadline_at": deadline.isoformat() if deadline else "",
                    "deadline_kind": "event_start",
                    "when": starts.astimezone(TORONTO).strftime("%Y-%m-%d") if starts else "",
                    "status": "Upcoming",
                    "tier": "uw",
                    "source": "socratica",
                }
            )
    return drop_past_deadlines(events, current)


def fetch_communitech_events(now: datetime | None = None) -> list[dict]:
    """Communitech's events page. Their newsletter is members-only, and the site often blocks scripts."""
    current = now or datetime.now(timezone.utc)
    try:
        response = _get(
            COMMUNITECH_EVENTS,
            headers={
                "Accept": "text/html",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
            },
        )
    except requests.RequestException:
        return []
    if "Security Check" in response.text[:800]:
        return []
    events = []
    seen = set()
    for match in re.finditer(r"<h[23][^>]*>(.*?)</h[23]>", response.text, re.IGNORECASE | re.S):
        name = re.sub(r"<[^>]+>", " ", match.group(1))
        name = re.sub(r"\s+", " ", html.unescape(name)).strip()
        if not name or not HACKATHON_TITLE.search(name) or name.lower() in seen:
            continue
        window = response.text[max(0, match.start() - 500): match.end() + 300]
        starts = _date_in_phrase(_plain(window), current.year)
        if starts is None:
            continue
        seen.add(name.lower())
        href = re.search(r'href="([^"]+)"', window)
        url = COMMUNITECH_EVENTS
        if href:
            raw = html.unescape(href.group(1))
            url = raw if raw.startswith("http") else requests.compat.urljoin(COMMUNITECH_EVENTS, raw)
        events.append(
            {
                "name": name,
                "location": "Communitech, Kitchener",
                "url": url,
                "starts_at": starts.isoformat(),
                "ends_at": "",
                "deadline_at": starts.isoformat(),
                "deadline_kind": "event_start",
                "when": starts.astimezone(TORONTO).strftime("%Y-%m-%d"),
                "status": "Upcoming",
                "tier": "uw",
                "source": "communitech",
            }
        )
    return drop_past_deadlines(events, current)


def merge_hackathons(*groups: list[dict]) -> list[dict]:
    """Waterloo site rows win over a feed row with the same name."""
    by_name: dict[str, dict] = {}
    for group in groups:
        for item in group:
            key = item["name"].strip().lower()
            current = by_name.get(key)
            candidate_local = item.get("source") in LOCAL_SOURCES
            current_local = current is not None and current.get("source") in LOCAL_SOURCES
            if current is None or (candidate_local and not current_local):
                by_name[key] = item
    merged = drop_past_deadlines(list(by_name.values()))
    merged.sort(
        key=lambda item: (
            0 if item.get("tier") == "uw" else 1,
            item.get("deadline_at") or item.get("starts_at") or "9999",
            item["name"].lower(),
        )
    )
    return merged


def fetch_hackathons() -> list[dict]:
    groups = []
    for fetch in (
        fetch_devpost_events,
        fetch_mlh_events,
        fetch_uw_events,
        fetch_velocity_events,
        fetch_ideas_clinic_events,
        fetch_hackathon_radar,
        fetch_socratica_events,
        fetch_communitech_events,
    ):
        try:
            groups.append(fetch())
        except Exception:
            groups.append([])
    return merge_hackathons(*groups)
