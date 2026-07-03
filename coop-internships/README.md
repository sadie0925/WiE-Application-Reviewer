# Co-op & Internship Listings

Automated co-op and internship postings scraped from company career pages (Greenhouse, Lever, Ashby, Workday). Simplify-style pipeline: scrape → `listings.json` → auto-generated README.

## Quick start

```bash
cd coop-internships
pip install requests
python main.py scrape    # fetch listings from company ATS APIs
python main.py readme    # regenerate README.md table
```

## Architecture

```
Company career pages (Greenhouse, Lever, Ashby, Workday)
        ↓  (hourly GitHub Action)
    Python scrapers
        ↓
   listings.json  ← also updated by approved GitHub Issues
        ↓  (on every listings.json commit)
   README.md auto-regenerated
```

## What's included

| Piece | Status |
|-------|--------|
| Greenhouse scraper | ✅ |
| Lever scraper | ✅ |
| Ashby scraper | ✅ |
| Workday scraper | ✅ (basic) |
| `listings.json` storage | ✅ |
| README auto-generation | ✅ |
| Hourly scrape GitHub Action | ✅ |
| Community issue submissions | ✅ (`approved` label triggers Action) |

## Add a company

Edit `companies.json`:

```json
{ "name": "Stripe", "platform": "greenhouse", "slug": "stripe" }
{ "name": "Anthropic", "platform": "lever", "slug": "anthropic" }
{ "name": "Ramp", "platform": "ashby", "slug": "ramp" }
```

For Workday, also add `workday_host` and `workday_site`.

## Deploy to GitHub

This folder is a **standalone repo** — push it to its own GitHub repository (not the WiE applicant reviewer):

```bash
cd coop-internships
git init
git add .
git commit -m "Initial co-op listings scraper"
gh repo create uwwiegithub/coop-internships --public --source=. --push
```

GitHub Actions will run automatically once pushed.

## vs Simplify

Simplify has a proprietary backend scraping thousands of companies hourly. This repo scrapes a **curated list** you control in `companies.json`. You can grow the list over time — each platform's API is free and doesn't need browser scraping for Greenhouse/Lever/Ashby.

## Contributing

Open an issue with a new posting. A maintainer adds the `approved` label and it gets added automatically.

See [CONTRIBUTING.md](./CONTRIBUTING.md).

<!-- LISTINGS:START -->

**54 active listings** · 62 inactive · Last updated: 2026-07-03 04:43 UTC

## Active Listings

