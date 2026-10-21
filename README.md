# 🎯 Career Radar v4: Direct ATS Multi-Source Pipeline & Intelligence Hub

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-WAL%20Mode-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Chrome Extension Bridge](https://img.shields.io/badge/Companion-Chrome%20Extension-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)](https://developer.chrome.com/docs/extensions/)
[![Status](https://img.shields.io/badge/Status-Production%20Active-brightgreen?style=for-the-badge)](#)

A high-performance, direct-source ATS aggregator and executive career intelligence workstation. Built to bypass stale, low-signal public job boards by scraping directly from primary applicant tracking systems (**Greenhouse**, **Lever**, **Ashby**, **Workday**, and **Amazon Direct**). Features automated executive role classification, fit scoring, application telemetry, and an autonomous split-screen companion pipeline for tailored resume generation.

---

## 🖥️ Command Center Interface

![Career Radar Command Center UI](../portfolio-assets/career_radar_ui.png)

*The Career Radar v4 Executive Command Center: Live multi-hub metrics, category filter pills, direct ATS source badges, executive fit scoring, and 1-click Cater Resume companion triggers.*

---

## ⚡ Core Capabilities

- **Primary ATS Ingestion Engines:**
  - **Greenhouse & Lever Direct Scrapers:** High-frequency REST polling across curated target tech rosters.
  - **Ashby API Ingestion:** Direct GraphQL/REST query layer extracting rich compensation data and exact hiring team requirements.
  - **Workday Search Aggregator:** Automated session handling for complex enterprise portals.
  - **Amazon Direct Ingestion:** Deep crawling with structured extraction of Basic vs. Preferred qualifications and core leadership principles.
- **Deterministic Role Taxonomy:** Categorizes inbound postings into high-precision tracks:
  - *AI / LLM Product Management*
  - *Technical Program Management (TPM / Infra / Hardware)*
  - *Business Operations & Strategy (BizOps)*
  - *Engineering Operations & Delivery*
  - *FinOps & Enterprise Systems*
- **Executive Fit Scoring:** Evaluates title seniority, technical keywords, and compensation bands against custom candidate profile parameters.
- **Bi-Directional Chrome Extension Bridge:**
  - One-click **"Cater Resume"** trigger in the UI communicates with the companion Chrome extension.
  - Automatically manages OS split-screen docking (80% ATS source, 20% Gemini sidecar).
  - Streams parsed JD text directly into Gemini Gems for real-time resume synthesis and auto-triggers print-ready PDF generation.
- **Local-First Architecture:** Zero external tracking dependencies, utilizing SQLite in WAL mode for microsecond response times and rock-solid privacy.

---

## 🏗️ Architecture & Data Pipeline

```
                                  +-----------------------------+
                                  | Primary Enterprise Sources  |
                                  | (Greenhouse, Lever, Ashby,  |
                                  |   Workday, Amazon Direct)   |
                                  +--------------+--------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  |     Scraper / Ingestion     |
                                  |   (scrapers/pipeline.py)    |
                                  +--------------+--------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  |  Taxonomy & Scoring Engine  |
                                  |   (taxonomy.py, scoring.py) |
                                  +--------------+--------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  | SQLite Storage (WAL Mode)   |
                                  |       (jobs_v4.db)          |
                                  +--------------+--------------+
                                                 |
                         +-----------------------+-----------------------+
                         |                                               |
                         v                                               v
            +--------------------------+                   +---------------------------+
            | FastAPI Backend Service  |                   | Browser Extension Bridge  |
            |   (REST API on :8050)    |                   | (Job Copilot for Gemini)  |
            +------------+-------------+                   +-------------+-------------+
                         |                                               |
                         v                                               v
            +--------------------------+                   +---------------------------+
            | Responsive Web Dashboard | <===============> | Side-by-Side Split Screen |
            | (Vanilla JS + CSS Grid)  |  "Cater Resume"   |  (Gemini Gem AI Sidecar)  |
            +--------------------------+                   +---------------------------+
```

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Uvicorn, Requests, Pydantic |
| **Database** | SQLite3 with Write-Ahead Logging (WAL) |
| **Frontend** | Vanilla JavaScript (ES6+), HTML5, CSS Grid / Flexbox |
| **Companion Extension** | Chrome Manifest V3, WebExtensions Messaging API |
| **AI Integration** | Google Gemini Gem sidecar with automated clipboard & window orchestration |

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11+
- Virtual environment tool (`venv` or `uv`)

### 2. Installation
```bash
# Clone the repository
git clone git@github.com:Jspaun-00/Careerradar.git
cd Careerradar

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the sample environment file and configure your local settings:
```bash
cp .env.example .env
```

Ensure your `.env` contains:
```ini
HOST=127.0.0.1
PORT=8050
ENV=production
GEMINI_GEM_URL=https://gemini.google.com/gem/your-gem-id
```

### 4. Running the Application
```bash
# Start the FastAPI server
python3 app.py
```
Open your browser to:
```
http://127.0.0.1:8050
```

### 5. Running Ingestion Scrapers
To execute an on-demand scrape across all configured company rosters:
```bash
python3 scrapers/run_all.py
```

---

## 📡 REST API Overview

- `GET /api/jobs`: Returns filtered, scored job listings with pagination and category breakdown.
- `GET /api/stats`: Dashboard summary counts (total jobs, active categories, 24h delta).
- `POST /api/jobs/{id}/archive`: Mark a listing as reviewed or hidden.
- `GET /api/jobs/{id}`: Detailed metadata including un-truncated qualification requirements.

---

## 🔒 Security & Privacy

- **Fully Anonymized:** All private candidate credentials, API keys, and personal identifiers are loaded strictly via environment variables or git-ignored sidecars.
- **Local Storage:** All ingested roles, historical matches, and application statuses stay on your machine.
