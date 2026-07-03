"""ATS platform scrapers for co-op and internship listings."""

from __future__ import annotations

from scrapers.ashby import scrape_ashby
from scrapers.greenhouse import scrape_greenhouse
from scrapers.lever import scrape_lever
from scrapers.workday import scrape_workday

SCRAPERS = {
    "greenhouse": scrape_greenhouse,
    "lever": scrape_lever,
    "ashby": scrape_ashby,
    "workday": scrape_workday,
}


def scrape_company(company: dict) -> list[dict]:
    platform = company["platform"]
    scraper = SCRAPERS.get(platform)
    if not scraper:
        raise ValueError(f"Unknown platform: {platform}")
    return scraper(company)
