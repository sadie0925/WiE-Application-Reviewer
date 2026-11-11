"""Listing filters for undergrad co-op/intern roles + CS vs other classification."""

from __future__ import annotations

import re
import time

from scrapers.location import filter_us_ca_locations, is_us_or_canada_location

INCLUDE_PATTERN = re.compile(
    r"\b(intern(ship)?|co-?op|undergraduate\s+intern)\b",
    re.IGNORECASE,
)

EXCLUDE_PATTERN = re.compile(
    r"\b("
    r"phd|doctorate|postdoc|post-doc|"
    r"recruiter|recruiting|head\s+of|"
    r"people\s+strategy|inside\s+sales|"
    r"early\s+career(?!\s+(engineer|developer|intern))"
    r")\b",
    re.IGNORECASE,
)

NEW_GRAD_TITLE_PATTERN = re.compile(
    r"\b("
    r"new\s*grad(?:uate)?|new-grad|"
    r"university\s+grad(?:uate)?|"
    r"entry[\s-]?level|"
    r"junior\s+(?:software|swe|sde|engineer|developer|firmware)"
    r")\b",
    re.IGNORECASE,
)

GRAD_ONLY_TITLE = re.compile(
    r"\b("
    r"ph\.?d\.?(?:\s+only)?|"
    r"doctorate|"
    r"post[\s-]?doc|"
    r"master'?s(?:\s+only)?|"
    r"ms[\s/]+phd|phd[\s/]+ms"
    r")\b",
    re.IGNORECASE,
)

# Title / category signals for CS & closely related tech software roles
CS_TITLE_PATTERN = re.compile(
    r"\b("
    r"software|swe|sde|developer|programmer|programming|"
    r"computer\s*science|comp(?:uter)?\s*sci|"
    r"full[\s-]?stack|front[\s-]?end|back[\s-]?end|"
    r"mobile\s*(?:app|engineer|developer)|ios|android|"
    r"machine\s*learning|deep\s*learning|\bml\b|\bai\b|artificial\s*intelligence|"
    r"data\s*(?:scientist|science|engineer|engineering|analyst|analytics)|"
    r"devops|sre|site\s*reliability|"
    r"cyber\s*security|security\s*engineer|infosec|"
    r"cloud\s*(?:engineer|developer)|platform\s*engineer|"
    r"firmware|embedded\s*software|compiler|"
    r"quant(?:itative)?\s*(?:developer|engineer|technologist)|"
    r"web\s*developer|app(?:lication)?\s*developer|"
    r"systems?\s*(?:software|engineer)|infrastructure\s*(?:engineer|software)"
    r")\b",
    re.IGNORECASE,
)

CS_CATEGORIES = {
    "software",
    "software engineering",
    "ai/ml/data",
    "data science, ai & machine learning",
    "quant",
    "quantitative finance",
}

# Clear non-CS title signals — win over a mis-tagged Simplify category
OTHER_TITLE_PATTERN = re.compile(
    r"\b("
    r"mechanical|electrical|civil|chemical|biomedical|aerospace|"
    r"forestry|agriculture|agricultur|"
    r"marketing|sales|finance(?!\s*(?:tech|software|engineer|developer))|"
    r"accounting|audit|hr\b|human\s*resources|recruit|"
    r"supply\s*chain|operations(?!\s*(?:research|engineer|software))|"
    r"business\s*(?:analyst|strategy|development|operations)|"
    r"project\s*manager|program\s*manager|"
    r"relationship\s*manager|customer\s*connections|"
    r"optical\s*modem|hardware(?!\s*software)|asic|fpga|"
    r"rf\b|radio\s*frequency|photonics|nanofabrication|"
    r"product\s*(?:manager|management|marketing|intern|ops|operations)"
    r")\b",
    re.IGNORECASE,
)


def is_intern_title(title: str) -> bool:
    if EXCLUDE_PATTERN.search(title) or NEW_GRAD_TITLE_PATTERN.search(title):
        return False
    return bool(INCLUDE_PATTERN.search(title))


