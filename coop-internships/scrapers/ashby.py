from __future__ import annotations

import time

import requests

from scrapers.base import is_intern_role, normalize_listing

ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def scrape_ashby(company: dict) -> list[dict]:
    slug = company["slug"]
    name = company["name"]
    now = int(time.time())
    source = f"scraper:ashby:{slug}"

    response = requests.get(ASHBY_API.format(slug=slug), timeout=30)
    response.raise_for_status()
    jobs = response.json().get("jobs", [])

    listings = []
    for job in jobs:
        title = job.get("title", "")
        if not is_intern_role(title):
            continue

        location = job.get("location", "")
        locations = [location] if location else []
        if job.get("isRemote"):
            locations.append("Remote")

        listings.append(
            normalize_listing(
                company_name=name,
                title=title,
                url=job.get("jobUrl", ""),
                locations=locations,
                source=source,
                now=now,
            )
        )

    return listings
