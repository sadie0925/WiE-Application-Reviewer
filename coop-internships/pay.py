"""Find pay in a job posting and show it per hour.

Works on any posting text (a description, or a whole careers page with its
embedded JSON). Looks for money written with a currency ($, US$, CA$, C$, USD,
CAD, £, GBP, €, EUR), then:

- a range ("$20 - $50", "between $116,400 and $175,200", "$45k to $60k"),
- a min / max pair stored apart ("minimum": "$7,650/month", "maximum": "$12,667/month"),
- or a single fixed amount ("$25/hour", "CA$5,000 per month").

Yearly, monthly and weekly pay is converted at 40 hours a week (2,080 hours a year).
"""

from __future__ import annotations

import json
import re

HOURS = {"hr": 1.0, "wk": 40.0, "mo": 2080.0 / 12, "yr": 2080.0}

_SYMBOL = {
    "$": "$", "US$": "$", "USD": "$",
    "CA$": "CA$", "C$": "CA$", "CAD": "CA$",
    "£": "£", "GBP": "£",
    "€": "€", "EUR": "€",
}

_NUMBER = r"(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?P<dec>\.\d{1,2})?(?:\s?(?P<k>[kK])(?![a-zA-Z]))?"
# Currency before the number: "$25", "CA$ 5,000", "USD 120,000"
_PRE = re.compile(r"(?P<cur>\b(?:USD|CAD)\s?\$|CA\$|C\$|US\$|\$|£|€|\b(?:USD|CAD|GBP|EUR)\b)\s?" + _NUMBER)
# Currency after the number: "120,000 CAD", "45 USD"
_POST = re.compile(r"(?<![\d.,$£€])" + _NUMBER + r"\s?(?P<cur>USD|CAD|GBP|EUR)\b")

# Words right after an amount that say what period it is.
_PERIOD_AFTER = (
    ("hr", re.compile(r"^[\s\\/\"',.:)\]]{0,4}(?:(?:/|per|an?|each|by\s+the)\s*)?(?:hour|hr|h)\b|^[\s,)\]]{0,3}hourly", re.I)),
    ("wk", re.compile(r"^[\s\\/\"',.:)\]]{0,4}(?:(?:/|per|a)\s*)?(?:week|wk)\b|^[\s,)\]]{0,3}weekly", re.I)),
    ("mo", re.compile(r"^[\s\\/\"',.:)\]]{0,4}(?:(?:/|per|a)\s*)?(?:month|mo|mth)\b|^[\s,)\]]{0,3}monthly", re.I)),
    ("yr", re.compile(r"^[\s\\/\"',.:)\]]{0,4}(?:(?:/|per|an?)\s*)?(?:year|yr|annum|annual)\b|^[\s,)\]]{0,3}(?:annually|yearly|annual)", re.I)),
)
# Period words just before an amount ("Hourly rate: $25", "Annual salary range: ...").
_PERIOD_BEFORE = (
    ("hr", re.compile(r"\b(hourly|per\s+hour|an\s+hour)\b[^$£€]{0,40}$", re.I)),
    ("wk", re.compile(r"\b(weekly|per\s+week)\b[^$£€]{0,40}$", re.I)),
    ("mo", re.compile(r"\b(monthly|per\s+month)\b[^$£€]{0,40}$", re.I)),
    ("yr", re.compile(r"\b(annual(?:ly|ized)?|yearly|per\s+year|salary)\b[^$£€]{0,40}$", re.I)),
)
_PAY_WORDS = re.compile(
    r"\b(pay|paid|compensation|salary|salaries|wage|rate|earn|base|range|hourly|annual|"
    r"remuneration|stipend|minimum|maximum|min|max)\b",
    re.I,
)
# Money that is not pay.
_NOT_PAY_BEFORE = re.compile(
    r"(sign(?:ing|-on)\s+bonus|bonus\s+of|relocation|reimburs\w*|raised|funding|revenue|valuation|"
    r"401\(?k|budget|tuition|housing|gift\s*cards?|prize|award|grant|fees?|"
    r"discount|donat\w*|credits?|allowance|per\s+diem|investment|series\s+[a-d]|"
    r"\bunder\b|\bover\b|trillion|portfolio)[^$£€.]{0,40}$",
    re.I,
)
_NOT_PAY_AFTER = re.compile(r"^\s?(?:million|billion|trillion|mil\b|bn\b|m\b|\+?\s*employees|%)", re.I)
# Application-form questions ("My desired salary: Under $65,000 / $65,000 - $70,000 ...").
_FORM_CONTEXT = re.compile(r"desired|salary\s+expectations?|expected\s+salary|what\s+are\s+your|select\s+one", re.I)
_BARE_LOW = re.compile(r"(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?P<dec>\.\d{1,2})?\s*(?:-|–|—|to)\s*$")
# "$86.500,00" / "$140.000" written with dots for thousands.
_EU_NUMBER = re.compile(r"([$£€]\s?)(\d{1,3}(?:\.\d{3})+)(?:,(\d{2}))?(?![\d.])")
_CURRENCY_WORD = re.compile(r"\b(?:USD|CAD|GBP|EUR)\b", re.I)
# Second number of a range without its own currency sign: "$26.00-29.00", "$45k-60k".
_BARE_HIGH = re.compile(r"(?:\s*/\s*[A-Za-z]+)?\s*(?:-|–|—|to)\s*(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?P<dec>\.\d{1,2})?(?:\s?(?P<k>[kK])(?![a-zA-Z]))?")
_RANGE_GAP = re.compile(r"^\s*(?:-|–|—|~|to|and|through|up\s+to)\s*$", re.I)
_MAX_GAP = re.compile(r"max(?:imum)?|upper|high(?:est)?|to\b", re.I)