def is_undergrad_degrees(degrees: list | None) -> bool:
    """True when undergrads can apply. Master's/PhD-only rows are False."""
    if not degrees:
        return True

    lower = [str(d).lower() for d in degrees]
    has_bachelor = any("bachelor" in d or "associate" in d for d in lower)
    only_grad = all(
        ("master" in d) or ("phd" in d) or ("doctorate" in d) or ("graduate" in d)
        for d in lower
    )
    if only_grad and not has_bachelor:
        return False
    if any("phd" in d or "doctorate" in d for d in lower) and not has_bachelor:
        return False
    if any("master" in d for d in lower) and not has_bachelor:
        return False
    return True


def classify_program(listing: dict) -> str:
    """Return 'cs' or 'other' for README sectioning.

    Prefer title signals. CS covers software/CS/data/AI/ML/quant-dev roles.
    Clear non-CS title keywords beat a mis-tagged feed category.
    """
    title = listing.get("title") or ""
    if OTHER_TITLE_PATTERN.search(title) and not CS_TITLE_PATTERN.search(title):
        return "other"
    if CS_TITLE_PATTERN.search(title):
        return "cs"

    category = str(listing.get("category") or "").strip().lower()
    if category in CS_CATEGORIES:
        return "cs"

    return "other"


def passes_new_grad_filters(listing: dict) -> bool:
    """Software new-grad roles. Master's/PhD-only titles and degree lists are dropped."""
    if not listing.get("active") or listing.get("is_visible") is False:
        return False
    title = listing.get("title") or ""
    if INCLUDE_PATTERN.search(title):
        return False
    if GRAD_ONLY_TITLE.search(title) and not NEW_GRAD_TITLE_PATTERN.search(title):
        # "PhD Software Engineer" stays out; "New Grad" wins when both appear.
        if re.search(r"\bph\.?d\b|\bmaster", title, re.IGNORECASE):
            return False
    if GRAD_ONLY_TITLE.search(title) and not re.search(
        r"\b(bachelor|undergrad|new\s*grad|entry[\s-]?level|junior)\b",
        title,
        re.IGNORECASE,
    ):
        if re.search(r"\b(ph\.?d|doctorate|post[\s-]?doc)\b", title, re.IGNORECASE):
            return False
        if re.search(r"\bmaster'?s\s+only\b", title, re.IGNORECASE):
            return False
    if not is_undergrad_degrees(listing.get("degrees")):
        return False
    if not any(is_us_or_canada_location(loc) for loc in listing.get("locations") or []):
        return False
    return True


def listing_added_at(listing: dict) -> int:
    try:
        posted = int(listing.get("date_posted") or 0)
    except (TypeError, ValueError):
        posted = 0
    if posted > 0:
        return posted
    try:
        return int(listing.get("date_updated") or 0)
    except (TypeError, ValueError):
        return 0


def purge_listings(
    listings: list[dict],
    *,
    max_age_days: int = 30,
    now: float | None = None,
) -> tuple[list[dict], dict]:
    """Drop closed applications. Internships also expire after max_age_days.

    Active software new-grad rows stay until the feed marks them closed.
    Master's/PhD-only new-grad rows are removed.
    """
    current = time.time() if now is None else now
    intern_age = max_age_days * 24 * 60 * 60
    kept: list[dict] = []
    stats = {"closed": 0, "expired": 0, "kept": 0}
    for listing in listings:
        if listing.get("active") is False or listing.get("is_visible") is False:
            stats["closed"] += 1
            continue
        if listing.get("track") == "new_grad" and listing.get("program") != "cs":
            stats["closed"] += 1
            continue
        if listing.get("track") == "new_grad" and not is_undergrad_degrees(listing.get("degrees")):
            stats["closed"] += 1
            continue
        if listing.get("track") == "new_grad":
            kept.append(listing)
            continue
        added = listing_added_at(listing)
        if added <= 0 or (current - added) > intern_age:
            stats["expired"] += 1
            continue
        kept.append(listing)
    stats["kept"] = len(kept)
    return kept, stats


