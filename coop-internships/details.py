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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from pay import pay_from_fields, pay_from_text
from scrapers.filters import auth_labels_from_text, terms_from_description

ROOT = Path(__file__).parent
CACHE_PATH = ROOT / "details-cache.json"
DETAIL_URL = "https://api.simplify.jobs/v2/job-posting/:id/{id}/company"
HEADERS = {"User-Agent": "WiE-Coop-Listings/1.0 (github; educational)"}
TIMEOUT = 20
PAGE_TIMEOUT = 15
WORKERS = 8
RETRY_FAILED_AFTER = 6 * 60 * 60
CACHE_VERSION = 3

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

def _plain_text(raw: str | None) -> str:
    text = raw or ""
    for _ in range(2):  # some ATS double-escape (&amp;#xa;)
        text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _pay_label(posting: dict, text: str) -> str:
    """Pay from Simplify's salary fields, else from the description text."""
    return pay_from_fields(
        posting.get("min_salary"), posting.get("max_salary"),
        posting.get("salary_period"), posting.get("currency_type"),
    ) or pay_from_text(text)


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


# ---------------------------------------------------------------------------
# Fallback: the company's own posting page
# ---------------------------------------------------------------------------
# Every posting's own Apply page is read once (not only when Simplify has no pay),
# because Simplify's copy sometimes drops or garbles the pay section. Pay found on the
# company's page wins over Simplify. robots.txt is respected; a site that refuses
# (401/403) is not asked again for that posting. Each run spends at most
# PAGE_TIME_LIMIT seconds on this, newest postings first, so new jobs are never held up.

PAGE_BUDGET = 400
PAGE_WORKERS = 6
PAGE_TIME_LIMIT = 90
PAGE_RETRY_AFTER = 6 * 60 * 60
_robots: dict[str, RobotFileParser] = {}
_robots_lock = threading.Lock()


def _allowed(url: str) -> bool:
    parts = urlparse(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return False
    base = f"{parts.scheme}://{parts.netloc}"
    with _robots_lock:
        parser = _robots.get(base)
    if parser is None:
        parser = RobotFileParser()
        try:
            response = requests.get(base + "/robots.txt", headers=HEADERS, timeout=10)
            parser.parse(response.text.splitlines() if response.status_code == 200 else [])
        except requests.RequestException:
            parser.parse([])
        with _robots_lock:
            _robots[base] = parser
    return parser.can_fetch(HEADERS["User-Agent"], url)


def _workday_api(url: str) -> str | None:
    """Workday pages are rendered by script; the same posting is public JSON at /wday/cxs/."""
    parts = urlparse(url)
    if "myworkdayjobs.com" not in parts.netloc:
        return None
    path = [piece for piece in parts.path.split("/") if piece]
    if path and re.fullmatch(r"[a-z]{2}-[A-Z]{2}", path[0]):
        path = path[1:]
    if len(path) < 2:
        return None
    tenant = parts.netloc.split(".")[0]
    return f"https://{parts.netloc}/wday/cxs/{tenant}/{path[0]}/{'/'.join(path[1:])}"


def _page_text(url: str) -> tuple[str, int]:
    api = _workday_api(url)
    target = api or url
    if not _allowed(target):
        return "", -1
    response = requests.get(
        target,
        headers={**HEADERS, "Accept": "application/json" if api else "text/html"},
        timeout=PAGE_TIMEOUT,
    )
    if response.status_code != 200:
        return "", response.status_code
    if api:
        info = (response.json() or {}).get("jobPostingInfo") or {}
        return _plain_text(info.get("jobDescription")), 200
    # Many careers sites keep the description in embedded JSON, so scripts are kept.
    raw = (
        response.text.replace("\\u0024", "$")
        .replace("\\u002F", "/")
        .replace("\\u002f", "/")
        .replace("\\/", "/")
        .replace('\\"', '"')
    )
    raw = re.sub(r"<style[\s\S]*?</style>", " ", raw, flags=re.IGNORECASE)
    return _plain_text(raw), 200


def _page_pay_one(listing: dict) -> tuple[str, dict]:
    listing_id = listing["id"]
    now = int(time.time())
    tries = int(listing.get("_page_tries") or 0) + 1
    try:
        text, status = _page_text(listing.get("url") or "")
    except (requests.RequestException, ValueError) as exc:
        return listing_id, {"page_checked": now, "page_status": f"error: {str(exc)[:80]}", "page_tries": tries}
    return listing_id, {
        "page_checked": now,
        "page_status": status,
        "page_pay": pay_from_text(text) if text else "",
        "page_tries": tries,
    }


def _page_needs_check(entry: dict, now: float) -> bool:
    if entry.get("error") or entry.get("missing"):
        return False
    checked = entry.get("page_checked")
    if not checked:
        return True
    status = entry.get("page_status")
    # Temporary failures (timeouts, rate limits, 5xx): retried on the next runs, then every 6 hours.
    temporary = status == 429 or (isinstance(status, int) and status >= 500) or str(status).startswith("error")
    if not temporary:
        return False
    return int(entry.get("page_tries") or 0) < 3 or now - int(checked) > PAGE_RETRY_AFTER


def fetch_page_pay(listings: list[dict], cache: dict, budget: int = PAGE_BUDGET) -> int:
    """Read pay from each posting's own page (newest first, time-boxed)."""
    now = time.time()
    todo = []
    for listing in sorted(listings, key=lambda item: -int(item.get("date_posted") or 0)):
        entry = cache.get(listing.get("id") or "")
        if entry and listing.get("url") and _page_needs_check(entry, now):
            todo.append({**listing, "_page_tries": entry.get("page_tries") or 0})
    todo = todo[:budget]
    if not todo:
        return 0
    deadline = time.time() + PAGE_TIME_LIMIT
    done = 0
    pool = ThreadPoolExecutor(PAGE_WORKERS)
    futures = [pool.submit(_page_pay_one, listing) for listing in todo]
    try:
        for future in as_completed(futures, timeout=max(1, deadline - time.time())):
            listing_id, update = future.result()
            cache[listing_id].update(update)
            done += 1
    except FuturesTimeout:
        pass  # the rest are checked on the next run
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return done


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
            listing["detail_pay"] = pay_from_text("pay " + override)
        entry = cache.get(listing.get("id") or "")
        if not entry or entry.get("error") or entry.get("missing"):
            continue
        if not override:
            # The company's own page wins; Simplify is the fallback.
            page_pay, simplify_pay = entry.get("page_pay") or "", entry.get("pay") or ""
            if page_pay.startswith("$") and simplify_pay.startswith("CA$"):
                # Canadian pages often write plain "$"; Simplify knows it is CAD.
                page_pay = page_pay.replace("$", "CA$")
            listing["detail_pay"] = page_pay or simplify_pay
        listing["detail_auth"] = list(entry.get("auth") or [])
        listing["detail_h1b"] = entry.get("sponsors_h1b")
        listing["detail_seasons"] = list(entry.get("seasons") or [])
        listing["detail_desc_terms"] = entry.get("desc_terms") or ""
        listing["functions"] = list(entry.get("functions") or [])
