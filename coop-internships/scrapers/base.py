import re
import uuid

# Must match at least one of these
INCLUDE_PATTERN = re.compile(
    r"\b(intern(ship)?|co-?op|undergraduate\s+intern)\b",
    re.IGNORECASE,
)

# Exclude grad / non-student / recruiting roles even if they contain "intern"
EXCLUDE_PATTERN = re.compile(
    r"\b("
    r"phd|doctorate|postdoc|post-doc|"
    r"new\s*grad|new-grad|"
    r"master'?s?|mba|"
    r"recruiter|recruiting|head\s+of|"
    r"people\s+strategy|inside\s+sales|"
    r"early\s+career(?!\s+(engineer|developer|intern))"
    r")\b",
    re.IGNORECASE,
)

TERM_PATTERNS = [
    (re.compile(r"summer\s*20(\d{2})", re.I), "Summer 20{}"),
    (re.compile(r"fall\s*20(\d{2})", re.I), "Fall 20{}"),
    (re.compile(r"winter\s*20(\d{2})", re.I), "Winter 20{}"),
    (re.compile(r"spring\s*20(\d{2})", re.I), "Spring 20{}"),
    (re.compile(r"20(\d{2})\s+intern", re.I), "20{}"),
]


def is_intern_role(title: str) -> bool:
    if EXCLUDE_PATTERN.search(title):
        return False
    return bool(INCLUDE_PATTERN.search(title))


def extract_terms(title: str) -> list[str]:
    terms = []
    for pattern, template in TERM_PATTERNS:
        match = pattern.search(title)
        if match:
            terms.append(template.format(match.group(1)))
    if not terms:
        terms.append("Unknown")
    return terms


def make_listing_id(url: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def normalize_listing(
    *,
    company_name: str,
    title: str,
    url: str,
    locations: list[str],
    source: str,
    now: int,
) -> dict:
    return {
        "id": make_listing_id(url),
        "company_name": company_name,
        "company_url": "",
        "title": title.strip(),
        "url": url,
        "locations": locations or ["Unknown"],
        "terms": extract_terms(title),
        "active": True,
        "is_visible": True,
        "source": source,
        "date_posted": now,
        "date_updated": now,
    }