def passes_listing_filters(listing: dict, *, require_active: bool = True) -> bool:
    if require_active:
        if not listing.get("active"):
            return False
        if listing.get("is_visible") is False:
            return False

    title = listing.get("title", "")
    if not is_intern_title(title):
        return False
    if not is_undergrad_degrees(listing.get("degrees")):
        return False

    locations = listing.get("locations", [])
    if not any(is_us_or_canada_location(loc) for loc in locations):
        return False

    return True


def normalize_filtered_listing(listing: dict, source: str, track: str = "intern") -> dict:
    """Return listing with US/CA locations only and consistent fields."""
    us_ca_locs = filter_us_ca_locations(listing.get("locations", []))
    normalized = {
        "id": listing.get("id", ""),
        "company_name": listing.get("company_name", ""),
        "company_url": listing.get("company_url", ""),
        "title": listing.get("title", "").strip(),
        "url": listing.get("url", ""),
        "locations": us_ca_locs or ["Unknown"],
        "active": True,
        "is_visible": True,
        "source": source,
        "date_posted": listing.get("date_posted", 0),
        "date_updated": listing.get("date_updated", 0),
        "category": listing.get("category", ""),
        "sponsorship": listing.get("sponsorship", ""),
        "degrees": list(listing.get("degrees") or []),
        "track": track,
    }
    description = (listing.get("description") or "").strip()
    if description:
        normalized["description"] = description
    # Keep season labels from the feed only as a fallback signal for the board.
    terms = listing.get("terms")
    if isinstance(terms, list) and terms:
        normalized["terms"] = [str(item) for item in terms if item]
    normalized["program"] = classify_program(normalized)
    return normalized


# Waterloo's spring term is May–August. US postings call that summer.
_SEASON_LABEL = {
    "winter": "Winter",
    "spring": "Spring",
    "fall": "Fall",
    "autumn": "Fall",
    "summer": "Spring",
}
_SEASON_ORDER = {"Winter": 0, "Spring": 1, "Fall": 2}
_SEASON_WORD = re.compile(
    r"\b(winter|spring|fall|autumn|summer)\b(?:\s+(20\d{2}))?",
    re.IGNORECASE,
)

# Feed sponsorship enum → board label. Checked in O(1).
_SPONSORSHIP_LABELS = {
    "Offers Sponsorship": "Sponsors",
    "Does Not Offer Sponsorship": "No sponsorship",
    "U.S. Citizenship is Required": "US citizenship",
}

# Phrase → label. Longer phrases first. One lowercase scan of the posting text.
# These mark US-person / no-visa / clearance barriers for UW students.
_AUTH_PHRASES: tuple[tuple[str, str], ...] = tuple(
    sorted(
        (
            ("ts/sci", "US clearance"),
            ("ts sci", "US clearance"),
            ("top secret", "US clearance"),
            ("secret clearance", "US clearance"),
            ("security clearance", "US clearance"),
            ("us clearance", "US clearance"),
            ("u.s. clearance", "US clearance"),
            ("u.s. person", "US person"),
            ("u.s. persons", "US person"),
            ("us person", "US person"),
            ("us persons", "US person"),
            ("u.s. citizenship is required", "US citizenship"),
            ("us citizenship is required", "US citizenship"),
            ("u.s. citizen", "US citizenship"),
            ("u.s. citizens", "US citizenship"),
            ("us citizen", "US citizenship"),
            ("us citizens", "US citizenship"),
            ("citizenship required", "US citizenship"),
            ("must be a citizen", "US citizenship"),
            ("must be a u.s. citizen", "US citizenship"),
            ("must be a us citizen", "US citizenship"),
            ("permanent resident", "PR only"),
            ("permanent residents", "PR only"),
            ("u.s. permanent resident", "PR only"),
            ("us permanent resident", "PR only"),
            ("green card", "PR only"),
            ("authorized to work", "Work auth required"),
            ("legally authorized to work", "Work auth required"),
            ("work authorization", "Work auth required"),
            ("without restriction", "Work auth required"),
            ("without sponsorship", "No sponsorship"),
            ("no sponsorship", "No sponsorship"),
            ("does not sponsor", "No sponsorship"),
            ("do not sponsor", "No sponsorship"),
            ("will not sponsor", "No sponsorship"),
            ("unable to sponsor", "No sponsorship"),
            ("not offer sponsorship", "No sponsorship"),
            ("does not offer sponsorship", "No sponsorship"),
            ("not provide visa", "No sponsorship"),
            ("no visa sponsorship", "No sponsorship"),
            ("visa not provided", "No sponsorship"),
            ("cannot sponsor", "No sponsorship"),
            ("won't sponsor", "No sponsorship"),
            ("offers sponsorship", "Sponsors"),
            ("offer sponsorship", "Sponsors"),
            ("visa sponsorship", "Sponsors"),
            ("will sponsor", "Sponsors"),
            ("sponsorship available", "Sponsors"),
        ),
        key=lambda item: -len(item[0]),
    )
)


