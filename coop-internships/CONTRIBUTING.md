# Contributing

## Submit a new listing

1. Open a [Co-op Listing Submission](../../issues/new/choose) issue
2. Fill in company, title, URL, **US or Canada location**, and term
3. A maintainer adds the `approved` label
4. GitHub Action adds it to `listings.json` and closes the issue

**Note:** Only US and Canada locations are accepted.

## Data source

Primary data comes from the [Simplify Jobs](https://github.com/SimplifyJobs/Summer2026-Internships) public feed, filtered for:
- Undergraduate intern/co-op roles
- United States & Canada locations only
- Excludes PhD, new grad, recruiter roles

## listings.json schema

```json
{
  "id": "uuid",
  "company_name": "Stripe",
  "title": "Software Engineer Intern - Summer 2026",
  "url": "https://...",
  "locations": ["San Francisco, CA"],
  "terms": ["Summer 2026"],
  "active": true,
  "is_visible": true,
  "source": "simplify",
  "date_posted": 1690430400,
  "date_updated": 1690430400
}
```
