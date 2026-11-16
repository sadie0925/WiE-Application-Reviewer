"""Listing filters for undergrad co-op/intern roles + CS vs other classification."""

from __future__ import annotations

import re
import time

from scrapers.location import filter_us_ca_locations, is_us_or_canada_location, listing_countries

INCLUDE_PATTERN = re.compile(
    r"\b(intern(ship)?|co-?op|undergraduate\s+intern)\b",
    re.IGNORECASE,
)

EXCLUDE_PATTERN = re.compile(
    r"\b("
    r"phd|doctorate|postdoc|post-doc|"
    r"recruiter|recruiting|head\s+of|"
    r"people\s+strategy|inside\s+sales"
    r")\b",
    re.IGNORECASE,
)

# Synonyms that mean new-grad / early undergrad hire (not only the words "new grad").
NEW_GRAD_TITLE_PATTERN = re.compile(
    r"\b("
    r"new\s*grad(?:uate)?|new-grad|"
    r"university\s+grad(?:uate)?|"
    r"college\s+grad(?:uate)?|"
    r"recent\s+grad(?:uate)?|"
    r"new\s+college\s+grad|"
    r"entry[\s-]?level|"
    r"early[\s-]?career|"
    r"campus\s+(?:hire|recruit)|"
    r"university\s+(?:hire|recruit)|"
    r"graduating\s+(?:senior|class)|"
    r"class\s+of\s+20\d{2}|"
    r"junior\s+(?:software|swe|sde|engineer|developer|firmware|full[\s-]?stack)"
    r")\b",
    re.IGNORECASE,
)

GRAD_ONLY_TITLE = re.compile(
    r"\b("
    r"ph\.?d\.?(?:\s+only)?|"
    r"doctorate|"
    r"post[\s-]?doc|"
    r"master'?s(?:\s+(?:only|required|degree))?|"
    r"ms[\s/]+phd|phd[\s/]+ms|"
    r"graduate\s+student|"
    r"m\.?s\.?\s+only"
    r")\b",
    re.IGNORECASE,
)

SENIOR_TITLE = re.compile(
    r"\b(senior|staff|principal|distinguished|director|manager|"
    r"lead\s+(?:software|engineer)|mid[\s-]?level|ii+|iii+)\b",
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

# One pass over title+description for $/hr. No extra HTTP.
_WAGE_RE = re.compile(
    r"(?:"
    r"\$\s*(\d{2,3}(?:,\d{3})?(?:\.\d{1,2})?)"
    r"(?:\s*[-–—]\s*\$?\s*(\d{2,3}(?:,\d{3})?(?:\.\d{1,2})?))?"
    r"\s*(?:/|\s*per\s*)\s*(?:hr|hrs|hour)\b"
    r"|"
    r"(\d{2,3}(?:,\d{3})?(?:\.\d{1,2})?)"
    r"(?:\s*[-–—]\s*(\d{2,3}(?:,\d{3})?(?:\.\d{1,2})?))?"
    r"\s*(?:USD|CAD|\$)?\s*(?:/|\s*per\s*)\s*(?:hr|hrs|hour)\b"
    r")",
    re.IGNORECASE,
)


def is_intern_title(title: str) -> bool:
    if EXCLUDE_PATTERN.search(title) or NEW_GRAD_TITLE_PATTERN.search(title):
        return False
    if GRAD_ONLY_TITLE.search(title):
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
    """Return 'cs' or 'other' for README sectioning."""
    title = listing.get("title") or ""
    if OTHER_TITLE_PATTERN.search(title) and not CS_TITLE_PATTERN.search(title):
        return "other"
    if CS_TITLE_PATTERN.search(title):
        return "cs"

    category = str(listing.get("category") or "").strip().lower()
    if category in CS_CATEGORIES:
        return "cs"

    return "other"


def _grad_only_text(listing: dict) -> bool:
    """True when title/description clearly requires master's or PhD only."""
    text = f"{listing.get('title') or ''}\n{listing.get('description') or ''}"
    if re.search(
        r"\b(ph\.?d|doctorate|post[\s-]?doc)\s+(required|only|preferred)\b|"
        r"\b(requires?|must have)\s+a?\s*(ph\.?d|doctorate|master'?s)\b|"
        r"\bmaster'?s\s+only\b|"
        r"\bph\.?d\.?\s+only\b",
        text,
        re.IGNORECASE,
    ):
        # Allow if the same text also clearly invites bachelor's / new grads.
        if re.search(
            r"\b(bachelor|undergrad|new\s*grad|entry[\s-]?level|early[\s-]?career)\b",
            text,
            re.IGNORECASE,
        ):
            return False
        return True
    return False


def passes_new_grad_filters(listing: dict) -> bool:
    """Software new-grad / early-career roles. Master's/PhD-only and senior roles out."""
    if not listing.get("active") or listing.get("is_visible") is False:
        return False
    title = listing.get("title") or ""
    if INCLUDE_PATTERN.search(title):
        return False
    if SENIOR_TITLE.search(title) and not NEW_GRAD_TITLE_PATTERN.search(title):
        return False
    if GRAD_ONLY_TITLE.search(title):
        if re.search(r"\b(ph\.?d|doctorate|post[\s-]?doc)\b", title, re.IGNORECASE):
            return False
        if re.search(r"\bmaster'?s\s+only\b|\bm\.?s\.?\s+only\b", title, re.IGNORECASE):
            return False
        if not NEW_GRAD_TITLE_PATTERN.search(title) and not re.search(
            r"\b(bachelor|undergrad)\b", title, re.IGNORECASE
        ):
            if re.search(r"\bmaster", title, re.IGNORECASE):
                return False
    if _grad_only_text(listing):
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
    new_grad_max_age_days: int = 60,
    now: float | None = None,
) -> tuple[list[dict], dict]:
    """Drop closed applications. Interns expire after max_age_days; new grads after 2 months."""
    current = time.time() if now is None else now
    intern_age = max_age_days * 24 * 60 * 60
    new_grad_age = new_grad_max_age_days * 24 * 60 * 60
    kept: list[dict] = []
    stats = {"closed": 0, "expired": 0, "not_software": 0, "kept": 0}
    for listing in listings:
        if listing.get("active") is False or listing.get("is_visible") is False:
            stats["closed"] += 1
            continue
        if listing.get("track") == "new_grad" and listing.get("program") != "cs":
            stats["not_software"] += 1
            continue
        if listing.get("track") == "new_grad" and not is_undergrad_degrees(listing.get("degrees")):
            stats["closed"] += 1
            continue
        if listing.get("track") == "new_grad" and _grad_only_text(listing):
            stats["closed"] += 1
            continue
        added = listing_added_at(listing)
        limit = new_grad_age if listing.get("track") == "new_grad" else intern_age
        if added <= 0 or (current - added) > limit:
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
    if _grad_only_text(listing):
        return False

    locations = listing.get("locations", [])
    if not any(is_us_or_canada_location(loc) for loc in locations):
        return False

    return True


