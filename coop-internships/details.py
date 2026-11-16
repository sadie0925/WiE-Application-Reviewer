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

from scrapers.filters import auth_labels_from_text, terms_from_description, _WAGE_RE

ROOT = Path(__file__).parent
CACHE_PATH = ROOT / "details-cache.json"
DETAIL_URL = "https://api.simplify.jobs/v2/job-posting/:id/{id}/company"
HEADERS = {"User-Agent": "WiE-Coop-Listings/1.0 (github; educational)"}
TIMEOUT = 20
WORKERS = 8
RETRY_FAILED_AFTER = 6 * 60 * 60
CACHE_VERSION = 1

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

_YEARLY_RE = re.compile(
    r"\$\s*(\d{2,3}(?:,\d{3})+|\d{2,3}\s*[kK])(?:\.\d{2})?"
    r"(?:\s*(?:-|–|—|to)\s*\$?\s*(\d{2,3}(?:,\d{3})+|\d{2,3}\s*[kK])(?:\.\d{2})?)?"
    r"(?:\s*(?:USD|CAD))?\s*(?:/\s*|per\s+|a\s+|an\s+)?(?:year|yr|annual(?:ly)?|annum)",
    re.IGNORECASE,
)


def _plain_text(raw: str | None) -> str:
    text = raw or ""
    for _ in range(2):  # some ATS double-escape (&amp;#xa;)
        text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _money(value: float, period: str, prefix: str) -> str:
    if period == "yr" and value >= 1000:
        return f"{prefix}{round(value / 1000)}k"
    if float(value).is_integer():
        return f"{prefix}{int(value):,}"
    return f"{prefix}{value:,.2f}"


def _pay_label(posting: dict, text: str) -> str:
    low = posting.get("min_salary")
    high = posting.get("max_salary")
    currency = posting.get("currency_type") or "USD"
    prefix = _CURRENCY_PREFIX.get(currency, f"{currency} ")
    if low or high:
        low = float(low or high)
        high = float(high or low)
        period = _PERIODS.get(posting.get("salary_period"))
        if not period:
            if high <= 300:
                period = "hr"
            elif low >= 15000:
                period = "yr"
            else:
                period = ""
        if period:
            if abs(high - low) < 0.005:
                return f"{_money(low, period, prefix)}/{period}"
            return f"{_money(low, period, prefix)}–{_money(high, period, prefix)}/{period}"

    match = _WAGE_RE.search(text)
    if match:
        a = (match.group(1) or match.group(3) or "").replace(",", "")
        b = (match.group(2) or match.group(4) or "").replace(",", "")
        if a:
            return f"{prefix}{a}–{prefix}{b}/hr" if b else f"{prefix}{a}/hr"

    match = _YEARLY_RE.search(text)
    if match:
        def _num(s: str) -> float:
            s = s.replace(",", "").replace(" ", "")
            return float(s[:-1]) * 1000 if s.lower().endswith("k") else float(s)
        a = _num(match.group(1))
        b = _num(match.group(2)) if match.group(2) else None
        if a >= 15000:
            if b and b > a:
                return f"{_money(a, 'yr', prefix)}–{_money(b, 'yr', prefix)}/yr"
            return f"{_money(a, 'yr', prefix)}/yr"
    return ""


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


def apply_details(listings: list[dict], cache: dict) -> None:
    """Copy cached detail fields onto listings (no network)."""
    for listing in listings:
        entry = cache.get(listing.get("id") or "")
        if not entry or entry.get("error") or entry.get("missing"):
            continue
        listing["detail_pay"] = entry.get("pay") or ""
        listing["detail_auth"] = list(entry.get("auth") or [])
        listing["detail_h1b"] = entry.get("sponsors_h1b")
        listing["detail_seasons"] = list(entry.get("seasons") or [])
        listing["detail_desc_terms"] = entry.get("desc_terms") or ""
        listing["functions"] = list(entry.get("functions") or [])
