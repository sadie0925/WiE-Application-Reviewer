"""Per-posting details (pay, work auth, term, job function) from Simplify.

The Simplify GitHub feeds only carry title / location / terms. Pay, citizenship
and sponsorship rules, and the job description live on each posting's page.
We fetch each posting once, keep only the small derived fields, and cache them
in details-cache.json so later runs only fetch new postings.
"""

from __future__ import annotations

import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from scrapers.filters import auth_labels_from_text, terms_from_description

ROOT = Path(__file__).parent
CACHE_PATH = ROOT / "details-cache.json"
DETAIL_URL = "https://api.simplify.jobs/v2/job-posting/:id/{id}/company"
HEADERS = {"User-Agent": "WiE-Coop-Listings/1.0 (github; educational)"}
TIMEOUT = 20
WORKERS = 8
RETRY_FAILED_AFTER = 6 * 60 * 60
CACHE_VERSION = 2

# Simplify enums (checked against posting text).
_SEASONS = {1: "Winter", 2: "Spring", 3: "Summer", 4: "Fall"}
_PERIODS = {1: "hr", 2: "wk", 3: "mo", 4: "yr"}
_REQUIREMENTS = {
    1: "US work auth",
    2: "US citizenship",
    3: "US clearance",
    4: "Canada work auth",
    5: "Canadian citizen/PR",
}
_CURRENCY_PREFIX = {"USD": "$", "CAD": "CA$"}

def _plain_text(raw: str | None) -> str:
    text = raw or ""
    for _ in range(2):  # some ATS double-escape (&amp;#xa;)
        text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Hourly conversion: 40 h/week, 52 weeks/year.
_HOURS = {"hr": 1.0, "wk": 40.0, "mo": 2080.0 / 12, "yr": 2080.0}

_AMOUNT = r"(?:CA)?\$\s?(\d[\d,]*(?:\.\d+)?)\s*([kK](?![a-z]))?"
_MONEY_RANGE_RE = re.compile(
    _AMOUNT
    + r"(?:\s*(?:USD|CAD))?(?:\s*(?:-|–|—|to)\s*" + _AMOUNT.replace("\\$", "\\$?") + r")?"
    + r"(?:\s*(?:USD|CAD))?(?P<after>[^$]{0,30})",
    re.IGNORECASE,
)
_PERIOD_WORDS = (
    (re.compile(r"^\W{0,3}(?:/\s*|per\s+|an?\s+|each\s+)?(?:hour|hr)\b|^\W{0,3}hourly", re.I), "hr"),
    (re.compile(r"^\W{0,3}(?:/\s*|per\s+|a\s+)?(?:week|wk)\b|^\W{0,3}weekly", re.I), "wk"),
    (re.compile(r"^\W{0,3}(?:/\s*|per\s+|a\s+)?(?:month|mo)\b|^\W{0,3}monthly", re.I), "mo"),
    (re.compile(r"^\W{0,3}(?:/\s*|per\s+|an?\s+)?(?:year|yr|annum)\b|^\W{0,3}annual(?:ly)?", re.I), "yr"),
)
# An unlabeled range ("Expected Compensation $20.00 - $50.00 + benefits") only counts near a pay word.
_PAY_CONTEXT = re.compile(
    r"\b(pay|compensation|salary|wage|rate|stipend|earn|base|range|hourly|annual)\b", re.IGNORECASE
)


def _amount(number: str, k: str | None) -> float:
    value = float(number.replace(",", ""))
    return value * 1000 if k else value


def _guess_period(low: float, high: float) -> str:
    if high <= 300:
        return "hr"
    if low >= 15000:
        return "yr"
    return ""


def _hourly_label(low: float, high: float, period: str, prefix: str) -> str:
    """Every pay shown as $/hr; yearly / monthly / weekly salaries are converted."""
    hours = _HOURS[period]
    low, high = low / hours, high / hours
    if low > high:
        low, high = high, low

    def fmt(value: float) -> str:
        if period != "hr":
            return f"{prefix}{round(value):,}"  # converted: whole dollars
        if abs(value - round(value)) < 0.005:
            return f"{prefix}{round(value):,}"
        return f"{prefix}{value:,.2f}"

    if abs(high - low) < 0.005 or fmt(low) == fmt(high):
        return f"{fmt(low)}/hr"
    return f"{fmt(low)}–{fmt(high)}/hr"


def _pay_from_text(text: str, prefix: str) -> str:
    for match in _MONEY_RANGE_RE.finditer(text):
        low = _amount(match.group(1), match.group(2))
        high = _amount(match.group(3), match.group(4)) if match.group(3) else low
        if low <= 0 or high <= 0:  # "$0.00 - $0.00" placeholders
            continue
        after = match.group("after") or ""
        period = next((p for regex, p in _PERIOD_WORDS if regex.search(after)), "")
        if not period:
            before = text[max(0, match.start() - 80): match.start()]
            if not _PAY_CONTEXT.search(before):
                continue
            period = _guess_period(low, high)
            if not period:
                continue
        # Sanity: skip things like "$5 billion" or a bonus line.
        hourly_high = high / _HOURS[period]
        if not (7 <= hourly_high <= 400):
            continue
        return _hourly_label(low, high, period, prefix)
    return ""


