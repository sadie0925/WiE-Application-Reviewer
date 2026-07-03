from __future__ import annotations

import time

import requests

from scrapers.base import is_intern_role, normalize_listing

WORKDAY_API = (
    "https://{host}/wday/cxs/{tenant}/{site}/jobs"
)


def scrape_workday(company: dict) -> list[dict]:
    host = company["workday_host"]
    site = company["workday_site"]
    tenant = host.split(".")[0]
    name = company["name"]
    now = int(time.time())
    source = f"scraper:workday:{tenant}"

    listings = []
    offset = 0
    page_size = 20

    while True:
        response = requests.post(
            WORKDAY_API.format(host=host, tenant=tenant, site=site),
            json={
                "appliedFacets": {},
                "limit": page_size,
                "offset": offset,
                "searchText": "intern",
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobPostings", [])

        for job in jobs:
            title = job.get("title", "")
            if not is_intern_role(title):
                continue

            bullet_fields = job.get("bulletFields", [])
            location = bullet_fields[0] if bullet_fields else "Unknown"
            external_path = job.get("externalPath", "")
            site = company["workday_site"]
            if external_path:
                url = f"https://{host}/en-US/{site}{external_path}"
            else:
                url = ""

            listings.append(
                normalize_listing(
                    company_name=name,
                    title=title,
                    url=url,
                    locations=[location],
                    source=source,
                    now=now,
                )
            )

        total = data.get("total", 0)
        offset += page_size
        if offset >= total or not jobs:
            break

    return listings