def hourly_wage_label(listing: dict) -> str:
    """Pay from the posting (Simplify salary fields or $/hr, $/yr in the text). Blank if absent."""
    detail = (listing.get("detail_pay") or "").strip()
    if detail:
        # Simplify often tags Canadian postings as USD; Canadian roles pay CAD.
        if detail.startswith("$") and listing_countries(listing) == {"Canada"}:
            detail = detail.replace("$", "CA$")
        return detail
    cached = (listing.get("hourly_wage") or "").strip()
    if cached:
        return cached
    text = f"{listing.get('title') or ''}\n{listing.get('description') or ''}"
    match = _WAGE_RE.search(text)
    if not match:
        return ""
    low = match.group(1) or match.group(3)
    high = match.group(2) or match.group(4)
    if not low:
        return ""
    low = low.replace(",", "")
    if high:
        high = high.replace(",", "")
        return f"${low}–${high}/hr"
    return f"${low}/hr"


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
    terms = listing.get("terms")
    if isinstance(terms, list) and terms:
        normalized["terms"] = [str(item) for item in terms if item]
    wage = hourly_wage_label(normalized)
    if wage:
        normalized["hourly_wage"] = wage
    normalized["program"] = classify_program(normalized)
    return normalized




# ---------------------------------------------------------------------------
# Software-only new grad
# ---------------------------------------------------------------------------

# Titles that are clearly software engineering (or a close software role).
SWE_TITLE_PATTERN = re.compile(
    r"\b("
    r"software|swe|sde|sdet|developers?|programmers?|programming|coder|"
    r"full[\s-]?stack|front[\s-]?end|back[\s-]?end|"
    r"web\s+(?:engineer|developer)|mobile|ios|android|"
    r"dev\s*ops|devsecops|mlops|site\s+reliability|sre|"
    r"platform\s+engineer|cloud\s+(?:engineer|developer)|infrastructure\s+engineer|"
    r"(?:machine\s+learning|ml|ai|ai/ml|llm|applied\s+ai)\s+engineer|"
    r"data\s+engineer|firmware|embedded\s+software|"
    r"forward[\s-]deployed|(?:test|qa)\s+automation|"
    r"systems?\s+development\s+engineer|application\s+development|"
    r"game\s+(?:engineer|programmer)|compiler\s+engineer"
    r")\b",
    re.IGNORECASE,
)

