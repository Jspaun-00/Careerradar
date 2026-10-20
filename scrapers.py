import asyncio
import httpx
import re
import urllib.parse
import bs4
from datetime import datetime, timezone
from jobspy import scrape_jobs
from jobspy.indeed import Indeed
from taxonomy import ATS_TARGETS
from evaluator import strict_location_match, enrich_job

# Patch JobSpy's Indeed processor to preserve the exact millisecond timestamp from dateOnIndeed
_orig_indeed_process = Indeed._process_job
def _enhanced_indeed_process(self, job_dict):
    post = _orig_indeed_process(self, job_dict)
    raw_ms = job_dict.get("dateOnIndeed")
    if raw_ms:
        post.date_posted = datetime.fromtimestamp(raw_ms / 1000.0, timezone.utc)
    return post
Indeed._process_job = _enhanced_indeed_process

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}

def matches_role_keywords(title: str, config: dict) -> bool:
    if not title:
        return False
    t = title.lower()
    if any(ex.lower() in t for ex in config.get("exclude_keywords", [])):
        return False
    return any(rk.lower() in t for rk in config.get("role_keywords", []))

# 1. AMAZON DIRECT JSON API (With Strict Metro Verification & Granular Timestamps)
async def scrape_amazon_direct(client: httpx.AsyncClient, profile: dict, config: dict):
    jobs = []
    city_query = profile["primary_location"]
    for term in ["Program Manager", "Process Improvement", "Operational Excellence"]:
        url = "https://www.amazon.jobs/en/search.json"
        params = {"base_query": term, "loc_query": city_query, "sort": "recent", "result_limit": 35}
        try:
            r = await client.get(url, params=params, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                for j in r.json().get("jobs", []):
                    title = j.get("title", "")
                    loc = j.get("normalized_location") or j.get("location", "")
                    if matches_role_keywords(title, config) and strict_location_match(loc, profile, config.get("include_remote_us", False)):
                        raw_date = j.get("updated_time") or j.get("posted_date")
                        jobs.append({
                            "profile_id": profile["id"],
                            "profile_name": profile["name"],
                            "company": "Amazon",
                            "title": title,
                            "location": loc,
                            "url": f"https://www.amazon.jobs{j.get('job_path', '')}",
                            "ats": "Amazon Direct",
                            "description": f"{j.get('description_short', '')} {j.get('basic_qualifications', '')}",
                            "posted_raw": raw_date
                        })
        except Exception:
            pass
    return jobs

# 2. EIGHTFOLD AI DIRECT CONNECTOR (Microsoft, Starbucks & Qualcomm)
async def scrape_eightfold_direct(client: httpx.AsyncClient, ef_site: dict, profile: dict, config: dict):
    jobs = []
    city_query = profile["primary_location"]
    for term in ["Program Manager", "Process Improvement"]:
        url = f"https://{ef_site['host']}/api/apply/v2/jobs"
        params = {
            "domain": ef_site["domain"],
            "query": term,
            "location": city_query,
            "start": 0,
            "num": 25,
            "sort_by": "timestamp"
        }
        try:
            r = await client.get(url, params=params, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                positions = r.json().get("positions", [])
                for pos in positions:
                    title = pos.get("name", "")
                    loc_list = pos.get("locations", [pos.get("location", "")])
                    loc_str = ", ".join(loc_list) if isinstance(loc_list, list) else str(loc_list)
                    if matches_role_keywords(title, config) and strict_location_match(loc_str, profile, config.get("include_remote_us", False)):
                        pos_id = pos.get("id", "")
                        canonical_url = pos.get("canonicalPositionUrl") or f"https://{ef_site['host']}/careers/job/{pos_id}?domain={ef_site['domain']}"
                        raw_date = pos.get("t_create") or pos.get("creationDate") or pos.get("postedDate")
                        jobs.append({
                            "profile_id": profile["id"],
                            "profile_name": profile["name"],
                            "company": ef_site["name"],
                            "title": title,
                            "location": loc_str,
                            "url": canonical_url,
                            "ats": f"{ef_site['name']} Direct (Eightfold)",
                            "description": pos.get("job_description", ""),
                            "posted_raw": raw_date
                        })
        except Exception:
            pass
    return jobs

# 3. WORKDAY DIRECT CXS CONNECTOR (Boeing, Salesforce/Tableau, Nike, Dell, Intel, etc.)
async def scrape_workday(client: httpx.AsyncClient, wd: dict, profiles: list, config: dict):
    endpoint = f"https://{wd['host']}/wday/cxs/{wd['tenant']}/{wd['site']}/jobs"
    wd_headers = {
        **HEADERS,
        "Content-Type": "application/json",
        "Origin": f"https://{wd['host']}",
        "Referer": f"https://{wd['host']}/en-US/{wd['site']}"
    }
    jobs = []
    lookback_days = max(1, int(config.get("lookback_hours", 24) / 24))

    for term in ["Program Manager", "Process Improvement", "Continuous Improvement"]:
        payload = {"appliedFacets": {}, "limit": 25, "offset": 0, "searchText": term}
        try:
            r = await client.post(endpoint, json=payload, headers=wd_headers, timeout=15)
            if r.status_code == 200:
                for j in r.json().get("jobPostings", []):
                    posted_str = (j.get("postedOn") or "").lower()
                    # Recency check
                    is_recent = ("today" in posted_str) or ("yesterday" in posted_str)
                    if not is_recent and lookback_days >= 3:
                        for d in range(1, min(lookback_days + 1, 15)):
                            if f"{d} day" in posted_str:
                                is_recent = True
                                break
                    if not is_recent:
                        continue

                    title = j.get("title", "")
                    loc = j.get("locationsText", "")
                    if not matches_role_keywords(title, config):
                        continue
                    for p in profiles:
                        if strict_location_match(loc, p, config.get("include_remote_us", False)):
                            jobs.append({
                                "profile_id": p["id"],
                                "profile_name": p["name"],
                                "company": wd["name"],
                                "title": title,
                                "location": loc,
                                "url": f"https://{wd['host']}/en-US/{wd['site']}{j.get('externalPath', '')}",
                                "ats": "Workday Direct",
                                "description": " ".join(j.get("bulletFields", []) or []),
                                "posted_raw": j.get("postedOn") or "Posted Today"
                            })
        except Exception:
            pass
    return jobs

# 4. GREENHOUSE DIRECT CONNECTOR (Stripe, Cloudflare, Figma, Datadog, Brex, GitLab, Pinterest, etc.)
async def scrape_greenhouse(client: httpx.AsyncClient, slug: str, profiles: list, config: dict):
    try:
        r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", timeout=15)
        if r.status_code != 200:
            return []
        jobs = []
        for j in r.json().get("jobs", []):
            title = j.get("title", "")
            if not matches_role_keywords(title, config):
                continue
            loc = j.get("location", {}).get("name", "")
            for p in profiles:
                if strict_location_match(loc, p, config.get("include_remote_us", False)):
                    raw_date = j.get("first_published") or j.get("updated_at")
                    jobs.append({
                        "profile_id": p["id"],
                        "profile_name": p["name"],
                        "company": j.get("company_name") or slug.capitalize(),
                        "title": title,
                        "location": loc,
                        "url": j.get("absolute_url"),
                        "ats": "Greenhouse Direct",
                        "description": j.get("content", ""),
                        "posted_raw": raw_date
                    })
        return jobs
    except Exception:
        return []

# 5. LEVER DIRECT CONNECTOR (Palantir, Shield AI, etc.)
async def scrape_lever(client: httpx.AsyncClient, slug: str, profiles: list, config: dict):
    try:
        r = await client.get(f"https://api.lever.co/v0/postings/{slug}?mode=json", timeout=15)
        if r.status_code != 200:
            return []
        jobs = []
        for j in r.json():
            title = j.get("text", "")
            if not matches_role_keywords(title, config):
                continue
            loc = j.get("categories", {}).get("location", "")
            for p in profiles:
                if strict_location_match(loc, p, config.get("include_remote_us", False)):
                    jobs.append({
                        "profile_id": p["id"],
                        "profile_name": p["name"],
                        "company": slug.capitalize(),
                        "title": title,
                        "location": loc,
                        "url": j.get("hostedUrl"),
                        "ats": "Lever Direct",
                        "description": j.get("descriptionPlain", ""),
                        "salary_min": j.get("salaryRange", {}).get("min"),
                        "salary_max": j.get("salaryRange", {}).get("max"),
                        "posted_raw": j.get("createdAt")
                    })
        return jobs
    except Exception:
        return []

# 6. ASHBY DIRECT CONNECTOR (Ramp, Notion, Linear, Vanta, Replit)
async def scrape_ashby(client: httpx.AsyncClient, slug: str, profiles: list, config: dict):
    try:
        r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=15)
        if r.status_code != 200:
            return []
        jobs = []
        for j in r.json().get("jobs", []):
            title = j.get("title", "")
            if not matches_role_keywords(title, config):
                continue
            loc = j.get("location", "")
            sec_locs = [s.get("location", "") for s in j.get("secondaryLocations", []) if isinstance(s, dict)]
            combined_loc = f"{loc}, {', '.join(sec_locs)}" if sec_locs else loc
            for p in profiles:
                if strict_location_match(combined_loc, p, config.get("include_remote_us", False)):
                    jobs.append({
                        "profile_id": p["id"],
                        "profile_name": p["name"],
                        "company": slug.capitalize(),
                        "title": title,
                        "location": loc or p["primary_location"],
                        "url": j.get("jobUrl") or j.get("applyUrl"),
                        "ats": "Ashby Direct",
                        "description": j.get("descriptionPlain", "") or j.get("descriptionHtml", ""),
                        "posted_raw": j.get("publishedAt")
                    })
        return jobs
    except Exception:
        return []

# 7. TARGETED ENTERPRISE, LINKEDIN & INDEED SWEEPS (NO Glassdoor; Captures Apple, Meta, Google, MSFT, Boeing, etc.)
def _run_hub_jobspy_sweep(profile: dict, config: dict):
    lookback = int(config.get("lookback_hours", 24))
    hub_companies = ATS_TARGETS["targeted_company_sweeps"].get(profile["id"], [])
    
    # Priority query list
    if profile.get("id") == "us_national":
        all_queries = [
            '("Program Manager" OR "Operations Program Manager")',
            '("Process Improvement" OR "Operational Excellence" OR "Continuous Improvement")',
            '("BizOps" OR "Strategy & Operations" OR "Technical Program Manager")'
        ]
        results_per_query = 35
    else:
        anchor_queries = [f'"{c}" Program Manager' for c in hub_companies[:4]]
        broad_queries = [
            '("Program Manager" OR "Process Improvement" OR "Operational Excellence")',
            '("Business Operations" OR "Technical Program Manager")'
        ]
        all_queries = anchor_queries + broad_queries
        results_per_query = 25
    
    collected = []
    seen_keys = set()
    active_sites = ["indeed", "linkedin"]

    for q in all_queries:
        try:
            # Query LinkedIn guest search directly for exact post times (e.g. "3 hours ago", "9 hours ago")
            li_time_map = {}
            try:
                li_url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={urllib.parse.quote(q)}&location={urllib.parse.quote(profile['primary_location'])}"
                li_resp = httpx.get(li_url, headers=HEADERS, timeout=8)
                if li_resp.status_code == 200:
                    li_soup = bs4.BeautifulSoup(li_resp.text, "html.parser")
                    for li_elem in li_soup.find_all("li"):
                        link_tag = li_elem.find("a", class_="base-card__full-link")
                        time_tag = li_elem.find("time")
                        if link_tag and time_tag and "href" in link_tag.attrs:
                            job_key = link_tag["href"].split("?")[0].rstrip("/").split("-")[-1]
                            li_time_map[job_key] = time_tag.get_text(strip=True)
            except Exception:
                pass

            df = scrape_jobs(
                site_name=active_sites,
                search_term=q,
                location=profile["primary_location"],
                distance=35 if profile.get("id") != "us_national" else 100,
                results_wanted=results_per_query,
                hours_old=lookback,
                country_indeed="USA"
            )
            for _, row in df.iterrows():
                title = str(row.get("title", ""))
                company = str(row.get("company", "Unknown"))
                loc = str(row.get("location", profile["primary_location"]))
                dedup_sig = f"{company.lower()}:{title.lower()}:{loc.lower()}"
                if dedup_sig in seen_keys:
                    continue
                seen_keys.add(dedup_sig)

                if matches_role_keywords(title, config) and strict_location_match(loc, profile, config.get("include_remote_us", False)):
                    site_str = str(row.get("site", "Board")).strip().lower()
                    posted_val = row.get("date_posted")
                    if "linkedin" in site_str:
                        ats_label = "LinkedIn"
                        job_url = str(row.get("job_url_direct") or row.get("job_url") or "")
                        # Match exact relative time if found in LinkedIn guest search
                        url_key = job_url.split("?")[0].rstrip("/").split("-")[-1]
                        if url_key in li_time_map:
                            posted_val = li_time_map[url_key]
                    elif "indeed" in site_str:
                        ats_label = "Indeed"
                    else:
                        ats_label = site_str.capitalize()

                    collected.append({
                        "profile_id": profile["id"],
                        "profile_name": profile["name"],
                        "company": company,
                        "title": title,
                        "location": loc,
                        "url": str(row.get("job_url_direct") or row.get("job_url")),
                        "ats": ats_label,
                        "description": str(row.get("description", "")),
                        "salary_min": row.get("min_amount"),
                        "salary_max": row.get("max_amount"),
                        "posted_raw": posted_val
                    })
        except Exception:
            pass
    return collected

# MASTER PIPELINE
async def run_all_scrapers(config: dict, target_profile_id: str = "ALL"):
    active_profiles = [
        p for p in config.get("profiles", [])
        if (target_profile_id == "ALL" and p.get("enabled", True)) or p.get("id") == target_profile_id
    ]
    tasks, task_names = [], []

    limits = httpx.Limits(max_connections=250, max_keepalive_connections=50)
    async with httpx.AsyncClient(follow_redirects=True, limits=limits) as client:
        for p in active_profiles:
            tasks.append(scrape_amazon_direct(client, p, config))
            task_names.append(f"Amazon ({p['id']})")
            for ef in ATS_TARGETS["eightfold"]:
                tasks.append(scrape_eightfold_direct(client, ef, p, config))
                task_names.append(f"{ef['name']} ({p['id']})")

        if active_profiles:
            for slug in ATS_TARGETS.get("greenhouse", []):
                tasks.append(scrape_greenhouse(client, slug, active_profiles, config))
                task_names.append(f"GH:{slug}")
            for slug in ATS_TARGETS.get("lever", []):
                tasks.append(scrape_lever(client, slug, active_profiles, config))
                task_names.append(f"LV:{slug}")
            for slug in ATS_TARGETS.get("ashby", []):
                tasks.append(scrape_ashby(client, slug, active_profiles, config))
                task_names.append(f"Ashby:{slug}")
            for wd in ATS_TARGETS.get("workday", []):
                tasks.append(scrape_workday(client, wd, active_profiles, config))
                task_names.append(f"WD:{wd['name']}")

        for p in active_profiles:
            tasks.append(asyncio.to_thread(_run_hub_jobspy_sweep, p, config))
            task_names.append(f"FAANG/Enterprise LinkedIn+Indeed ({p['id']})")

        settled = await asyncio.gather(*tasks, return_exceptions=True)

    enriched_jobs, health_log = [], []
    enabled_tracks = set(config.get("enabled_tracks", ["Non-Tech / Business PM", "Process Improvement & Ops", "Technical PM (TPM)"]))

    for name, res in zip(task_names, settled):
        if isinstance(res, Exception):
            health_log.append({"source": name, "status": "WARN", "count": 0, "error": str(res)[:50]})
        else:
            health_log.append({"source": name, "status": "OK", "count": len(res)})
            for raw in res:
                job = enrich_job(raw, config)
                if job["role_track"] in enabled_tracks:
                    enriched_jobs.append(job)

    return enriched_jobs, health_log
