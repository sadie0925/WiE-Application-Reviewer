from __future__ import annotations

import time

import requests

from scrapers.base import is_intern_role, normalize_listing

LEVER_API = "https://api.lever.co/v0/postings/{slug}"


def scrape_lever(company: dict) -> list[dict]:
    slug = company["slug"]
    name = company["name"]
    now = int(time.time())
    source = f"scraper:lever:{slug}"

    response = requests.get(
        LEVER_API.format(slug=slug),
        params={"mode": "json"},
        timeout=30,
    )
    response.raise_for_status()
    jobs = response.json()
    if not isinstance(jobs, list):
        return []

    listings = []
    for job in jobs:
        title = job.get("text", "")
        if not is_intern_role(title):
            continue

        locations = []
        if job.get("categories", {}).get("location"):
            locations = [job["categories"]["location"]]
        if job.get("workplaceType"):
            locations.append(job["workplaceType"])

        listings.append(
            normalize_listing(
                company_name=name,
                title=title,
                url=job.get("hostedUrl", job.get("applyUrl", "")),
                locations=locations,
                source=source,
                now=now,
            )
        )

    return listings
