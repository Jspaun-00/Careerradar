import sqlite3
import json
import hashlib
from datetime import datetime, timezone
from taxonomy import DEFAULT_CONFIG

DB_PATH = "career_radar_v4.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                dedup_key TEXT PRIMARY KEY,
                profile_id TEXT,
                profile_name TEXT,
                company TEXT,
                sub_brand TEXT,
                tier TEXT,
                title TEXT,
                role_track TEXT,
                seniority TEXT,
                work_mode TEXT,
                location TEXT,
                salary_min INTEGER,
                salary_max INTEGER,
                salary_display TEXT,
                fit_score INTEGER,
                matched_skills TEXT,
                url TEXT,
                ats TEXT,
                status TEXT DEFAULT 'NEW',
                first_seen TEXT,
                posted_at TEXT,
                posted_display TEXT,
                has_exact_time INTEGER DEFAULT 0,
                description TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Schema migration check for existing tables
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(jobs)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "posted_at" not in existing_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN posted_at TEXT")
        if "posted_display" not in existing_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN posted_display TEXT")
        if "has_exact_time" not in existing_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN has_exact_time INTEGER DEFAULT 0")
        if "description" not in existing_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN description TEXT")
        if "resume_catered" not in existing_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN resume_catered INTEGER DEFAULT 0")
        if "resume_catered_at" not in existing_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN resume_catered_at TEXT")

        # Purge any Glassdoor entries as requested
        conn.execute("DELETE FROM jobs WHERE ats LIKE '%glassdoor%' OR ats LIKE '%Glassdoor%' OR company LIKE '%Glassdoor%'")
        # Ensure any records with null or 'Recently' posted_display are properly computed
        rows = conn.execute("SELECT dedup_key, coalesce(posted_at, first_seen) FROM jobs WHERE posted_display IS NULL OR posted_display = 'Recently'").fetchall()
        for k, pat in rows:
            if pat:
                from evaluator import parse_posted_date
                iso, disp, has_time = parse_posted_date(pat)
                conn.execute("UPDATE jobs SET posted_at = ?, posted_display = ?, has_exact_time = ? WHERE dedup_key = ?", (iso, disp, 1 if has_time else 0, k))

def get_config() -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT value FROM app_state WHERE key = 'config'").fetchone()
        if row:
            saved = json.loads(row[0])
            merged = {**DEFAULT_CONFIG, **saved}
            existing_pids = {p["id"] for p in merged.get("profiles", [])}
            for def_p in DEFAULT_CONFIG.get("profiles", []):
                if def_p["id"] not in existing_pids:
                    merged.setdefault("profiles", []).append(def_p)
            return merged
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(cfg: dict):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES ('config', ?)", (json.dumps(cfg),))

def save_meta(meta: dict):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES ('last_meta', ?)", (json.dumps(meta),))

def get_meta() -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT value FROM app_state WHERE key = 'last_meta'").fetchone()
        return json.loads(row[0]) if row else {}

def upsert_jobs(jobs: list) -> int:
    new_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        for j in jobs:
            raw_id = f"{j.get('profile_id')}_{j.get('company')}_{j.get('title')}_{j.get('location')}".lower()
            dedup_key = hashlib.sha256(raw_id.encode()).hexdigest()[:24]
            exists = conn.execute("SELECT 1 FROM jobs WHERE dedup_key = ?", (dedup_key,)).fetchone()
            if not exists:
                conn.execute("""
                    INSERT INTO jobs (
                        dedup_key, profile_id, profile_name, company, sub_brand, tier, title,
                        role_track, seniority, work_mode, location, salary_min, salary_max,
                        salary_display, fit_score, matched_skills, url, ats, status, first_seen,
                        posted_at, posted_display, has_exact_time, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NEW', ?, ?, ?, ?, ?)
                """, (
                    dedup_key, j.get("profile_id"), j.get("profile_name"), j.get("company"),
                    j.get("sub_brand", ""), j.get("tier"), j.get("title"), j.get("role_track"),
                    j.get("seniority"), j.get("work_mode"), j.get("location"), j.get("salary_min", 0),
                    j.get("salary_max", 0), j.get("salary_display"), j.get("fit_score", 50),
                    j.get("matched_skills", ""), j.get("url"), j.get("ats"), now_iso,
                    j.get("posted_at", now_iso), j.get("posted_display", f"Today, {datetime.now().strftime('%I:%M %p').lstrip('0')}"),
                    1 if j.get("has_exact_time") else 0, j.get("description", "")
                ))
                new_count += 1
            else:
                conn.execute("""
                    UPDATE jobs SET posted_at = coalesce(?, posted_at),
                                    posted_display = coalesce(?, posted_display),
                                    has_exact_time = coalesce(?, has_exact_time),
                                    description = case when length(description) < 10 then ? else description end
                    WHERE dedup_key = ?
                """, (j.get("posted_at"), j.get("posted_display"), 1 if j.get("has_exact_time") else 0, j.get("description", ""), dedup_key))
    return new_count

def list_jobs() -> list:
    from evaluator import parse_posted_date
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        # Order by posted_at DESC (most recent first) by default
        rows = conn.execute("SELECT * FROM jobs ORDER BY posted_at DESC, first_seen DESC").fetchall()
        jobs_list = []
        for r in rows:
            d = dict(r)
            if d.get("posted_at"):
                _, dynamic_disp, has_time = parse_posted_date(d["posted_at"])
                d["posted_display"] = dynamic_disp
                d["has_exact_time"] = 1 if has_time else 0
            jobs_list.append(d)
        return jobs_list

def update_job_status(dedup_key: str, status: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE dedup_key = ?", (status, dedup_key))

def update_resume_catered(dedup_key: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE jobs SET resume_catered = 1, resume_catered_at = ? WHERE dedup_key = ?", (now_iso, dedup_key))
