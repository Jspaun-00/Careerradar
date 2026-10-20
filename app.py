import time
import webbrowser
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import init_db, get_config, save_config, upsert_jobs, list_jobs, update_job_status, save_meta, get_meta
from scrapers import run_all_scrapers

scheduler = AsyncIOScheduler()
PORT = 8050

async def execute_snapshot(trigger_source: str = "Scheduled 10:00 AM", profile_id: str = "ALL"):
    start = time.time()
    cfg = get_config()
    jobs, health = await run_all_scrapers(cfg, profile_id)
    new_count = upsert_jobs(jobs)
    meta = {
        "last_run": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        "trigger": trigger_source,
        "duration_sec": round(time.time() - start, 1),
        "new_count": new_count,
        "total_scanned": len(jobs),
        "health": health
    }
    save_meta(meta)

    # Automatically pop open the user's browser on scheduled morning runs
    if "Scheduled" in trigger_source and cfg.get("auto_open_browser", True):
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    return meta

def reschedule_daily_job():
    scheduler.remove_all_jobs()
    cfg = get_config()
    hh, mm = map(int, cfg.get("schedule_time", "10:00").split(":"))
    scheduler.add_job(
        execute_snapshot,
        "cron",
        hour=hh,
        minute=mm,
        kwargs={"trigger_source": "Scheduled Daily Run", "profile_id": "ALL"}
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    reschedule_daily_job()
    scheduler.start()
    cfg = get_config()
    if cfg.get("scan_on_startup", False):
        import asyncio
        asyncio.create_task(execute_snapshot(trigger_source="Startup Auto-Scan", profile_id="ALL"))
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_dashboard():
    return FileResponse("static/index.html")

@app.get("/api/state")
def api_get_state():
    return {"jobs": list_jobs(), "meta": get_meta(), "config": get_config()}

@app.post("/api/run")
async def api_run_snapshot(payload: dict = Body(...)):
    profile_id = payload.get("profile_id", "ALL")
    lookback = payload.get("lookback_hours")
    if lookback:
        cfg = get_config()
        cfg["lookback_hours"] = int(lookback)
        save_config(cfg)
    meta = await execute_snapshot(trigger_source=f"Manual ({profile_id})", profile_id=profile_id)
    return {"meta": meta, "jobs": list_jobs()}

@app.post("/api/job/status")
def api_set_status(payload: dict = Body(...)):
    update_job_status(payload["dedup_key"], payload["status"])
    return {"ok": True}

@app.post("/api/config")
def api_save_config(new_cfg: dict = Body(...)):
    save_config(new_cfg)
    reschedule_daily_job()
    return {"ok": True, "config": get_config()}

@app.get("/api/knowledge-bank")
def api_get_knowledge_bank():
    cfg = get_config()
    return {"knowledge_bank_text": cfg.get("knowledge_bank_text", "")}

@app.post("/api/tailor-prompt")
def api_tailor_prompt(payload: dict = Body(...)):
    dedup_key = payload.get("dedup_key")
    cfg = get_config()
    kb_text = cfg.get("knowledge_bank_text", "")
    
    # Fetch job from DB
    import sqlite3
    from database import DB_PATH
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE dedup_key = ?", (dedup_key,)).fetchone()
    
    if not row:
        return {"error": "Job not found"}
    
    job = dict(row)
    raw_desc = job.get("description", "")
    if "<" in raw_desc or "&" in raw_desc:
        import html
        import re
        from bs4 import BeautifulSoup
        try:
            desc = BeautifulSoup(html.unescape(raw_desc), "html.parser").get_text(separator="\n")
            desc = re.sub(r'\n{3,}', '\n\n', desc).strip()
        except Exception:
            desc = raw_desc
    else:
        desc = raw_desc

    if len(desc) < 30:
        desc = f"Title: {job.get('title')}, Company: {job.get('company')}, Track: {job.get('role_track')}, Location: {job.get('location')}."

    prompt = f"""You are an elite Executive Career Strategist and ATS Optimization Specialist.
Your objective is to tailor the candidate's resume and generate 5 STAR achievement bullets customized specifically for this target position.

CRITICAL CANDIDATE PROFILE & EDUCATIONAL BACKGROUND:
- Academic Degree: Master of Business Administration (MBA) in Business.
- The candidate does NOT hold an undergraduate degree in Computer Science, Software Engineering, Electrical Engineering, or STEM.
- Positioning Strategy: Position the candidate as a high-impact Business, Operations, and Continuous Improvement Program Leader (Lean Six Sigma, Operational Excellence, Strategy, Cross-Functional Execution) who partners effectively with technical teams, rather than as an individual contributor software engineer or technical coder.

TARGET POSITION:
- Role Title: {job.get('title')}
- Company: {job.get('company')}
- Role Track: {job.get('role_track')}
- Seniority: {job.get('seniority')}
- Target Comp / Salary: {job.get('salary_display')}
- Matched Competencies: {job.get('matched_skills')}

JOB DESCRIPTION SUMMARY / EXCERPT:
{desc[:3000]}

CANDIDATE'S KNOWLEDGE BANK & VERIFIED EXPERIENCE:
{kb_text}

OUTPUT INSTRUCTIONS:
1. Executive Summary (3-4 high-impact sentences positioning the candidate as the ideal leader for this specific role, highlighting their MBA business acumen and operational excellence).
2. 5 Tailored STAR Achievement Bullets (Situation, Task, Action, Result) with strong metrics (%, $, time saved, cycle time reduction, throughput).
3. Top 8 Keyword Match Matrix (mapping the JD's exact phrases to the candidate's background).
4. Concise Cover Letter Hook (1 punchy paragraph explaining why the candidate is applying to {job.get('company')}).
"""
    return {
        "job": job,
        "prompt": prompt,
        "kb_snippet": kb_text[:300]
    }


if __name__ == "__main__":
    import uvicorn
    webbrowser.open(f"http://127.0.0.1:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