# schema.org JobPosting salary, which many careers sites embed for search engines.
_BASE_SALARY = re.compile(r'"baseSalary"\s*:\s*\{(?P<body>.{0,600}?)\}\s*\}', re.S)


def _symbol(raw: str) -> str:
    code = raw.strip().upper().replace(" ", "")
    if code in _SYMBOL:
        return _SYMBOL[code]
    return _SYMBOL.get(code.rstrip("$"), "$")  # "USD$", "CAD$"


def _tokens(text: str) -> list[dict]:
    found = []
    for regex in (_PRE, _POST):
        for match in regex.finditer(text):
            value = float(match.group("num").replace(",", "") + (match.group("dec") or ""))
            if match.group("k"):
                value *= 1000
            cur = _symbol(match.group("cur"))
            end = match.end()
            code_after = re.match(r"\s?(USD|CAD|GBP|EUR)\b", text[end: end + 5])
            if code_after:
                cur, end = _SYMBOL[code_after.group(1)], end + code_after.end()
            found.append({
                "start": match.start(),
                "end": end,
                "value": value,
                "cur": cur,
                "k": bool(match.group("k")),
            })
    found.sort(key=lambda item: item["start"])
    # Drop overlaps ("USD $120,000" matches twice).
    tokens: list[dict] = []
    for token in found:
        if tokens and token["start"] < tokens[-1]["end"]:
            continue
        tokens.append(token)
    return tokens


def _period_after(text: str, pos: int) -> str:
    after = text[pos: pos + 40]
    for period, regex in _PERIOD_AFTER:
        if regex.search(after):
            return period
    return ""


def _period_before(text: str, pos: int) -> str:
    before = text[max(0, pos - 80): pos]
    for period, regex in _PERIOD_BEFORE:
        if regex.search(before):
            return period
    return ""


def _guess_period(low: float, high: float) -> str:
    if high <= 300:
        return "hr"
    if low >= 15000:
        return "yr"
    return ""


def hourly_label(low: float, high: float, period: str, symbol: str = "$") -> str:
    """'$25/hr', '$20–$50/hr', or a converted salary like '$56–$84/hr'."""
    hours = HOURS[period]
    low, high = sorted((low / hours, high / hours))

    def fmt(value: float) -> str:
        if period != "hr" or abs(value - round(value)) < 0.005:
            return f"{symbol}{round(value):,}"
        return f"{symbol}{value:,.2f}"

    if fmt(low) == fmt(high):
        return f"{fmt(low)}/hr"
    return f"{fmt(low)}–{fmt(high)}/hr"


