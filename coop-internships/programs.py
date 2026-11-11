"""Early undergrad programs at high-paying firms.

Ordinary internships stay on the job boards. This list is fellows, insight,
and early-year programs for undergraduates, read from each company's public
careers page. A row is removed as soon as its application deadline passes.
Instagram, TikTok, and LinkedIn are not checked.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import requests

from hackathons import parse_loose_date

USER_AGENT = "WiE-Coop-Listings/1.0 (github; educational)"
REQUEST_TIMEOUT = 30

# Public Greenhouse boards for firms that usually sit in the top pay band.
# The sync only keeps student programs, not every software job.
GREENHOUSE_BOARDS = (
    "anthropic",
    "stripe",
    "databricks",
    "roblox",
    "jumptrading",
    "imc",
    "optiver",
    "point72",
    "xai",
    "coinbase",
    "block",
    "airbnb",
    "akunacapital",
    "virtu",
    "ramp",
    "scaleai",
)

# Official program pages that are not on Greenhouse. A page is listed only
# when it is actually open and has a future date.
WATCH_PAGES = (
    ("Google", "STEP", "https://www.google.com/about/careers/applications/buildyourfuture/programs/step"),
    ("Microsoft", "Explore", "https://careers.microsoft.com/v2/global/en/exploremicrosoft"),
    ("NVIDIA", "Ignite", "https://www.nvidia.com/en-us/about-nvidia/careers/university-recruiting/"),
)

JANE_STREET_INDEX = "https://www.janestreet.com/join-jane-street/programs-and-events/"

STUDENT_TITLE = re.compile(
    r"\b("
    r"fellows program|insight program(?:me)?|early insight|"
    r"step internship|ignite|freshman|first[- ]year|sophomore|"
    r"underclass|immersion program|explore internship"
    r")\b",
    re.IGNORECASE,
)
PHD_REQUIRED = re.compile(
    r"\b(ph\.?d\.?\s+students only|specifically at ph\.?d|hold a ph\.?d|completed (?:their|a) ph\.?d)\b",
    re.IGNORECASE,
)
PHD_NOT_REQUIRED = re.compile(
    r"\b(do not need a ph\.?d|don't need a ph\.?d|no ph\.?d(?: required)?|ph\.?d not required)\b",
    re.IGNORECASE,
)
CLOSED = re.compile(
    r"no longer accepting|applications will re-open|will re-open at a later date|"
    r"not currently accepting|applications are closed|position has been filled",
    re.IGNORECASE,
)
SWE_TEXT = re.compile(
    r"\b(software|computer science|technology|stem|python|machine learning|ai safety)\b",
    re.IGNORECASE,
)
HIGH_SCHOOL_ONLY = re.compile(r"\bhigh school\b", re.IGNORECASE)
UNIVERSITY = re.compile(r"\b(university|undergraduate|college)\b", re.IGNORECASE)


def _get(url: str, **kwargs) -> requests.Response:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    headers.update(kwargs.pop("headers", {}))
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
    response.raise_for_status()
    return response


def _plain(page: str) -> str:
    text = html.unescape(page)
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def _application_deadline(text: str, now: datetime) -> datetime | None:
    patterns = (
        r"(?:apply(?: here)? by|deadline to apply|applications? (?:are )?open until)"
        r"\s*:?\s*(?:[A-Za-z]+,?\s+)?([A-Za-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)",
        r"\buntil\s+([A-Za-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        found = parse_loose_date(match.group(1), now.year)
        if found:
            return found
    return None


def _program_start(text: str, now: datetime) -> datetime | None:
    window = re.search(
        r"(?:available|when:|runs from|start(?:ing)? in|cohort)\s+.{0,140}",
        text,
        re.IGNORECASE,
    )
    if not window:
        return None
    chunk = window.group(0)
    year_match = re.search(r"20\d{2}", chunk)
    year = int(year_match.group(0)) if year_match else now.year
    for month, day in re.findall(r"([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?!\d)", chunk):
        found = parse_loose_date(f"{month} {day}, {year}", year)
        if found:
            return found
    month_only = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
        chunk,
        re.IGNORECASE,
    )
    if month_only:
        return parse_loose_date(f"{month_only.group(1)} 1, {year}", year)
    return None


def _term_label(text: str) -> str:
    found = []
    seen = set()
    for match in re.finditer(
        r"\b(winter|spring|fall|autumn|summer)\b(?:\s+(20\d{2}))?",
        text,
        re.IGNORECASE,
    ):
        word = match.group(1).lower()
        if word == "summer" and re.match(r"\s+games\b", text[match.end(): match.end() + 12], re.IGNORECASE):
            continue
        label = {"winter": "Winter", "spring": "Spring", "fall": "Fall", "autumn": "Fall", "summer": "Spring"}[word]
        year = match.group(2) or ""
        key = (label, year)
        if key in seen:
            continue
        seen.add(key)
        found.append((year or "0000", {"Winter": 0, "Spring": 1, "Fall": 2}[label], f"{label} {year}".strip()))
    if not found:
        for match in re.finditer(r"\b(January|February|March)\b", text, re.IGNORECASE):
            sentence = text[max(0, match.start() - 30): match.end() + 40]
            year_match = re.search(r"20\d{2}", sentence)
            year = year_match.group(0) if year_match else ""
            key = ("Winter", year)
            if key in seen:
                continue
            seen.add(key)
            found.append((year or "0000", 0, f"Winter {year}".strip()))
            break
    found.sort()
    return ", ".join(item[2] for item in found)


def _audience(text: str) -> str:
    first = re.search(r"\b(first[- ]years?|freshm[ae]n)\b", text, re.IGNORECASE)
    second = re.search(r"\b(second[- ]years?|sophomores?)\b", text, re.IGNORECASE)
    if first and second:
        return "First- and second-year"
    if first:
        return "First-year"
    if second:
        return "Second-year"
    if re.search(r"\babout to start (?:their )?first year\b", text, re.IGNORECASE):
        return "Incoming first-year"
    if PHD_NOT_REQUIRED.search(text):
        return "No PhD required"
    if re.search(r"\bundergraduates?\b", text, re.IGNORECASE):
        return "Any undergrad"
    return ""


def _pay(text: str) -> str:
    stipend = re.search(
        r"weekly stipend of\s+([^.]{0,80})",
        text,
        re.IGNORECASE,
    )
    if stipend:
        amount = re.split(r"\s+\+|</", stipend.group(1))[0]
        return "Weekly " + re.sub(r"\s+", " ", amount).strip(" +")
    money = re.search(
        r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*(?:/|per)\s*(?:hour|hr|week|month))",
        text,
        re.IGNORECASE,
    )
    if money:
        return re.sub(r"\s+", " ", money.group(0))
    if re.search(r"cover travel[\s\S]{0,60}meals[\s\S]{0,40}housing", text, re.IGNORECASE):
        return "Travel, meals, housing"
    return ""


def _place_ok(location: str) -> bool:
    low = location.lower()
    if not low:
        return False
    north_america = any(
        token in low
        for token in ("united states", "u.s.", "usa", "canada", "ontario", "remote", "new york")
    )
    uk_only = any(token in low for token in ("united kingdom", "london", " uk")) and not north_america
    return north_america and not uk_only


def _skip_text(text: str) -> bool:
    if CLOSED.search(text):
        return True
    if PHD_REQUIRED.search(text) and not PHD_NOT_REQUIRED.search(text):
        return True
    if re.search(r"\bmaster'?s (?:students? )?only\b", text, re.IGNORECASE):
        return True
    if HIGH_SCHOOL_ONLY.search(text) and not UNIVERSITY.search(text):
        return True
    return False


def _row(
    company: str,
    name: str,
    url: str,
    location: str,
    text: str,
    now: datetime,
    *,
    require_swe: bool,
) -> dict | None:
    if _skip_text(text):
        return None
    if require_swe and not SWE_TEXT.search(f"{name} {text}"):
        return None
    if not _place_ok(location):
        return None
    app_deadline = _application_deadline(text, now)
    starts = _program_start(text, now)
    if app_deadline is not None and app_deadline < now:
        return None
    if starts is not None and starts < now:
        return None
    if app_deadline is None and starts is None:
        return None
    return {
        "company": company,
        "name": name,
        "url": url,
        "location": location,
        "term": _term_label(text),
        "pay": _pay(text),
        "audience": _audience(text),
        "starts_at": starts.isoformat() if starts else "",
        "ends_at": "",
        "deadline_at": app_deadline.isoformat() if app_deadline else "",
        "deadline_kind": "application" if app_deadline else "",
        "source": "official",
    }


def fetch_greenhouse_programs(now: datetime) -> list[dict]:
    events = []
    for board in GREENHOUSE_BOARDS:
        try:
            listing = _get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs")
        except requests.RequestException:
            continue
        for job in listing.json().get("jobs") or []:
            title = job.get("title") or ""
            if not STUDENT_TITLE.search(title):
                continue
            if re.search(r"\b(economics|policy)\b", title, re.IGNORECASE) and not re.search(
                r"\b(software|engineer|safety)\b", title, re.IGNORECASE
            ):
                continue
            job_id = job.get("id")
            try:
                detail = _get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}")
            except requests.RequestException:
                continue
            payload = detail.json()
            content = _plain(payload.get("content") or "")
            location = ((payload.get("location") or {}).get("name")) or ""
            company = payload.get("company_name") or board
            row = _row(
                company,
                title.strip(),
                payload.get("absolute_url") or "",
                location,
                f"{title} {content}",
                now,
                require_swe=True,
            )
            if row:
                events.append(row)
    return events


def _jane_street_cards(page: str) -> list[tuple[str, str, str, str]]:
    cards = []
    for match in re.finditer(
        r'href="(/join-jane-street/programs-and-events/[^"]+)"[^>]*>[\s\S]*?'
        r'<h3 class="program-title">\s*(.*?)\s*</h3>\s*'
        r'<h6 class="accepting-applications-label[^"]*">\s*(.*?)\s*</h6>[\s\S]*?'
        r'<p class="description">(.*?)</p>',
        page,
    ):
        title = re.sub(r"\s+", " ", html.unescape(match.group(2))).strip()
        status = re.sub(r"\s+", " ", html.unescape(match.group(3))).strip()
        description = re.sub(r"\s+", " ", html.unescape(match.group(4))).strip()
        cards.append((match.group(1), title, status, description))
    return cards


def _jane_street_text(title: str, description: str, detail_text: str, extra: str) -> str:
    """Keep the program description and the date lines, not the application form."""
    cut = detail_text.find("Accept All")
    rest = detail_text[cut + len("Accept All"):] if cut >= 0 else detail_text
    anchor = description[:40].strip()
    start = rest.find(anchor) if anchor else -1
    body = rest[start:start + 1600] if start >= 0 else description
    bits = [title, description, body]
    for pattern in (
        r".{0,30}available\s+.{0,140}",
        r".{0,40}deadline to apply.{0,90}",
        r".{0,40}apply here by.{0,40}",
    ):
        match = re.search(pattern, extra, re.IGNORECASE)
        if match:
            bits.append(match.group(0))
    travel = re.search(r"cover travel.{0,100}", detail_text, re.IGNORECASE)
    if travel:
        bits.append(travel.group(0))
    return " ".join(bits)


def fetch_jane_street_programs(now: datetime) -> list[dict]:
    try:
        index = _get(JANE_STREET_INDEX, headers={"Accept": "text/html"})
    except requests.RequestException:
        return []
    events = []
    for href, title, status, description in _jane_street_cards(index.text):
        if "ACCEPTING" not in status.upper():
            continue
        url = "https://www.janestreet.com" + href
        try:
            detail = _get(url, headers={"Accept": "text/html"})
            detail_text = _plain(detail.text)
        except requests.RequestException:
            detail_text = description
        slug = href.strip("/").split("/")[-1]
        extra = ""
        apply_url = f"https://www.janestreet.com/apply-{slug}-nyc/"
        try:
            form = _get(apply_url, headers={"Accept": "text/html"})
            if form.url.rstrip("/").endswith(f"apply-{slug}-nyc"):
                extra = _plain(form.text)
                url = form.url
        except requests.RequestException:
            pass
        if slug == "insight":
            try:
                email = _get("https://www.janestreet.com/insight-nyc-email", headers={"Accept": "text/html"})
                extra += " " + _plain(email.text)
            except requests.RequestException:
                pass
        text = _jane_street_text(title, description, detail_text, extra)
        row = _row(
            "Jane Street",
            title,
            url,
            "New York",
            text,
            now,
            require_swe=True,
        )
        if row:
            events.append(row)
    return events


def fetch_watch_pages(now: datetime) -> list[dict]:
    events = []
    for company, name, url in WATCH_PAGES:
        try:
            response = _get(url, headers={"Accept": "text/html"})
        except requests.RequestException:
            continue
        if response.url.rstrip("/") != url.rstrip("/") and name.lower() not in response.url.lower():
            continue
        text = _plain(response.text)
        if not re.search(r"accepting applications|applications are (?:now )?open|apply here by", text, re.IGNORECASE):
            continue
        row = _row(company, name, response.url, "United States", f"{name} {text}", now, require_swe=True)
        if row:
            events.append(row)
    return events


def fetch_programs(now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    groups = []
    for fetch in (fetch_greenhouse_programs, fetch_jane_street_programs, fetch_watch_pages):
        try:
            groups.append(fetch(current))
        except Exception:
            groups.append([])
    from hackathons import drop_past_deadlines

    by_url: dict[str, dict] = {}
    for group in groups:
        for item in group:
            by_url[item["url"]] = item
    merged = drop_past_deadlines(list(by_url.values()), current)
    merged.sort(
        key=lambda item: (
            item.get("deadline_at") or item.get("starts_at") or "9999",
            item.get("company") or "",
            item.get("name") or "",
        )
    )
    return merged
