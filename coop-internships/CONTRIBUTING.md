# Contributing

## Submit a new listing

1. Open a [Co-op Listing Submission](../../issues/new/choose) issue
2. Fill in company, title, URL, and **US or Canada location**
3. A maintainer adds the `approved` label
4. GitHub Action adds it to `listings.json`, regenerates the boards, and closes the issue

**Note:** Only US and Canada locations are accepted. Closed applications, and anything added more than 30 days ago, are removed on the next sync.

## Data source

- Internships: [Simplify Summer 2027](https://github.com/SimplifyJobs/Summer2027-Internships)
- Software new grad: [Simplify New-Grad Positions](https://github.com/SimplifyJobs/New-Grad-Positions)

Pages (newest first):

- Canada and the United States are separate pages
- Each country has **software internships**, **other internships**, and **software new grad**
- A role with locations in both countries is listed on both pages

Season/term columns are omitted — feed metadata is often wrong unless the title itself names a season.

## listings.json schema

```json
{
  "id": "uuid",
  "company_name": "Stripe",
  "title": "Software Engineer Intern - Summer 2026",
  "url": "https://...",
  "locations": ["San Francisco, CA"],
  "program": "cs",
  "track": "intern",
  "active": true,
  "is_visible": true,
  "source": "simplify",
  "date_posted": 1690430400,
  "date_updated": 1690430400
}
```

`program` is `"cs"` or `"other"`. `track` is `"intern"` or `"new_grad"`. Both are derived from the title and category.