def _pay_label(posting: dict, text: str) -> str:
    low = posting.get("min_salary")
    high = posting.get("max_salary")
    currency = posting.get("currency_type") or "USD"
    prefix = _CURRENCY_PREFIX.get(currency, f"{currency} ")
    if (low or high) and float(low or high or 0) > 0:
        low = float(low or high)
        high = float(high or low)
        period = _PERIODS.get(posting.get("salary_period")) or _guess_period(low, high)
        if period:
            return _hourly_label(low, high, period, prefix)
    return _pay_from_text(text, prefix)


def extract(posting: dict) -> dict:
    """Keep only the small fields the boards need."""
    text = _plain_text(posting.get("description"))
    for key in ("requirements", "additional_requirements_text"):
        extra = posting.get(key)
        if isinstance(extra, list):
            text += " " + " ".join(str(item) for item in extra if isinstance(item, str))

    auth: list[str] = []
    for code in posting.get("additional_requirements") or []:
        label = _REQUIREMENTS.get(code)
        if label and label not in auth:
            auth.append(label)
    h1b = posting.get("sponsors_h1b")
    for label in auth_labels_from_text(text):
        if label not in auth:
            auth.append(label)

    seasons = []
    for item in posting.get("seasons") or []:
        if isinstance(item, (list, tuple)) and len(item) == 2 and item[0] in _SEASONS:
            seasons.append(f"{_SEASONS[item[0]]} {item[1]}")

    return {
        "v": CACHE_VERSION,
        "fetched": int(time.time()),
        "pay": _pay_label(posting, text),
        "auth": auth,
        "sponsors_h1b": h1b,
        "seasons": seasons,
        "desc_terms": terms_from_description(text),
        "functions": [f.get("title") for f in posting.get("functions") or [] if f.get("title")],
    }


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(cache: dict, keep_ids: set[str]) -> None:
    pruned = {key: cache[key] for key in sorted(cache) if key in keep_ids}
    CACHE_PATH.write_text(
        json.dumps(pruned, indent=0, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _needs_fetch(entry: dict | None, now: float) -> bool:
    if not entry:
        return True
    if entry.get("error"):
        return now - int(entry.get("fetched") or 0) > RETRY_FAILED_AFTER
    return entry.get("v") != CACHE_VERSION


def _fetch_one(session: requests.Session, listing_id: str) -> tuple[str, dict]:
    try:
        response = session.get(DETAIL_URL.format(id=listing_id), headers=HEADERS, timeout=TIMEOUT)
        if response.status_code == 404:
            return listing_id, {"v": CACHE_VERSION, "fetched": int(time.time()), "missing": True}
        response.raise_for_status()
        return listing_id, extract(response.json())
    except (requests.RequestException, ValueError) as exc:
        return listing_id, {"error": str(exc)[:200], "fetched": int(time.time())}


def fetch_missing(listings: list[dict], cache: dict, budget: int = 600) -> int:
    """Fetch details for listings not yet cached (newest first). Returns fetch count."""
    now = time.time()
    todo = []
    for listing in sorted(listings, key=lambda item: -int(item.get("date_posted") or 0)):
        listing_id = listing.get("id")
        if not listing_id or str(listing.get("source")) != "simplify":
            continue
        if _needs_fetch(cache.get(listing_id), now):
            todo.append(listing_id)
    todo = todo[:budget]
    if not todo:
        return 0
    with requests.Session() as session, ThreadPoolExecutor(WORKERS) as pool:
        for listing_id, entry in pool.map(lambda i: _fetch_one(session, i), todo):
            cache[listing_id] = entry
    return len(todo)


OVERRIDES_PATH = ROOT / "pay-overrides.json"


def load_pay_overrides() -> dict[str, str]:
    """Manual pay for postings whose pay Simplify's copy leaves out.

    Keys are apply URLs; values are the pay text from the posting,
    e.g. "$20.00 - $50.00". Converted to $/hr like everything else.
    """
    try:
        data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str) and not k.startswith("_")}


def apply_details(listings: list[dict], cache: dict) -> None:
    """Copy cached detail fields onto listings (no network)."""
    overrides = load_pay_overrides()
    for listing in listings:
        override = overrides.get(listing.get("url") or "")
        if override:
            listing["detail_pay"] = _pay_from_text("pay " + override, "$")
        entry = cache.get(listing.get("id") or "")
        if not entry or entry.get("error") or entry.get("missing"):
            continue
        if not override:
            listing["detail_pay"] = entry.get("pay") or ""
        listing["detail_auth"] = list(entry.get("auth") or [])
        listing["detail_h1b"] = entry.get("sponsors_h1b")
        listing["detail_seasons"] = list(entry.get("seasons") or [])
        listing["detail_desc_terms"] = entry.get("desc_terms") or ""
        listing["functions"] = list(entry.get("functions") or [])
