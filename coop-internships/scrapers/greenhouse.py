from __future__ import annotations

import time

import requests

from scrapers.base import is_intern_role, normalize_listing

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def scrape_greenhouse(company: dict) -> list[dict]:
    slug = company["slug"]
    name = company["name"]
    now = int(time.time())
    source = f"scraper:greenhouse:{slug}"

    response = requests.get(
        GREENHOUSE_API.format(slug=slug),
        params={"content": "true"},
        timeout=30,
    )
    response.raise_for_status()
    jobs = response.json().get("jobs", [])

    listings = []
    for job in jobs:
        title = job.get("title", "")
        if not is_intern_role(title):
            continue

        locations = [loc.get("name", "") for loc in job.get("locations", []) if loc.get("name")]
        if not locations and job.get("location"):
            locations = [job["location"]["name"]]

        listings.append(
            normalize_listing(
                company_name=name,
                title=title,
                url=job.get("absolute_url", ""),
                locations=locations,
                source=source,
                now=now,
            )
        )

    return listings