| Company | Role | Location | Term | Posted | Apply |
| ------- | ---- | -------- | ---- | ------ | ----- |
| Notion | Software Engineer Intern (Fall 2026) | San Francisco, California, Remote | Fall 2026 | 2026-07-03 | [Apply](https://jobs.ashbyhq.com/notion/5b15697c-fa91-4511-9482-c98a6ff29f90) |
| Nvidia | Applied Physics and Electro-Optics Intern | JR2018120 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Israel-Yokneam/Applied-Physics-and-Electro-Optics-Intern_JR2018120) |
| Nvidia | Applied Research Intern, NLP - Fall 2026 | JR2010488 | Fall 2026 | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Applied-Research-Intern--NLP---Fall-2026_JR2010488) |
| Nvidia | Applied Research Intern, Robotics - 2026 | JR2020124 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Shanghai/Applied-Research-Intern--Robotics---2026_JR2020124) |
| Nvidia | Arch Intern, CPU - 2026 | JR2019197 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Shanghai/Arch-Intern--CPU---2026_JR2019197) |
| Nvidia | DGX Cloud Kubernetes Runtime Intern - Fall 2026 | JR2009619 | Fall 2026 | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/DGX-Cloud-Kubernetes-Runtime-Intern---Fall-2026_JR2009619) |
| Nvidia | Java Engineering Intern - Fall 2026 | JR2019769 | Fall 2026 | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Java-Engineering-Intern---Fall-2026_JR2019769) |
| Nvidia | Machine Learning Intern - 2026 | JR2016444 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Hong-Kong-STP/Machine-Learning-Intern---2026_JR2016444) |
| Nvidia | Machine Learning Intern - 2026 | JR2016445 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Hong-Kong-STP/Machine-Learning-Intern---2026_JR2016445) |
| Nvidia | Machine Learning Intern - AI Agents Conversational AI | JR2017298 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Hong-Kong-STP/Machine-Learning-Intern---AI-Agents-Conversational-AI_JR2017298) |
| Nvidia | Machine Learning Intern - Multimodal Models Generative AI | JR2017296 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/Hong-Kong-STP/Machine-Learning-Intern---Multimodal-Models-Generative-AI_JR2017296-1) |
| Nvidia | Machine Learning Intern, Humanoid Robotics - 2026 | JR2018845 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Shanghai/Machine-Learning-Intern--Humanoid-Robotics---2026_JR2018845) |
| Nvidia | Quantum Error Correction Research Scientist Intern - Fall 2026 | JR2018628 | Fall 2026 | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Remote/Quantum-Error-Correction-Research-Scientist-Intern---Fall-2026_JR2018628) |
| Nvidia | Quantum Research Scientist Intern - Fall 2026 | JR2018244 | Fall 2026 | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Remote/Quantum-Research-Scientist-Intern---Fall-2026_JR2018244) |
| Nvidia | Robotics Software Intern, Deployment and Humanoids - 2026 | JR2019641 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Shanghai/Robotics-Software-Intern--Deployment-and-Humanoids---2026_JR2019641) |
| Nvidia | Software Engineering Intern, JAX - Fall 2026 | JR2009745 | Fall 2026 | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/Software-Engineering-Intern--JAX---Fall-2026_JR2009745) |
| Nvidia | Software Engineering Intern, Neural Reconstruction - Summer 2026 | JR2010555 | Summer 2026 | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Shanghai/Software-Engineering-Intern--Neural-Reconstruction---Summer-2026_JR2010555-1) |
| Nvidia | Software Engineering Intern, Robot Learning Platform - 2026 | JR2018629 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Shanghai/Software-Engineering-Intern--Robot-Learning-Platform---2026_JR2018629) |
| Nvidia | Solution Architecture Intern, AI in Industry - 2026 | JR2014186 | Unknown | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Beijing/Solution-Architecture-Intern--AI-in-Industry---2026_JR2014186) |
| Nvidia | System Software Engineering Intern, Systems Infrastructure - Summer 2026 | JR2006824 | Summer 2026 | 2026-07-03 | [Apply](https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Shanghai/System-Software-Engineer-Intern--Systems-Infrastructure--Summer-2026_JR2006824) |
| Palantir | Deployment Strategist, Internship | Paris, France, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/774cf5c9-bf6a-4d77-bf60-d50ef1beb1a0) |
| Palantir | Deployment Strategist, Internship - US Government | Honolulu, HI, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/a49d4181-a289-435a-b581-7f5af0497c8e) |
| Palantir | Forward Deployed Software Engineer, Internship | Paris, France, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/1b6f1d82-d459-4dea-8bc2-8d2ffe6f881a) |
| Palantir | Forward Deployed Software Engineer, Internship - AUS Government | Sydney, Australia, hybrid | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/395a4483-fc3d-4b77-a500-501923fd0976) |
| Palantir | Forward Deployed Software Engineer, Internship - Commercial | New York, NY, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/4d29249a-d7e8-4c39-880d-3b35d7b2f6f6) |
| Palantir | Forward Deployed Software Engineer, Internship - Commercial | Chicago, IL, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/d5486403-c050-4920-b2e0-91b69b61ebb2) |
| Palantir | Forward Deployed Software Engineer, Internship - Defense Tech | Washington, D.C., onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/cccfe1bd-f15b-4fe5-b044-c793e7961c1b) |
| Palantir | Forward Deployed Software Engineer, Internship - France | New York, NY, hybrid | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/ac0dc094-2480-43c2-8495-26ade227ff4f) |
| Palantir | Forward Deployed Software Engineer, Internship - Intel | Washington, D.C., onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/9e40d77f-b07c-437b-98e7-def9b0184d89) |
| Palantir | Forward Deployed Software Engineer, Internship - Poland | New York, NY, hybrid | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/d582cd84-14fd-4aa3-b413-15982d286bd9) |
| Palantir | Forward Deployed Software Engineer, Internship - US Government | Honolulu, HI, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/315f695d-04d1-4a9a-848e-cb2bec7a997e) |
| Palantir | Forward Deployed Software Engineer, Internship - US Government | New York, NY, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/e0010393-c300-446f-bf67-fa2ef067f16f) |
| Palantir | Forward Deployed Software Engineer, Internship - US Government | Washington, D.C., onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/e6ff8bf2-135e-474d-ad37-24f490ae1dd2) |
| Palantir | Privacy and Civil Liberties Software Engineer, Internship | New York, NY, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/09846827-b931-4a9f-bd64-c3bb8860187b) |
| Palantir | Software Engineer, Internship | Denver, CO, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/373eb939-6f57-4836-8479-be79a5e07249) |
| Palantir | Software Engineer, Internship | New York, NY, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/7d69cf8a-06fd-4f05-bd84-27149db29c4d) |
| Palantir | Software Engineer, Internship | Washington, D.C., onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/bdcfb29f-4f27-42de-933f-7f83a359b9f0) |
| Palantir | Software Engineer, Internship | Palo Alto, CA, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/e27af7ab-41fc-40c9-b31d-02c6cb1c505c) |
| Palantir | Software Engineer, Internship - Defense Tech | New York, NY, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/8bcf4f33-0a79-4248-bbfd-49ac4be9dd8e) |
| Palantir | Software Engineer, Internship - Defense Tech | Palo Alto, CA, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/a483f41b-0da9-42ea-8ed6-cbf6eb93cc6d) |
| Palantir | Software Engineer, Internship - Defense Tech | Washington, D.C., onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/f17e98d0-046a-4e6e-9d65-ed0b12dd0ff7) |
| Palantir | Software Engineer, Internship - Infrastructure | New York, NY, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/b229baac-494b-4a0d-9a13-2e38806e06f3) |
| Palantir | Software Engineer, Internship - Infrastructure | Palo Alto, CA, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/f221738b-e97c-4ce3-a12a-17ada2b855e4) |
| Palantir | Software Engineer, Internship - Production Infrastructure | Seattle, WA, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/373367a9-3160-49d8-b7af-2efec062fad1) |
| Palantir | Software Engineer, Internship - Production Infrastructure | New York, NY, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/37964982-9b4c-471e-a1d8-fb8f45d7f116) |
| Palantir | Software Engineer, Internship - Production Infrastructure | Washington, D.C., onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/3ab9e715-1ea9-4c6c-ad50-7340eac14e86) |
| Palantir | Year at Palantir - Forward Deployed Software Engineer, Internship - Commercial | Chicago, IL, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/75cc1c09-8ebd-44c8-b3bc-d122cd1fecb3) |
| Palantir | Year at Palantir - Forward Deployed Software Engineer, Internship - Commercial | New York, NY, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/e6789b17-62fb-4226-a079-f8c17ff19e2d) |
| Palantir | Year at Palantir - Forward Deployed Software Engineer, Internship - USG | Washington, D.C., onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/5c4c65c5-77da-4d36-856c-4ade87631019) |
| Palantir | Year at Palantir - Forward Deployed Software Engineer, Internship - USG | New York, NY, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/5c7bb70c-83ea-43e7-8055-0c8f319f4333) |
| Palantir | Year at Palantir - Software Engineer, Internship | New York, NY, onsite | Unknown | 2026-07-03 | [Apply](https://jobs.lever.co/palantir/655f9937-a4ce-4e7d-80e2-a6659af07329) |
| Ramp | Software Engineer Internship, Android | New York, NY (HQ), Remote | Unknown | 2026-07-03 | [Apply](https://jobs.ashbyhq.com/ramp/67fadb77-43d8-4449-954b-d4cf2c6d3b8b) |
| Stripe | Software Engineer, Intern | Sydney, Australia | Unknown | 2026-07-03 | [Apply](https://stripe.com/jobs/search?gh_jid=7532256) |
| Test Co | Software Intern - Summer 2026 | Toronto, ON | Summer 2026 | 2026-07-03 | [Apply](https://example.com/job/123) |

<!-- LISTINGS:END -->