# Never software engineering, even when a software keyword appears.
NON_SWE_HARD = re.compile(
    r"\b(sales|recruit\w*|technician|marketing|rtl|account\s+manager)\b",
    re.IGNORECASE,
)

# Generic titles ("Engineer 1", "Associate Engineer") that need Simplify's job function.
_GENERIC_ENGINEER = re.compile(r"\b(engineer|engineering)\b", re.IGNORECASE)
_NON_SWE_GENERIC = re.compile(
    r"\b(hardware|electrical|mechanical|civil|chemical|manufacturing|process|"
    r"mechatronics|structural|powertrain|vehicle|field|support|analyst|scientist|"
    r"research|gis|rf|asic|fpga|silicon|validation|power|controls?|quality|systems?|"
    r"sales|solutions?|applications?|test|network|electronics?|optical|automation)\b",
    re.IGNORECASE,
)
_SWE_FUNCTIONS = {
    "Software Engineering",
    "Backend Engineering",
    "Full-Stack Engineering",
    "Frontend Engineering",
    "Systems Software Engineering",
    "Mobile Engineering",
    "Desktop Application Development",
    "Game Engineering",
}


def is_software_new_grad(listing: dict) -> bool:
    """New-grad boards: software engineering roles only (not other engineering, not analyst)."""
    title = listing.get("title") or ""
    if NON_SWE_HARD.search(title):
        return False
    if SWE_TITLE_PATTERN.search(title):
        return True
    functions = set(listing.get("functions") or [])
    if (
        _GENERIC_ENGINEER.search(title)
        and not _NON_SWE_GENERIC.search(title)
        and "Software Engineering" in functions
        and functions & _SWE_FUNCTIONS
    ):
        return True
    return False


def may_be_software_new_grad(listing: dict) -> bool:
    """Cheap pre-filter before details are known (generic titles still pass)."""
    title = listing.get("title") or ""
    if NON_SWE_HARD.search(title):
        return False
    if SWE_TITLE_PATTERN.search(title):
        return True
    return bool(_GENERIC_ENGINEER.search(title) and not _NON_SWE_GENERIC.search(title))


# ---------------------------------------------------------------------------
# Term
# ---------------------------------------------------------------------------

# Waterloo has three terms only: Fall, Winter/Spring, Summer.
_SEASON_LABEL = {
    "winter": "Winter/Spring",
    "spring": "Winter/Spring",
    "fall": "Fall",
    "autumn": "Fall",
    "summer": "Summer",
}
_SEASON_ORDER = {"Fall": 0, "Winter/Spring": 1, "Summer": 2}
_SEASON_WORD = re.compile(
    r"\b(winter|spring|fall|autumn|summer)\b(?:\s*(?:term|semester|session)?\s*[,']?\s*(20\d{2}))?",
    re.IGNORECASE,
)
# Descriptions mention seasons for graduation dates a lot ("graduating Spring 2027").
# Only count a season + year when the text around it is about the work term itself.
_WORK_TERM_CONTEXT = re.compile(
    r"\b(start\w*|begin\w*|commenc\w*|join\w*|intern\w*|co-?op|work\s+term|term|"
    r"cohort|program\s+runs|placement|duration|targeting|class\s+starts?)\b",
    re.IGNORECASE,
)
_GRAD_CONTEXT = re.compile(
    r"\b(graduat\w*|degree|diploma|obtain\w*|complet\w*|enrol\w*|academic|"
    r"expected|anticipated|class\s+of|finish\w*|pursuing|student)\b",
    re.IGNORECASE,
)


_MONTH_YEAR = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+(20\d{2})\b",
    re.IGNORECASE,
)
_MONTH_TERM = {
    "jan": "Winter/Spring", "feb": "Winter/Spring", "mar": "Winter/Spring", "apr": "Winter/Spring",
    "may": "Summer", "jun": "Summer", "jul": "Summer", "aug": "Summer",
    "sep": "Fall", "oct": "Fall", "nov": "Fall", "dec": "Fall",
}