def _sane(low: float, high: float, period: str) -> bool:
    if low <= 0 or high <= 0:  # "$0.00 - $0.00" placeholders
        return False
    hourly_high = high / HOURS[period]
    hourly_low = low / HOURS[period]
    return 7 <= hourly_low and hourly_high <= 400


def _structured_salary(text: str) -> str:
    """schema.org baseSalary: {"currency":"USD","value":{"minValue":..,"maxValue":..,"unitText":"YEAR"}}."""
    for match in _BASE_SALARY.finditer(text):
        body = match.group("body").replace('\\"', '"')
        def num(key: str) -> float | None:
            found = re.search(rf'"{key}"\s*:\s*"?(\d[\d,]*(?:\.\d+)?)', body)
            return float(found.group(1).replace(",", "")) if found else None
        low = num("minValue") or num("value")
        high = num("maxValue") or low
        if not low:
            continue
        unit = re.search(r'"unitText"\s*:\s*"(\w+)"', body)
        period = {"HOUR": "hr", "WEEK": "wk", "MONTH": "mo", "YEAR": "yr"}.get(
            (unit.group(1) if unit else "").upper(), ""
        ) or _guess_period(low, high)
        currency = re.search(r'"currency"\s*:\s*"(\w{3})"', body)
        symbol = _SYMBOL.get((currency.group(1) if currency else "USD").upper(), "$")
        if period and _sane(low, high, period):
            return hourly_label(low, high, period, symbol)
    return ""


