# Career Radar v4.0: Master Agent Build Specification

## Executive Summary & Architecture

Career Radar v4.0 is a unified, standalone local web application (`http://127.0.0.1:8050`) engineered for high-leverage job intelligence. Based on forensic audits of real-world ATS snapshots, v4.0 expands geographic coverage, eliminates cross-metro bleed, introduces direct enterprise API connectors (Eightfold AI and Workday CXS), establishes strict 3-way track classification, and incorporates a Knowledge Bank STAR-story matching engine.

### Key Architectural Upgrades in v4.0

1. **Multi-Hub Ingestion (4 High-Growth Tech Metros)**:
   - **Seattle, WA Metro**: Seattle, Bellevue, Redmond, Kirkland, Renton, Bothell, Kent, Everett, Tacoma.
   - **Denver / Boulder, CO Metro**: Denver, Boulder, Englewood, Broomfield, Westminster, Littleton, Lakewood, Aurora, Centennial, Greenwood Village.
   - **Portland, OR Metro**: Portland, Beaverton, Hillsboro, Tigard, Lake Oswego, Vancouver (WA side of Portland metro).
   - **Austin, TX Metro**: Austin, Round Rock, Cedar Park, Westlake, Bee Cave, Pflugerville, Buda, Kyle, Georgetown.

2. **Strict Location Filtering & False-Positive Elimination**:
   - Explicit `forbidden_tokens` per hub to eliminate geographic false positives:
     - Seattle excludes Washington D.C., WA state in Australia (Sydney, Perth), Washington PA, etc.
     - Austin excludes Dallas, Houston, San Antonio, Fort Worth, etc.
     - Denver excludes Colorado Springs, Fort Collins, etc.
     - Portland excludes Portland ME, etc.
   - Word-boundary token checking ensures clean matching without substring collisions.

3. **Expanded Direct ATS & Enterprise Ingestion**:
   - **Eightfold AI Connector**: Microsoft (`careers.microsoft.com`), Starbucks, Qualcomm unauthenticated search endpoints.
   - **Workday CXS Direct APIs**: Native JSON integration for Salesforce/Tableau, Boeing, Blue Origin, Nordstrom, T-Mobile, Expedia, F5, DaVita, VF Corp, Intel, Columbia Sportswear, Daimler Truck, Dell.
   - **Amazon Direct**: Native unauthenticated API (`amazon.jobs/en/search.json`).
   - **Greenhouse & Lever Direct**: Zero-auth REST boards for Stripe, Anduril, Shield AI, Palantir, Scale AI, Toast, Affirm, etc.
   - **Ashby HQ**: Direct public posting API.
   - **JobSpy & Targeted Company Sweeps**: Configurable multi-day lookback for Apple, Meta, Google, Costco, Nike, and market discovery.

4. **Strict 3-Way Mutually Exclusive Track Classification**:
   - `Technical PM (TPM)`: Quarantines hardware, ASIC, avionics, firmware, software, cloud infrastructure, ML/AI, distributed systems, and RF engineering roles.
   - `Process Improvement & Ops`: Lean Six Sigma, Continuous Improvement, Kaizen, Operational Excellence, Supply Chain optimization, Industrial Engineering.
   - `Non-Tech / Business PM`: Strategic program management, business operations, project management, GTM, corporate strategy.
   - *Hardware/Engineering TPM roles are strictly prevented from leaking into Non-Tech / Business PM filters.*

5. **Knowledge Bank STAR-Story Competency Matcher & Education Fit Engine**:
   - **Candidate Educational Profile**: The candidate holds a **Master of Business Administration (MBA) in Business**. The candidate does **not** possess an undergraduate bachelor's degree in engineering, computer science, or technical STEM fields.
   - **Technical Degree Disqualification Rule**: Roles whose Basic / Minimum Qualifications strictly mandate a Bachelor's in Engineering, Computer Science, or technical disciplines (without business degree equivalence) are **strictly disqualified from receiving a 100% Fit Score**.
   - **Penalties & Caps**:
     - *Rigid Engineering/CS Bachelor Requirement*: -35 pt deduction, hard cap at 65% max fit score, tagged `⚠️ Requires Eng/CS Degree (MBA Gap)`.
     - *Engineering/CS Degree with Practical Equiv Clause*: -20 pt deduction, hard cap at 72% max fit score, tagged `⚠️ Requires Eng/CS Degree (Equiv Exp Allowed)`.
     - *MBA / Business Preferred or Aligned*: +5 pt additive bonus (eligible for 100% match), tagged `🎓 MBA Preferred/Aligned`.
   - Extracts matched skill chips (e.g., Lean Six Sigma, Cross-Functional Leadership, Agile/Scrum, Roadmap Strategy, Root Cause Analysis).
   - Generates calibrated match scores (0–100) reflecting true candidate background fit.

