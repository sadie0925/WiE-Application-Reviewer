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
from pathlib import Path
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
LOCAL_SOURCES = {"uwaterloo", "velocity", "ideas-clinic", "socratica", "communitech", "club-linktree", "club-luma", "luma"}

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
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    response = requests.get(url, headers=headers, timeout=timeout, **kwargs)
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


def application_deadline_of(event: dict) -> datetime | None:
    """Only the application/registration close date. Never the event start."""
    if event.get("deadline_kind") != "application":
        return None
    return _parse_iso(event.get("deadline_at"))


def deadline_of(event: dict) -> datetime | None:
    """Back-compat: application deadline when known."""
    return application_deadline_of(event)


def _start_from_when(when: str, default_year: int) -> datetime | None:
    """Parse the first date in ranges like 'Nov 06 - 13, 2026'."""
    if not when:
        return None
    year_match = re.search(r"(20\d{2})", when)
    year = int(year_match.group(1)) if year_match else default_year
    return parse_loose_date(when, year)


def drop_past_deadlines(events: list[dict], now: datetime | None = None) -> list[dict]:
    """Clear EVERY hackathon/program row that is no longer apply-able.

    Applies to all sources (MLH, Devpost, Velocity, Radar, etc.), not one event:
    - application deadline passed → drop
    - event already started (starts_at or parsed `when`) → drop
    - event already ended → drop

    The Deadline column still shows application close only.
    """
    current = now or datetime.now(timezone.utc)
    kept = []
    for event in events:
        app_deadline = application_deadline_of(event)
        if app_deadline is not None and app_deadline < current:
            continue
        ends = _parse_iso(event.get("ends_at"))
        if ends is not None and ends < current:
            continue
        starts = _parse_iso(event.get("starts_at"))
        if starts is None:
            starts = _start_from_when(event.get("when") or "", current.year)
        if starts is not None and starts < current:
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
            if starts is not None and starts < current:
                continue
            if ends is not None and ends < current:
                continue
            key = name.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            site = url or "https://mlh.io" + (item.get("url") or "")
            # MLH does not publish application close dates. Deadline stays blank;
            # the row is removed once the event starts.
            events.append(
                {
                    "name": name.strip(),
                    "location": location or "—",
                    "url": site,
                    "starts_at": item.get("startsAt") or "",
                    "ends_at": item.get("endsAt") or "",
                    "deadline_at": "",
                    "deadline_kind": "",
                    "when": item.get("dateRange") or "",
                    "status": "Upcoming",
                    "tier": tier,
                    "source": "mlh",
                }
            )
    return drop_past_deadlines(events, current)


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
            starts = _start_from_when(period, current.year)
            # Keep rows so merge can carry a real start date onto Radar/MLH clones.
            # drop_past_deadlines removes anything already started or past deadline.
            if deadline is None and starts is None:
                continue
            events.append(
                {
                    "name": name.strip(),
                    "location": location or "—",
                    "url": url,
                    "starts_at": starts.isoformat() if starts else "",
                    "ends_at": "",
                    "deadline_at": deadline.isoformat() if deadline else "",
                    "deadline_kind": "application" if deadline else "",
                    "when": period,
                    "status": "Open" if deadline else "Upcoming",
                    "tier": tier,
                    "source": "devpost",
                }
            )
    return events


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
            if starts is not None and starts < current:
                continue
            deadline = None
            try:
                page = _get(link, headers={"Accept": "text/html"})
                default_year = starts.year if starts else current.year
                deadline = parse_application_deadline(page.text, default_year)
            except requests.RequestException:
                pass
            events.append(
                {
                    "name": title,
                    "location": "University of Waterloo",
                    "url": link,
                    "starts_at": starts.isoformat() if starts else "",
                    "ends_at": "",
                    "deadline_at": deadline.isoformat() if deadline else "",
                    "deadline_kind": "application" if deadline else "",
                    "when": starts.astimezone(TORONTO).strftime("%Y-%m-%d") if starts else "",
                    "status": "Open" if deadline else "Upcoming",
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
    if start is None:
        return None
    if start < now:
        return None
    deadline = parse_application_deadline(page, start.year if start else now.year)
    return {
        "name": name,
        "location": location,
        "url": url,
        "starts_at": start.isoformat(),
        "ends_at": "",
        "deadline_at": deadline.isoformat() if deadline else "",
        "deadline_kind": "application" if deadline else "",
        "when": start.astimezone(TORONTO).strftime("%Y-%m-%d"),
        "status": "Open" if deadline else "Upcoming",
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
            if starts is not None and starts < current:
                continue
            url = "https://www.hackathonradar.com" + card.group(1)
            tier = _tier(name, "Waterloo", url) or "major"
            events.append(
                {
                    "name": name,
                    "location": "Waterloo",
                    "url": url,
                    "starts_at": starts.isoformat() if starts else "",
                    "ends_at": "",
                    "deadline_at": "",
                    "deadline_kind": "",
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
            if starts is not None and starts < current:
                continue
            href = card.group(1)
            url = href if href.startswith("http") else "https://wygo.world" + href
            events.append(
                {
                    "name": name,
                    "location": "Waterloo",
                    "url": url,
                    "starts_at": starts.isoformat() if starts else "",
                    "ends_at": "",
                    "deadline_at": "",
                    "deadline_kind": "",
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
        if starts < current:
            continue
        events.append(
            {
                "name": name,
                "location": "Communitech, Kitchener",
                "url": url,
                "starts_at": starts.isoformat(),
                "ends_at": "",
                "deadline_at": "",
                "deadline_kind": "",
                "when": starts.astimezone(TORONTO).strftime("%Y-%m-%d"),
                "status": "Upcoming",
                "tier": "uw",
                "source": "communitech",
            }
        )
    return drop_past_deadlines(events, current)


# ---------------------------------------------------------------------------
# Luma (most UW clubs post events there) and club Linktrees
# ---------------------------------------------------------------------------

LUMA_NEARBY = "https://api.lu.ma/discover/get-paginated-events"
WATERLOO_LAT_LNG = (43.4723, -80.5449)
CLUBS_PATH = Path(__file__).parent / "uw-clubs.json"
CLUB_CACHE_PATH = Path(__file__).parent / "club-events-cache.json"
CLUB_RECRAWL_SECONDS = 6 * 60 * 60
LINKTREE_DELAY_SECONDS = 3

# Hackathon-type events (not weekly "hack nights" or talks).
EVENT_NAME = re.compile(
    r"\b(hackathon|hacks|hack(?!\s*night|\s*club)|designathon|datathon|buildathon|makeathon|"
    r"ideathon|codeathon|game\s*jam|innovation\s+challenge|case\s+competition|"
    r"pitch\s+competition|design\s+challenge|data\s+challenge|ai\s+challenge|cxc)\b",
    re.IGNORECASE,
)
NOT_EVENT = re.compile(r"\b(hack\s*nights?|workshop\s+series|info\s+session|recap|photos?)\b", re.IGNORECASE)
# UW campus or a UW club on Luma.
UW_LUMA = re.compile(
    r"\b(uw|uwaterloo|university\s+of\s+waterloo|waterloo\s+(?:engineering|cs|math)|"
    r"engsoc|mathsoc|wics|wie)\b|@\s*waterloo|200\s+university\s+ave(?:nue)?\s+w",
    re.IGNORECASE,
)
FORM_HOSTS = re.compile(r"(docs\.google\.com/forms|forms\.gle|typeform\.com|tally\.so|airtable\.com|jotform)", re.I)
MONTH_YEAR = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(20\d{2})\b",
    re.IGNORECASE,
)
FULL_DATE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:\s*[-–]\s*(?:[a-z]+\.?\s+)?\d{1,2}(?:st|nd|rd|th)?)?,?\s+(20\d{2})\b",
    re.IGNORECASE,
)


def _html_get(url: str) -> requests.Response:
    return _get(url, headers={"Accept": "text/html"})


def _next_data(page: str) -> dict:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(1)).get("props", {}).get("pageProps", {})
    except json.JSONDecodeError:
        return {}


def _luma_row(entry: dict, tier: str | None, source: str) -> dict | None:
    """One Luma event (from the nearby feed, a calendar, or an event page)."""
    event = entry.get("event") or entry
    name = _clean_link_title(event.get("name") or "")
    if not name or not EVENT_NAME.search(name) or NOT_EVENT.search(name):
        return None
    if (entry.get("registration_availability") or "open") not in {"open", "waitlist"}:
        return None
    geo = event.get("geo_address_info") or {}
    country = (geo.get("country_code") or "").upper()
    if country and country not in {"CA", "US"}:
        return None
    calendar = entry.get("calendar") or {}
    hosts = " ".join(h.get("name") or "" for h in entry.get("hosts") or [])
    if tier is None:
        blob = " ".join([name, calendar.get("name") or "", hosts, geo.get("full_address") or "", geo.get("address") or ""])
        tier = "uw" if UW_LUMA.search(blob) else (_tier(name, geo.get("city_state") or "", "") or "major")
    starts = _parse_iso(event.get("start_at"))
    where = geo.get("address") or geo.get("city_state") or ("Online" if event.get("location_type") == "online" else "—")
    if geo.get("city_state") and geo.get("address") and geo["city_state"] not in where:
        where = f"{where}, {geo['city_state']}"
    return {
        "name": name,
        "location": where,
        "url": f"https://luma.com/{event.get('url')}" if event.get("url") else "",
        "starts_at": starts.isoformat() if starts else "",
        "ends_at": event.get("end_at") or "",
        "deadline_at": "",
        "deadline_kind": "",
        "when": starts.astimezone(TORONTO).strftime("%Y-%m-%d") if starts else "",
        "status": "Open",
        "tier": tier,
        "source": source,
        "organizer": calendar.get("name") or "",
    }


def fetch_luma_nearby(now: datetime | None = None) -> list[dict]:
    """Every public Luma event around Waterloo (UW clubs, Laurier, Communitech, ...)."""
    current = now or datetime.now(timezone.utc)
    events: list[dict] = []
    cursor = None
    for _page in range(10):
        params = {
            "latitude": WATERLOO_LAT_LNG[0],
            "longitude": WATERLOO_LAT_LNG[1],
            "pagination_limit": 50,
        }
        if cursor:
            params["pagination_cursor"] = cursor
        try:
            data = _get(LUMA_NEARBY, params=params).json()
        except (requests.RequestException, ValueError):
            break
        for entry in data.get("entries") or []:
            row = _luma_row(entry, None, "luma")
            if row:
                events.append(row)
        cursor = data.get("next_cursor") if data.get("has_more") else None
        if not cursor:
            break
    return drop_past_deadlines(events, current)


def _luma_page(url: str, tier: str | None, source: str) -> list[dict]:
    """A Luma event page or calendar page."""
    data = (_next_data(_html_get(url).text).get("initialData") or {})
    kind, body = data.get("kind"), data.get("data") or {}
    if kind == "event":
        row = _luma_row(body, tier, source)
        return [row] if row else []
    rows = []
    for key in ("featured_items", "items", "upcoming"):
        items = body.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and "event" in item:
                    row = _luma_row(item, tier, source)
                    if row:
                        rows.append(row)
    return rows


def _site_event(name: str, url: str, page: str, now: datetime) -> dict | None:
    """A club's own hackathon site (e.g. cxc.uwdatascience.ca). Date may be month-only."""
    text = _plain(page)
    starts = None
    when = ""
    full = None
    for match in FULL_DATE.finditer(text):
        found = parse_loose_date(f"{match.group(1)} {match.group(2)}, {match.group(3)}", int(match.group(3)))
        if found and found >= now:
            full = found
            break
    if full:
        starts = full.replace(hour=0, minute=0, second=0)
        when = starts.strftime("%Y-%m-%d")
    else:
        for match in MONTH_YEAR.finditer(text):
            month = MONTHS.get(match.group(1).lower()[:3])
            year = int(match.group(2))
            first = datetime(year, month, 1, tzinfo=TORONTO)
            # Month-only ("FEBRUARY 2027"): kept until that month begins.
            if month and first >= now:
                starts = first
                when = first.strftime("%B %Y")
                break
    if starts is None:
        return None
    deadline = parse_application_deadline(page, starts.year)
    return {
        "name": name,
        "location": "University of Waterloo",
        "url": url,
        "starts_at": starts.isoformat(),
        "ends_at": "",
        "deadline_at": deadline.isoformat() if deadline else "",
        "deadline_kind": "application" if deadline else "",
        "when": when,
        "month_only": full is None,
        "status": "Open" if deadline else "Upcoming",
        "tier": "uw",
        "source": "club-linktree",
    }


def _form_is_open(url: str) -> bool:
    try:
        page = _html_get(url).text.lower()
    except requests.RequestException:
        return False
    return not any(
        phrase in page
        for phrase in ("no longer accepting responses", "closedform", "form is closed", "not accepting submissions")
    )


def _clean_link_title(title: str) -> str:
    title = re.sub(r"^[\W_]+|[\W_]+$", "", title.strip())
    return re.sub(r"\s+", " ", title)


def _club_links(club: dict, now: datetime) -> list[dict]:
    """Hackathons / challenges linked from one club's Linktree or Luma calendar."""
    rows: list[dict] = []
    if club.get("luma"):
        try:
            rows.extend(_luma_page(f"https://luma.com/{club['luma']}", "uw", "club-luma"))
        except requests.RequestException:
            pass
    handle = club.get("linktree")
    if not handle:
        return rows
    props = _next_data(_html_get(f"https://linktr.ee/{handle}").text)
    for link in props.get("links") or []:
        url = (link.get("url") or "").strip()
        title = _clean_link_title(link.get("title") or "")
        if not url or not title:
            continue
        is_event = EVENT_NAME.search(title) and not NOT_EVENT.search(title)
        try:
            if "luma.com/" in url or "lu.ma/" in url:
                rows.extend(_luma_page(url, "uw", "club-linktree"))
            elif not is_event:
                continue
            elif FORM_HOSTS.search(url):
                # An open application / sign-up form for a hackathon.
                if _form_is_open(url):
                    rows.append({
                        "name": title,
                        "location": "University of Waterloo",
                        "url": url,
                        "starts_at": "",
                        "ends_at": "",
                        "deadline_at": "",
                        "deadline_kind": "",
                        "when": "",
                        "status": "Open",
                        "tier": "uw",
                        "source": "club-linktree",
                    })
            else:
                row = _site_event(title, url, _html_get(url).text, now)
                if row:
                    rows.append(row)
        except requests.RequestException:
            continue
    for row in rows:
        row.setdefault("organizer", club.get("name") or "")
        if not row.get("organizer"):
            row["organizer"] = club.get("name") or ""
    return rows


def _load_clubs() -> list[dict]:
    try:
        data = json.loads(CLUBS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [club for club in data.get("clubs") or [] if isinstance(club, dict)]


def fetch_club_events(now: datetime | None = None) -> list[dict]:
    """Waterloo club Linktrees and Luma calendars from uw-clubs.json.

    Linktree rate-limits scripts, so each club is checked at most every 6 hours,
    one request every few seconds, and the last good result is kept if a check fails.
    """
    import time as _time

    current = now or datetime.now(timezone.utc)
    try:
        cache = json.loads(CLUB_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cache = {}
    events: list[dict] = []
    changed = False
    for club in _load_clubs():
        key = club.get("linktree") or club.get("luma") or club.get("name") or ""
        saved = cache.get(key) or {}
        fresh = _time.time() - float(saved.get("checked") or 0) < CLUB_RECRAWL_SECONDS
        if not fresh:
            try:
                rows = _club_links(club, current)
                saved = {"checked": int(_time.time()), "events": rows}
                cache[key] = saved
                changed = True
            except (requests.RequestException, ValueError):
                pass  # keep the last good result
            if club.get("linktree"):
                _time.sleep(LINKTREE_DELAY_SECONDS)
        events.extend(saved.get("events") or [])
    keep = {club.get("linktree") or club.get("luma") or club.get("name") or "" for club in _load_clubs()}
    if changed or set(cache) - keep:
        cache = {k: v for k, v in cache.items() if k in keep}
        CLUB_CACHE_PATH.write_text(json.dumps(cache, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return drop_past_deadlines(events, current)


def _event_start(event: dict) -> datetime | None:
    return _parse_iso(event.get("starts_at")) or _start_from_when(
        event.get("when") or "", datetime.now(timezone.utc).year
    )


def _merge_event(current: dict, incoming: dict) -> dict:
    """Prefer Waterloo sources, keep application deadlines, use the earliest start."""
    candidate_local = incoming.get("source") in LOCAL_SOURCES
    current_local = current.get("source") in LOCAL_SOURCES
    if candidate_local and not current_local:
        base, other = dict(incoming), current
    else:
        base, other = dict(current), incoming

    starts = [item for item in (_event_start(base), _event_start(other)) if item is not None]
    if starts:
        earliest = min(starts)
        base["starts_at"] = earliest.isoformat()
        if not base.get("when"):
            base["when"] = earliest.astimezone(TORONTO).strftime("%Y-%m-%d")

    if other.get("deadline_kind") == "application" and other.get("deadline_at"):
        if base.get("deadline_kind") != "application" or not base.get("deadline_at"):
            base["deadline_at"] = other["deadline_at"]
            base["deadline_kind"] = "application"
        else:
            a = _parse_iso(base.get("deadline_at"))
            b = _parse_iso(other.get("deadline_at"))
            if a and b and b < a:
                base["deadline_at"] = other["deadline_at"]

    if base.get("tier") != "uw" and other.get("tier") == "uw":
        base["tier"] = "uw"
    return base


def merge_hackathons(*groups: list[dict]) -> list[dict]:
    """Waterloo site rows win; earliest start date wins so started events clear."""
    by_name: dict[str, dict] = {}
    for group in groups:
        for item in group:
            key = item["name"].strip().lower()
            current = by_name.get(key)
            by_name[key] = item if current is None else _merge_event(current, item)
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
        fetch_luma_nearby,
        fetch_club_events,
    ):
        try:
            groups.append(fetch())
        except Exception:
            groups.append([])
    return merge_hackathons(*groups)