def pay_from_text(text: str) -> str:
    """Hourly pay label from posting text, or '' when no pay is stated."""
    if not text:
        return ""
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    text = text.replace("\\/", "/").replace("\\n", " ").replace("&nbsp;", " ").replace("\u00a0", " ")
    text = re.sub(r"<[^<>]{0,200}>", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = _EU_NUMBER.sub(lambda m: m.group(1) + m.group(2).replace(".", ",") + ("." + m.group(3) if m.group(3) else ""), text)
    structured = _structured_salary(text)
    if structured:
        return structured

    tokens = _tokens(text)
    candidates = []
    index = 0
    while index < len(tokens):
        found = _amount_at(text, tokens, index)
        if found is None:
            index += 1
            continue
        if found[0] == "skip":
            index = found[1]
            continue
        low, high, period, cur, next_index, end = found
        start = tokens[index]["start"]
        far = candidates and start - candidates[0][4] > 1500
        # Tiered pay listed together (by level, school year, or degree):
        # "Undergraduate: $25/hr Graduate: $30/hr PhD: $35/hr" -> $25–$35/hr.
        while next_index < len(tokens) and tokens[next_index]["start"] - end <= 120:
            more = _amount_at(text, tokens, next_index, inherit=period)
            if more is None or more[0] == "skip":
                break
            m_low, m_high, m_period, m_cur, m_next, m_end = more
            if m_period != period or not _same_currency(m_cur, cur) or m_high > high * 3 or m_low < low / 3:
                break
            low, high = min(low, m_low), max(high, m_high)
            next_index, end = m_next, m_end
        if far:
            # Far from the first stated pay: only a range that agrees with it counts.
            first_low = candidates[0][0]
            if low != high and period == candidates[0][2] and low <= first_low <= high:
                candidates.append((low, high, period, cur, start))
                break
            index = next_index
            continue
        candidates.append((low, high, period, cur, start))
        if low != high:
            break  # a stated range is the answer
        index = next_index
    if not candidates:
        return ""
    # Prefer the first range; otherwise the first single amount.
    low, high, period, cur, _start = next((c for c in candidates if c[0] != c[1]), candidates[0])
    return hourly_label(low, high, period, cur)


def _same_currency(a: str, b: str) -> bool:
    # "CAD $101,000 - $151,000": the second "$" is the same Canadian dollar.
    return a == b or {a, b} == {"$", "CA$"}


def _amount_at(text: str, tokens: list[dict], index: int, inherit: str = ""):
    """Pay starting at tokens[index]: (low, high, period, currency, next_index, end) or None."""
    first = tokens[index]
    before = text[max(0, first["start"] - 120): first["start"]]
    if _FORM_CONTEXT.search(before) or _NOT_PAY_BEFORE.search(before[-35:]) or _NOT_PAY_AFTER.search(text[first["end"]: first["end"] + 12]):
        return None
    low = high = first["value"]
    end = first["end"]
    next_index = index + 1
    paired = False
    bare_low = _BARE_LOW.search(text[max(0, first["start"] - 30): first["start"]])
    if bare_low:
        value = float(bare_low.group("num").replace(",", "") + (bare_low.group("dec") or ""))
        if first["value"] / 5 <= value < first["value"]:
            low, paired = value, True  # "127,100.00 - 185,000.00 USD annually"
    bare = None if paired else _BARE_HIGH.match(text, first["end"])
    if bare and bare.group("num"):
        value = float(bare.group("num").replace(",", "") + (bare.group("dec") or ""))
        if bare.group("k") or (first["value"] >= 1000 and value < 1000 and re.search(r"[kK]", text[first["end"] - 1: first["end"]])):
            value *= 1000
        if first["value"] < value <= first["value"] * 5:
            high, end, paired = value, bare.end(), True
    if not paired and index + 1 < len(tokens):
        second = tokens[index + 1]
        gap = text[first["end"]: second["start"]]
        plain_gap = _CURRENCY_WORD.sub("", gap)
        first_period = _period_after(text, first["end"])
        joined = (
            (len(plain_gap) <= 12 and _RANGE_GAP.match(plain_gap))
            # "$X/Yr.", "$Y/Yr." side by side: a min and a max with the same unit.
            or (len(gap) <= 40 and first_period and first_period == _period_after(text, second["end"]))
            or (len(gap) <= 90 and _MAX_GAP.search(gap))
        )
        if joined and second.get("k") and not first.get("k") and first["value"] < 1000 <= second["value"]:
            low = high = first["value"] * 1000
        if joined and _same_currency(second["cur"], first["cur"]) and low < second["value"] <= low * 5:
            high, end = second["value"], second["end"]
            next_index = index + 2
            paired = True
    period = _period_after(text, end) or _period_after(text, first["end"]) or _period_before(text, first["start"])
    if not period:
        if inherit and _guess_period(low, high) in {inherit, ""}:
            period = inherit
        elif not _PAY_WORDS.search(before):
            return None
        else:
            period = _guess_period(low, high)
            if not period:
                return None
    if not _sane(low, high, period):
        # A "salary" hint can be wrong ("salary range ... $20.00 - $45.00" is hourly).
        guess = _guess_period(low, high)
        if guess and guess != period and _sane(low, high, guess):
            period = guess
        else:
            return ("skip", next_index) if paired else None
    return low, high, period, first["cur"], next_index, end


def pay_from_fields(low, high, period_code, currency: str | None) -> str:
    """Simplify's structured salary fields."""
    try:
        low = float(low or high or 0)
        high = float(high or low or 0)
    except (TypeError, ValueError):
        return ""
    if low <= 0:
        return ""
    period = {1: "hr", 2: "wk", 3: "mo", 4: "yr"}.get(period_code) or _guess_period(low, high)
    if not period or not _sane(low, high, period):
        return ""
    return hourly_label(low, high, period, _SYMBOL.get((currency or "USD").upper(), "$"))


if __name__ == "__main__":  # quick self-check
    cases = {
        "The base pay range for this role is between $116,400 and $175,200, and your base pay": "$56–$84/hr",
        "Expected Compensation $20.00 - $50.00 + benefits": "$20–$50/hr",
        '"compensation_amount_minimum":"$7,650\\/month","compensation_amount_maximum":"$12,667\\/month"': "$44–$73/hr",
        '"tags2":["USD $150,500.00/Yr."],"tags3":["USD $215,000.00/Yr."]': "$72–$103/hr",
        "Minimum: $45,000 Maximum: $60,000 annually": "$22–$29/hr",
        "Pay: $25/hour. Signing bonus up to $5,000": "$25/hr",
        "Hourly rate: CA$32": "CA$32/hr",
        "Salary: 65,000 CAD per year": "CA$31/hr",
        "£28,000 - £32,000 per annum": "£13–£15/hr",
        "The company raised $50 million in funding": "",
        "Base Pay Range: $0.00 - $0.00 Per Hour": "",
        "Interns earn $6,000 per month": "$35/hr",
        '"baseSalary":{"@type":"MonetaryAmount","currency":"USD","value":{"@type":"QuantitativeValue","minValue":120000,"maxValue":150000,"unitText":"YEAR"}}}': "$58–$72/hr",
        "$45k to $60k per year": "$22–$29/hr",
        "Combined Salary Range USD $85,807.00 - USD $95,193.00 /Yr.": "$41–$46/hr",
        "The hourly pay range for this position is $26.00-29.00, plus overtime": "$26–$29/hr",
        "Undergraduate Students: $25/hr Graduate Students: $30/hr PhD Students: $35/hr": "$25–$35/hr",
        "The hourly rate for this job in Pasadena depending on education level (undergrad) is $21.00 as a freshman, $22.50 as a sophomore, $24.50 as a junior, and $26.50 as a Senior": "$21–$26.50/hr",
        "Pay Range: Level 1: $125,000.00 - $160,000.00 Level 2: $145,000.00 - $195,000.00 Your actual level": "$60–$94/hr",
        "Hiring Salary Range of: Undergraduate: $25–$30 per hour. Graduate: $35–$40 per hour.": "$25–$40/hr",
        "My desired annual salary for this position is: Under $65,000 $65,000 - $70,000 $70,000 - $75,000": "",
        "annual throughput of approximately $3.2 trillion. Pay: $30/hour": "$30/hr",
        '"has_bonus":false,"has_equity":false,"compensation_amount_minimum":"$7,650/month","compensation_amount_maximum":"$12,667/month"': "$44–$73/hr",
        "USA, CA, Cupertino - 127,100.00 - 185,000.00 USD annually": "$61–$89/hr",
        "Annual Salary = $105,000 ------ Full Time Salary Range: $80,000.00 - $115,000.00 In addition": "$38–$55/hr",
        "The US base salary range for this full-time position is $20.00 - $45.00 Our salary ranges": "$20–$45/hr",
        "Tech-1 (Freshman), Starting Salary: $19.51 per hour \\u003cbr /\\u003e\\u003cbr /\\u003eTech-2 (Sophomore), Starting Salary: $21.46 per hour\\u003cbr /\\u003e Tech (Graduate Student), Starting Salary: $32.13 per hour": "$19.51–$32.13/hr",
        "CAN base pay range per year: CAD $101,000 - $151,000. Location": "CA$49–CA$73/hr",
        "the estimated salary range for this position is $86,500.00 to $ 134,400.00 USD per year": "$42–$65/hr",
        "the estimated salary range for this position is $86.500,00 to $ 134.400,00 USD per year": "$42–$65/hr",
        "Full-Time Salary Range: $111,000 to $140.000 The salary range": "$53–$67/hr",
        "Salary: $75-$90k, commensurate with experience": "$36–$43/hr",
        "the base salary for this co-op role is $19 CAD per hour for 37.5 hours per week": "CA$19/hr",
        "Starting Rate: $19.50/Hourly - 22.00/Hourly (Based on locale": "$19.50–$22/hr",
        '"compensationTierSummary":"$30 per hour" ' + "x" * 1600 + " What we offer $20-$30/hr Real ownership": "$20–$30/hr",
    }
    bad = 0
    for text, want in cases.items():
        got = pay_from_text(text)
        ok = got == want
        bad += not ok
        print("ok " if ok else "BAD", repr(got), "want", repr(want), "|", text[:60])
    raise SystemExit(bad)
