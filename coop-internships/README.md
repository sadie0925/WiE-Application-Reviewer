# Co-op & Internship Listings (US & Canada)

Undergraduate co-op and internship postings in **United States & Canada**, synced automatically from the [Simplify Jobs](https://github.com/SimplifyJobs/Summer2026-Internships) community feed (plus optional ATS scrapers / community submissions).

Boards are separate pages, newest first. Closed applications, and anything added more than 30 days ago, are removed. Internships come from the Simplify Summer feed. Software new-grad roles come from Simplify's New-Grad Positions feed on their own pages, with master's/PhD-only rows dropped. Term and work-authorization cells stay blank unless the posting or feed says them.

The checker runs every 5 minutes, which is the fastest GitHub will schedule it. A new posting shows up on the next check after it appears in the feed. Hackathons are on their own page: Waterloo clubs and committees first, then other Canada and US events. A hackathon is removed as soon as its deadline passes, which is separate from the 30-day job rule. Early undergrad programs (fellows, insight, and first-year programs) are on their own page and are removed as soon as the application deadline passes.

## Quick start

```bash
cd coop-internships
python3 -m pip install requests
python3 main.py sync      # fetch feed + regenerate README (1 HTTP request)
python3 main.py readme    # regenerate README only
```

<!-- LISTINGS:START -->

**3039 open listings** · newest first · Updated 2026-11-12 15:25 ET

Internships come from the Simplify Summer feed. Software new-grad roles come from Simplify's New-Grad Positions feed. Internships are removed when closed or after **30 days**. Active new-grad rows stay until the feed marks them closed. Master's/PhD-only new-grad rows are left off. Roles in both countries show up on both pages.

| Board | Open |
| ----- | ---- |
| [Canada — Software internships](boards/canada-software.md) | 148 |
| [United States — Software internships](boards/us-software.md) | 881 |
| [Canada — Other internships](boards/canada-other.md) | 54 |
| [United States — Other internships](boards/us-other.md) | 313 |
| [Canada — Software new grad](boards/canada-new-grad.md) | 151 |
| [United States — Software new grad](boards/us-new-grad.md) | 1539 |
| [Hackathons and innovation challenges](boards/hackathons.md) | 21 (2 Waterloo first) |
| [Early undergrad programs](boards/programs.md) | 3 |

<!-- LISTINGS:END -->