def _listing_text(listing: dict) -> str:
    parts = [
        listing.get("title") or "",
        listing.get("description") or "",
        listing.get("sponsorship") or "",
    ]
    return "\n".join(parts)


def work_term_label(listing: dict) -> str:
    """Waterloo term from the title or description. Blank when neither says one.

    Summer is reported as Spring. "Summer Games" is a program name, not a term.
    Feed `terms` is only used when the title/description is silent.
    """
    primary = f"{listing.get('title') or ''}\n{listing.get('description') or ''}"
    found = _terms_from_text(primary)
    if found:
        return found
    terms = listing.get("terms") or []
    if not terms:
        return ""
    return _terms_from_text(" ".join(str(item) for item in terms))


def _terms_from_text(text: str) -> str:
    found = []
    seen = set()
    for match in _SEASON_WORD.finditer(text):
        word = match.group(1).lower()
        after = text[match.end(): match.end() + 16]
        if word == "summer" and re.match(r"\s+games\b", after, re.IGNORECASE):
            continue
        if word == "summer":
            window = text[max(0, match.start() - 40): match.end() + 40]
            seasonal = match.group(2) or re.search(
                r"\b(intern|internship|co-?op|term|student|analyst|new\s*grad|engineer)\b",
                window,
                re.IGNORECASE,
            )
            if not seasonal:
                continue
        label = _SEASON_LABEL[word]
        year = match.group(2) or ""
        key = (label, year)
        if key in seen:
            continue
        seen.add(key)
        found.append((year or "0000", _SEASON_ORDER[label], f"{label} {year}".strip()))
    found.sort()
    return ", ".join(item[2] for item in found)


_RESTRICTIVE_AUTH = {
    "No sponsorship",
    "US citizenship",
    "US person",
    "PR only",
    "US clearance",
    "Work auth required",
}


def work_auth_label(listing: dict) -> str:
    """US-only / no-visa / clearance signals that block many UW students.

    Uses the feed sponsorship enum first, then a single lowercase scan of a
    fixed phrase map so each posting is O(text length), not a stack of regexes.
    """
    labels: list[str] = []
    seen: set[str] = set()

    sponsorship = (listing.get("sponsorship") or "").strip()
    mapped = _SPONSORSHIP_LABELS.get(sponsorship)
    if mapped:
        labels.append(mapped)
        seen.add(mapped)

    haystack = _listing_text(listing).lower().replace("\u00a0", " ")
    for phrase, label in _AUTH_PHRASES:
        if label in seen:
            continue
        # Do not mark "Sponsors" when a restriction phrase already matched.
        if label == "Sponsors" and (seen & _RESTRICTIVE_AUTH):
            continue
        if phrase in haystack:
            labels.append(label)
            seen.add(label)
    if "Sponsors" in seen and (seen & _RESTRICTIVE_AUTH):
        labels = [item for item in labels if item != "Sponsors"]
    return ", ".join(labels)
