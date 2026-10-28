# Co-op & Internship Listings (US & Canada)

Undergraduate co-op and internship postings in **United States & Canada**, synced automatically from the [Simplify Jobs](https://github.com/SimplifyJobs/Summer2026-Internships) community feed (plus optional ATS scrapers / community submissions).

Boards are separate pages, newest first. Closed applications, and anything added more than 30 days ago, are removed. Software new-grad titles from this same feed go on their own pages. Term and work-authorization cells stay blank unless the posting itself says them.

The checker runs every 5 minutes, which is the fastest GitHub will schedule it. A new posting shows up on the next check after it appears in the feed. Hackathons are on their own page: Waterloo clubs and committees first, then other Canada and US events. A hackathon is removed as soon as its deadline passes, which is separate from the 30-day job rule.

## Quick start

```bash
cd coop-internships
python3 -m pip install requests
python3 main.py sync      # fetch feed + regenerate README (1 HTTP request)
python3 main.py readme    # regenerate README only
```

<!-- LISTINGS:START -->

**1402 open listings** · newest first · Updated 2026-10-27 20:20 ET

Same Simplify feed as before. A listing is removed when the application is closed, or when it was added more than **30 days** ago. Roles in both countries show up on both pages.

| Board | Open |
| ----- | ---- |
| [Canada — Software internships](boards/canada-software.md) | 177 |
| [United States — Software internships](boards/us-software.md) | 870 |
| [Canada — Other internships](boards/canada-other.md) | 47 |
| [United States — Other internships](boards/us-other.md) | 322 |
| [Canada — Software new grad](boards/canada-new-grad.md) | 0 |
| [United States — Software new grad](boards/us-new-grad.md) | 1 |
| [Hackathons and innovation challenges](boards/hackathons.md) | 59 (3 Waterloo first) |

<!-- LISTINGS:END -->
