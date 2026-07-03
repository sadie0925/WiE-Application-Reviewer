# Contributing

## Submit a new listing

1. Open a [New Listing Submission](../../issues/new/choose) issue
2. Fill in company, title, URL, location, and term
3. A maintainer reviews and adds the `approved` label
4. GitHub Action adds it to `listings.json` and closes the issue

## Add a company to the scraper

Edit `companies.json` and open a PR. Supported platforms:

| Platform | How to find slug |
|----------|-----------------|
| Greenhouse | `boards.greenhouse.io/{slug}` |
| Lever | `jobs.lever.co/{slug}` |
| Ashby | `jobs.ashbyhq.com/{slug}` |
| Workday | `{company}.wd5.myworkdayjobs.com` — needs `workday_host` + `workday_site` |

## listings.json schema

```json
{
  "id": "uuid-based-on-url",
  "company_name": "Stripe",
  "title": "Software Engineer Intern - Summer 2026",
  "url": "https://boards.greenhouse.io/stripe/jobs/123",
  "locations": ["San Francisco, CA"],
  "terms": ["Summer 2026"],
  "active": true,
  "is_visible": true,
  "source": "scraper:greenhouse:stripe",
  "date_posted": 1690430400,
  "date_updated": 1690430400
}
```