def _terms_from_text(text: str, *, strict: bool = False) -> str:
    found = []
    seen = set()
    for match in _SEASON_WORD.finditer(text):
        word = match.group(1).lower()
        year = match.group(2) or ""
        after = text[match.end(): match.end() + 16]
        if word == "summer" and re.match(r"\s+games\b", after, re.IGNORECASE):
            continue
        if strict:
            # Descriptions: need a year, and not "graduating by Spring 2027".
            if not year:
                continue
            near = text[max(0, match.start() - 60): match.end() + 30]
            if _GRAD_CONTEXT.search(near) or not _WORK_TERM_CONTEXT.search(near):
                continue
        elif not year:
            window = text[max(0, match.start() - 40): match.end() + 40]
            if word in {"fall", "spring", "summer"}:
                if not re.search(
                    r"\b(intern|internship|co-?op|term|student|analyst|new\s*grad|engineer|hire)\b",
                    window,
                    re.IGNORECASE,
                ):
                    continue
        label = _SEASON_LABEL[word]
        key = (label, year)
        if key in seen:
            continue
        seen.add(key)
        found.append((year or "0000", _SEASON_ORDER[label], f"{label} {year}".strip()))
    if not strict:
        # Titles like "Software Developer Intern (May 2027 - 12 months)".
        for match in _MONTH_YEAR.finditer(text):
            after = text[match.end(): match.end() + 12]
            if re.match(r"\s*grad", after, re.IGNORECASE):
                continue
            label = _MONTH_TERM[match.group(1)[:3].lower()]
            year = match.group(2)
            if (label, year) in seen:
                continue
            seen.add((label, year))
            found.append((year, _SEASON_ORDER[label], f"{label} {year}"))
    # Drop a bare "Summer" when "Summer 2027" is also there.
    with_year = {label.rsplit(" ", 1)[0] for year, _order, label in found if year != "0000"}
    found = [item for item in found if item[0] != "0000" or item[2] not in with_year]
    found.sort()
    return ", ".join(item[2] for item in found)


def terms_from_description(text: str) -> str:
    """Work term stated in a posting description (season + year only)."""
    return _terms_from_text(text or "", strict=True)


def work_term_label(listing: dict) -> str:
    """Waterloo term: title, then Simplify's season tags, then feed terms, then description."""
    found = _terms_from_text(listing.get("title") or "")
    if found:
        return found
    seasons = listing.get("detail_seasons") or []
    if seasons:
        found = _terms_from_text(" ".join(seasons))
        if found:
            return found
    terms = [str(item) for item in listing.get("terms") or [] if item and str(item) != "N/A"]
    if terms:
        found = _terms_from_text(" ".join(terms))
        if found:
            return found
    return listing.get("detail_desc_terms") or ""


# ---------------------------------------------------------------------------
# Work authorization
# ---------------------------------------------------------------------------

# Optional Simplify enum in the GitHub feed.
_SPONSORSHIP_LABELS = {
    "Offers Sponsorship": "Sponsors",
    "Does Not Offer Sponsorship": "No sponsorship",
    "U.S. Citizenship is Required": "US citizenship",
}

