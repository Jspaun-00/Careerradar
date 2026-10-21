import asyncio
import sqlite3
import re
import bs4
import httpx
from scrapers import clean_and_prune_description, HEADERS

async def enrich_all_short_descriptions():
    conn = sqlite3.connect('career_radar_v4.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT dedup_key, company, title, url, ats, length(description) 
        FROM jobs 
        WHERE length(description) < 2000
        ORDER BY company ASC
    """)
    rows = cursor.fetchall()
    print(f"Total jobs to inspect/enrich: {len(rows)}")

    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
        enriched_count = 0
        for dedup_key, company, title, url, ats, current_len in rows:
            new_desc = None
            try:
                # 1. Amazon Jobs
                if company == 'Amazon' or 'amazon.jobs' in (url or ''):
                    # Check for job ID
                    job_id_match = re.search(r'/jobs/(\d+)', url or '')
                    if job_id_match:
                        job_id = job_id_match.group(1)
                        r = await client.get("https://www.amazon.jobs/en/search.json", params={"base_query": job_id})
                        if r.status_code == 200:
                            data = r.json()
                            for j in data.get("jobs", []):
                                if str(j.get("id_icims")) == str(job_id) or str(j.get("id")) == str(job_id):
                                    combined = f"{j.get('description', '')}\n\nBASIC QUALIFICATIONS:\n{j.get('basic_qualifications', '')}\n\nPREFERRED QUALIFICATIONS:\n{j.get('preferred_qualifications', '')}".strip()
                                    new_desc = clean_and_prune_description(combined)
                                    break
                    
                    # If not found by ID or no ID in URL, search by title keywords
                    if not new_desc and title:
                        # Clean title to 3-5 alphanumeric words
                        words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', ' ', title).split() if len(w) > 2]
                        query = ' '.join(words[:4])
                        r = await client.get("https://www.amazon.jobs/en/search.json", params={"base_query": query, "result_limit": 5})
                        if r.status_code == 200:
                            for j in r.json().get("jobs", []):
                                cand_title = j.get("title", "")
                                # Check if closely matching
                                if any(w.lower() in cand_title.lower() for w in words[:3]):
                                    combined = f"{j.get('description', '')}\n\nBASIC QUALIFICATIONS:\n{j.get('basic_qualifications', '')}\n\nPREFERRED QUALIFICATIONS:\n{j.get('preferred_qualifications', '')}".strip()
                                    new_desc = clean_and_prune_description(combined)
                                    break

                # 2. LinkedIn Guest API
                elif url and 'linkedin.com/jobs/view/' in url:
                    li_id_match = re.search(r'view/(\d+)', url)
                    if li_id_match:
                        li_id = li_id_match.group(1)
                        li_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{li_id}"
                        r = await client.get(li_url)
                        if r.status_code == 200:
                            soup = bs4.BeautifulSoup(r.text, 'html.parser')
                            desc_el = soup.find('div', class_='show-more-less-html__markup')
                            if desc_el:
                                new_desc = clean_and_prune_description(str(desc_el))

                # 3. Lever API
                elif url and 'jobs.lever.co/' in url:
                    lever_match = re.search(r'jobs\.lever\.co/([^/]+)/([a-f0-9\-]+)', url)
                    if lever_match:
                        site, post_id = lever_match.groups()
                        r = await client.get(f"https://api.lever.co/v0/postings/{site}/{post_id}")
                        if r.status_code == 200:
                            data = r.json()
                            lever_parts = [data.get("description", "") or data.get("descriptionPlain", "")]
                            for lst in data.get("lists", []):
                                lever_parts.append(f"{lst.get('text', '')}:\n{lst.get('content', '')}")
                            new_desc = clean_and_prune_description("\n\n".join(lever_parts))

                # 4. Greenhouse (Direct or board)
                elif url and ('boards.greenhouse.io' in url or 'grnh.se' in url):
                    r = await client.get(url)
                    if r.status_code == 200:
                        soup = bs4.BeautifulSoup(r.text, 'html.parser')
                        content = soup.find('div', id='content') or soup.find('div', class_='body') or soup.find('div', id='job-description')
                        if content:
                            new_desc = clean_and_prune_description(str(content))

                # 5. Workday CXS API
                elif url and '.myworkdayjobs.com/' in url:
                    wd_match = re.search(r'https://([^.]+)\.wd(\d+)\.myworkdayjobs\.com/en-US/([^/]+)/job/(.+)', url)
                    if wd_match:
                        tenant, wd_num, site, path = wd_match.groups()
                        cxs_url = f"https://{tenant}.wd{wd_num}.myworkdayjobs.com/wday/cxs/{tenant.lower()}/{site}/job/{path}"
                        r = await client.get(cxs_url)
                        if r.status_code == 200:
                            desc_html = r.json().get('jobPostingInfo', {}).get('jobDescription', '')
                            if desc_html:
                                new_desc = clean_and_prune_description(desc_html)

                # 6. Fallback HTML fetch
                if not new_desc and url:
                    try:
                        r = await client.get(url)
                        if r.status_code == 200:
                            soup = bs4.BeautifulSoup(r.text, 'html.parser')
                            for sel in ['article', '[data-automation="jobDescription"]', '.job-description', '#job-description', '.description', 'main']:
                                el = soup.select_one(sel)
                                if el and len(el.text) > 400:
                                    cleaned = clean_and_prune_description(str(el))
                                    if len(cleaned) > current_len:
                                        new_desc = cleaned
                                        break
                    except Exception:
                        pass

                if new_desc and len(new_desc) > max(current_len, 400):
                    cursor.execute("UPDATE jobs SET description = ? WHERE dedup_key = ?", (new_desc, dedup_key))
                    conn.commit()
                    enriched_count += 1
                    print(f"[{enriched_count}] Enriched: {company} - {title} (Old: {current_len} -> New: {len(new_desc)})")
                else:
                    # If we couldn't get a longer one, leave it
                    pass

            except Exception as e:
                # print(f"Error for {title}: {e}")
                pass

    print(f"\nCompleted! Enriched {enriched_count} jobs.")
    conn.close()

if __name__ == '__main__':
    asyncio.run(enrich_all_short_descriptions())