6. **Canonical Company Registry with Sub-Brand Granularity**:
   - Normalizes corporate entities to clean canonical parent brands while preserving distinct sub-brand entities:
     - Amazon (Amazon Corporate, AWS / Amazon Web Services, Project Kuiper, Zoox).
     - Boeing (Commercial Airplanes, Defense, Space & Security, Global Services).
     - Alphabet (Google, Verily, Waymo).

7. **Flexible Timeframe Lookback & Desktop Launchers**:
   - On-demand lookback selector: 24h, 48h, 3 days, 7 days, 14 days.
   - One-click desktop launchers for macOS (`Launch_Career_Radar.command`) and Windows (`Launch_Career_Radar.bat`).

---

## Directory Structure

```text
career-radar-v3/
├── AGENT_BUILD_SPEC.md        # Master v4.0 architecture specification
├── Launch_Career_Radar.command# macOS double-click desktop launcher (chmod +x)
├── Launch_Career_Radar.bat    # Windows double-click desktop launcher
├── requirements.txt           # Python dependencies
├── app.py                     # FastAPI web server, APScheduler, lookback API
├── database.py                # SQLite schema (career_radar_v4.db) with sub-brands & matched skills
├── taxonomy.py                # 4 Hub profiles, Company Registry, Eightfold & Workday tenant registries
├── evaluator.py               # Strict location match, 3-way track classifier, Knowledge Bank matcher, salary parser
├── scrapers.py                # Direct connectors: Amazon, Eightfold, Workday, Greenhouse, Lever, Ashby, JobSpy
└── static/
    └── index.html             # Upgraded v4.0 command center UI with Knowledge Bank drawer & lookback controls
```

---

## Component Details

### 1. `taxonomy.py`
- Defines `SEARCH_PROFILES` for Seattle, Denver, Portland, and Austin with:
  - `city_tokens`: Hub-specific cities and suburbs.
  - `state_tokens`: State codes and names.
  - `forbidden_tokens`: Non-hub cities and false-positive terms.
- Defines `COMPANY_REGISTRY`: Canonical mapping with sub-brands and tier classifications (Tier 1 FAANG, Tier 2 Public Tech, Tier 3 AI & Unicorn, Tier 4 Enterprise & Aero, Tier 5 Discovery).
- Defines `EIGHTFOLD_TARGETS` (Microsoft, Starbucks, Qualcomm).
- Defines `WORKDAY_TARGETS` (Boeing, Blue Origin, Nordstrom, Salesforce, T-Mobile, Expedia, F5, DaVita, VF Corp, Intel, Columbia, Daimler, Dell).

### 2. `evaluator.py`
- `strict_location_match()`: Word-boundary validation against hub city tokens and forbidden lists.
- `classify_strict_3way_track()`: Multi-phase classification prioritizing TPM engineering quarantine before ops and business PM tagging.
- `compute_knowledge_bank_match()`: Compares job description against user STAR stories and competency keywords.
- `parse_salary()`: Extracts base compensation bands; falls back to Tier-based compensation benchmarks when unlisted.
- `enrich_job()`: Combines fit score, seniority detection, work mode tagging, and skill matching.

### 3. `scrapers.py`
- `scrape_amazon_direct()`: Direct JSON fetch from `amazon.jobs`.
- `scrape_eightfold_direct()`: Direct JSON fetch from Eightfold AI API.
- `scrape_workday()`: Direct JSON fetch from Workday CXS endpoints with multi-day lookback.
- `scrape_greenhouse_direct()` & `scrape_lever_direct()`: Fast public API sweeps.
- `scrape_jobspy_sync()`: Multi-board fallback (Indeed, Glassdoor, LinkedIn) with customizable lookback hours.

### 4. `database.py`
- Manages `career_radar_v4.db`.
- Schema includes `sub_brand`, `matched_skills`, `ats_source`, `status`, `notes`.
- Provides transactional updates, profile management, and Knowledge Bank persistence.

### 5. `app.py`
- FastAPI server listening on `http://127.0.0.1:8050`.
- Background scheduler triggering daily scans at configured morning hour.
- Supports `/api/run` with `lookback_hours` parameter (24, 48, 72, 168, 336).
- Endpoints for Knowledge Bank retrieval and updates (`/api/knowledge-bank`).

### 6. `static/index.html`
- Dark-mode responsive command center UI with Tailwind CSS and Lucide icons.
- Interactive lookback selector, Knowledge Bank drawer with STAR-story input, filter pills for 4 hubs and 3 tracks.
- Telemetry cards displaying total roles, Tier 1/2 count, 80+ fit score count, and compensation averages.