_AUTH_PHRASES = (
    # clearance / export
    (r"ts\s*/\s*sci|top\s+secret|secret\s+(?:security\s+)?clearance|security\s+clearance|"
     r"(?:active|obtain|maintain|possess)\w*\s+(?:a\s+|an\s+)?(?:dod\s+|u\.?s\.?\s+government\s+)?clearance|"
     r"polygraph|dod\s+clearance", "US clearance"),
    (r"itar|u\.?s\.?\s+persons?", "US person"),
    # citizenship
    (r"u\.?s\.?\s+citizen(?:s|ship)?|united\s+states\s+citizen(?:s|ship)?|"
     r"citizenship\s+(?:is\s+)?required|must\s+be\s+a\s+citizen", "US citizenship"),
    (r"canadian\s+citizen(?:s|ship)?|citizens?\s+or\s+permanent\s+residents?\s+of\s+canada|"
     r"protected\s+person|controlled\s+goods", "Canadian citizen/PR"),
    (r"(?:u\.?s\.?\s+)?permanent\s+residents?|green\s+card", "Citizen/PR only"),
    # work authorization
    (r"(?:authori[sz]ed|eligible|entitled|permitted)\s+to\s+work\s+in\s+(?:the\s+)?(?:u\.?s\.?a?\.?|united\s+states|america)|"
     r"u\.?s\.?\s+work\s+authori[sz]ation", "US work auth"),
    (r"(?:authori[sz]ed|eligible|entitled|permitted)\s+to\s+work\s+in\s+canada|"
     r"canadian\s+work\s+(?:authori[sz]ation|permit)|right\s+to\s+work\s+in\s+canada", "Canada work auth"),
    (r"(?:legally\s+)?authori[sz]ed\s+to\s+work|unrestricted\s+(?:right|authori[sz]ation)\s+to\s+work|"
     r"work\s+authori[sz]ation\s+without\s+restriction", "Work auth required"),
    # sponsorship
    (r"(?:not|unable\s+to|cannot|can\s*not|won'?t|will\s+not|do(?:es)?\s+not|n't)\s+"
     r"(?:\w+\s+){0,3}(?:sponsor|sponsorship|provide\s+(?:visa|immigration))|"
     r"no\s+(?:visa\s+|immigration\s+)?sponsorship|without\s+(?:visa\s+|immigration\s+|employer\s+)?sponsorship|"
     r"sponsorship\s+(?:is\s+)?not\s+(?:available|offered|provided)|"
     r"requir\w*\s+(?:\w+\s+){0,3}sponsorship|"
     r"no\s+(?:opt|cpt|h-?1b)\b|(?:opt|cpt|stem\s+opt)\s+(?:is\s+)?not\s+(?:accepted|eligible|supported)", "No sponsorship"),
    (r"(?:will|can|does|do)\s+(?:\w+\s+)?sponsor\b|offers?\s+(?:visa\s+)?sponsorship|"
     r"(?:visa\s+)?sponsorship\s+(?:is\s+)?(?:available|offered|provided)", "Sponsors"),
)
_AUTH_COMPILED = [
    (re.compile(r"\b(?:" + pattern + r")(?![a-z])", re.IGNORECASE), label)
    for pattern, label in _AUTH_PHRASES
]
_AUTH_TRIGGER_RE = re.compile(
    r"citizen|sponsor|clearance|visa|green\s*card|itar|authori[sz]|resident|"
    r"u\.?s\.?\s+person|polygraph|export|\bopt\b|h-?1b|right\s+to\s+work|controlled\s+goods|"
    r"protected\s+person|entitled\s+to\s+work|eligible\s+to\s+work",
    re.IGNORECASE,
)
# EEO boilerplate lists "citizenship" as a protected status — not a requirement.
_EEO_RE = re.compile(
    r"(?:without\s+regard\s+to|regardless\s+of|discriminat\w+|protected|on\s+the\s+basis\s+of|"
    r"equal\s+(?:employment\s+)?opportunity)[^.]{0,250}",
    re.IGNORECASE,
)
_AUTH_ORDER = [
    "US clearance",
    "US citizenship",
    "US person",
    "Citizen/PR only",
    "Canadian citizen/PR",
    "No sponsorship",
    "US work auth",
    "Canada work auth",
    "Work auth required",
    "Sponsors",
]
_RESTRICTIVE_AUTH = set(_AUTH_ORDER) - {"Sponsors"}


def _tidy_auth(labels: list[str]) -> list[str]:
    seen = set(labels)
    if "US citizenship" in seen:
        seen -= {"Citizen/PR only", "US work auth", "Work auth required"}
    if "Canadian citizen/PR" in seen:
        seen -= {"Citizen/PR only", "Canada work auth", "Work auth required"}
    if seen & {"US work auth", "Canada work auth"}:
        seen.discard("Work auth required")
    if "US clearance" in seen:
        seen.discard("US person")
    if "Sponsors" in seen and seen & {"No sponsorship", "US citizenship", "US clearance", "US person"}:
        seen.discard("Sponsors")
    return [label for label in _AUTH_ORDER if label in seen]


def auth_labels_from_text(text: str) -> list[str]:
    """Work-auth barriers stated in title/description text."""
    if not text or not _AUTH_TRIGGER_RE.search(text):
        return []
    cleaned = _EEO_RE.sub(" ", text.replace("\u00a0", " "))
    labels = [label for regex, label in _AUTH_COMPILED if regex.search(cleaned)]
    return _tidy_auth(labels)


def work_auth_label(listing: dict) -> str:
    """Work-auth barriers for UW students. Blank when the posting says nothing."""
    labels: list[str] = list(listing.get("detail_auth") or [])
    mapped = _SPONSORSHIP_LABELS.get((listing.get("sponsorship") or "").strip())
    if mapped:
        labels.append(mapped)
    labels.extend(auth_labels_from_text(listing.get("title") or ""))

    # Simplify's H-1B flag only matters for US roles.
    h1b = listing.get("detail_h1b")
    if h1b is not None:
        if "United States" in listing_countries(listing):
            labels.append("Sponsors" if h1b else "No sponsorship")
    return ", ".join(_tidy_auth(labels))
