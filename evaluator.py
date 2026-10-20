import re
import html
import bs4
from datetime import datetime, date, timezone, timedelta
from taxonomy import normalize_company

SALARY_REGEX = re.compile(
    r"\$\s?(\d{2,3}(?:,\d{3})+(?:\.\d{2})?|\d{2,3}[kK])\s*(?:-|to|–|—)\s*\$\s?(\d{2,3}(?:,\d{3})+(?:\.\d{2})?|\d{2,3}[kK])",
    re.IGNORECASE
)

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "your", "will", "have", "are",
    "work", "team", "role", "experience", "years", "ability", "skills", "including", "our"
}

def strict_location_match(loc_str: str, profile: dict, include_remote_us: bool = False) -> bool:
    """Eliminates the Washington DC / Sydney NSW / Dallas TX false-positive bug."""
    if not loc_str:
        return False
    low = loc_str.lower()

    # 1. Hard block forbidden cities/states (e.g. Washington, D.C., Dallas for Austin, Sydney for WA)
    for bad in profile.get("forbidden_tokens", []):
        if bad.lower() in low:
            # Only allow if an explicit target city from this hub is ALSO listed in a multi-location string
            if not any(city in low for city in profile.get("city_tokens", [])):
                return False

    # 2. Check explicit metro city names (e.g., Seattle, Bellevue, Redmond, Denver, Boulder, Beaverton, Austin)
    if any(city in low for city in profile.get("city_tokens", [])):
        return True

    # 3. Check strict word-boundary State Code (e.g. ", WA" or " WA " but NEVER "New South Wales" or "Waltham")
    state_code = profile.get("state_code", "")
    if state_code:
        if re.search(rf"(?:,\s*|\b){re.escape(state_code)}(?:\b|$)", loc_str):
            return True

    # 4. Optional US-Remote handling (off by default so remote jobs don't duplicate across all hubs)
    if include_remote_us and ("remote" in low) and not any(x in low for x in ["canada", "uk", "india", "europe", "emea", "apac"]):
        return True

    return False

def classify_strict_3way_track(title: str, description: str, config: dict) -> str:
    """
    Strictly separates:
    1. Technical PM (TPM) — quarantines any hardware/software/avionics/infra/AI engineering PM role
    2. Process Improvement & Ops — Six Sigma, Continuous Improvement, Kaizen, Operational Excellence
    3. Non-Tech / Business PM — Pure Business, Strategic, GTM, People, Compliance, Supply Chain, Ops PM
    """
    t_low = (title or "").lower()
    d_low = (description or "")[:1500].lower()

    # Step 1: Check if Title or Core Focus is Technical PM (Strict Quarantine)
    tech_tokens = config.get("technical_quarantine_keywords", [])
    if any(tok.lower() in t_low for tok in tech_tokens):
        return "Technical PM (TPM)"

    # Also quarantine if title says "Program Manager" alongside deep engineering hardware/software org tags
    if re.search(r"\b(asic|fpga|avionics|silicon|firmware|sw/fw|kernel|kubernetes|cloud infra|machine learning|llm|propulsion)\b", t_low + " " + d_low[:400]):
        return "Technical PM (TPM)"

    # Step 2: Check if Process Improvement / Operational Excellence
    pi_tokens = config.get("process_improvement_keywords", [])
    if any(tok.lower() in t_low for tok in pi_tokens):
        return "Process Improvement & Ops"
    if any(tok.lower() in d_low[:600] for tok in ["lean six sigma", "continuous improvement", "value stream mapping", "kaizen", "operational excellence"]):
        return "Process Improvement & Ops"

    # Step 3: Pure Non-Tech / Business Program Manager
    return "Non-Tech / Business PM"

def compute_knowledge_bank_match(title: str, description: str, track: str, kb_text: str):
    """Scores the job against the user's personal Knowledge Bank stories and returns matched keywords."""
    if not kb_text or not kb_text.strip():
        return 50, ["Standard Profile Match"]

    # Extract meaningful multi-word and single-word competencies from Knowledge Bank
    high_value_phrases = [
        "process improvement", "continuous improvement", "operational excellence", "lean six sigma",
        "program management", "cross-functional", "stakeholder management", "change management",
        "business operations", "cost reduction", "kpi", "kaizen", "value stream", "pmo",
        "transformation", "supply chain", "governance", "roadmap", "process re-engineering",
        "executive reporting", "risk management", "vendor management", "workflow automation"
    ]
    kb_low = kb_text.lower()
    job_blob = f"{title} {description}".lower()

    matched_Competencies = []
    for phrase in high_value_phrases:
        if phrase in kb_low and phrase in job_blob:
            matched_Competencies.append(phrase.title())

    # Token overlap fallback
    kb_words = {w for w in re.findall(r"[a-z]{4,}", kb_low) if w not in STOPWORDS}
    job_words = {w for w in re.findall(r"[a-z]{4,}", job_blob) if w not in STOPWORDS}
    overlap = kb_words.intersection(job_words)

    raw_ratio = min(1.0, (len(matched_Competencies) * 0.18) + (len(overlap) / max(12, len(kb_words) * 0.35)))
    kb_score = int(45 + (raw_ratio * 55))

    if track in ["Non-Tech / Business PM", "Process Improvement & Ops"]:
        kb_score = min(100, kb_score + 8)

    top_tags = matched_Competencies[:4] if matched_Competencies else [w.capitalize() for w in list(overlap)[:3]]
    return kb_score, (top_tags or ["Core PM Alignment"])

def _parse_dollar(val_str: str) -> int:
    clean = val_str.lower().replace(",", "").replace("$", "").strip()
    if clean.endswith("k"):
        return int(float(clean[:-1]) * 1000)
    return int(float(clean))

def extract_salary(text: str, est_base: str, min_from_board=None, max_from_board=None):
    try:
        if min_from_board and max_from_board and float(min_from_board) > 35000:
            lo, hi = int(float(min_from_board)), int(float(max_from_board))
            return lo, hi, f"${int(lo/1000)}k - ${int(hi/1000)}k (Verified)"
    except Exception:
        pass

    if text:
        match = SALARY_REGEX.search(text)
        if match:
            try:
                lo = _parse_dollar(match.group(1))
                hi = _parse_dollar(match.group(2))
                if 45000 <= lo <= 650000:
                    return lo, hi, f"${int(lo/1000)}k - ${int(hi/1000)}k (Posted)"
            except Exception:
                pass

    if est_base and est_base != "Not Listed":
        return 0, 0, f"{est_base} (Tier Est.)"
    return 0, 0, "Not Listed"

def classify_seniority(title: str) -> str:
    t = (title or "").lower()
    if any(k in t for k in ["principal", "director", "head of", "vp", "staff"]):
        return "Principal / Staff / Dir"
    if any(k in t for k in ["senior", "sr.", "sr ", "lead", "iii"]):
        return "Senior (Sr / L6)"
    return "Mid-Senior (L5 / II)"

def parse_posted_date(val):
    now = datetime.now()
    today_date = now.date()

    if not val:
        return now.isoformat(), f"Today, {now.strftime('%I:%M %p').lstrip('0')}", True

    # 1. Numeric timestamp (Lever epoch ms)
    if isinstance(val, (int, float)):
        ts = val / 1000.0 if val > 1e11 else val
        try:
            dt = datetime.fromtimestamp(ts)
            has_time = True
            iso = dt.isoformat()
            if dt.date() == today_date:
                disp = f"Today, {dt.strftime('%I:%M %p').lstrip('0')}"
            elif dt.date() == today_date - timedelta(days=1):
                disp = f"Yesterday, {dt.strftime('%I:%M %p').lstrip('0')}"
            else:
                disp = dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
            return iso, disp, has_time
        except Exception:
            return now.isoformat(), "Recently", False

    # 2. Python date or datetime object (e.g. from JobSpy / pandas)
    if isinstance(val, datetime):
        dt = val
        has_time = not (dt.hour == 0 and dt.minute == 0 and dt.second == 0)
        iso = dt.isoformat()
        if has_time:
            time_str = dt.strftime("%I:%M %p").lstrip("0")
            if dt.date() == today_date:
                disp = f"Today, {time_str}"
            elif dt.date() == today_date - timedelta(days=1):
                disp = f"Yesterday, {time_str}"
            else:
                disp = dt.strftime("%b %d, ") + time_str
        else:
            if dt.date() == today_date:
                disp = f"Today ({dt.strftime('%b %d')})"
            elif dt.date() == today_date - timedelta(days=1):
                disp = f"Yesterday ({dt.strftime('%b %d')})"
            else:
                disp = dt.strftime("%b %d").replace(" 0", " ")
        return iso, disp, has_time

    if isinstance(val, date):
        d = val
        dt = datetime.combine(d, datetime.min.time())
        iso = dt.isoformat()
        if d == today_date:
            disp = f"Today ({d.strftime('%b %d')})"
        elif d == today_date - timedelta(days=1):
            disp = f"Yesterday ({d.strftime('%b %d')})"
        else:
            disp = d.strftime("%b %d").replace(" 0", " ")
        return iso, disp, False

    # 3. String parsing
    s = str(val).strip()

    # Relative time expressions (e.g. "3 hours ago", "42 hours ago", "15 minutes ago", "about 4 hours", "Active 24 hours ago")
    m_rel = re.search(r"(\d+)\s*(second|sec|minute|min|hour|hr|day|week|month)", s, re.IGNORECASE)
    if m_rel:
        num = int(m_rel.group(1))
        unit = m_rel.group(2).lower()
        if "sec" in unit:
            est_dt = now - timedelta(seconds=num)
            return est_dt.isoformat(), f"Today, {est_dt.strftime('%I:%M %p').lstrip('0')}", True
        elif "min" in unit:
            est_dt = now - timedelta(minutes=num)
            return est_dt.isoformat(), f"Today, {est_dt.strftime('%I:%M %p').lstrip('0')} ({num}m ago)", True
        elif "hour" in unit or "hr" in unit:
            est_dt = now - timedelta(hours=num)
            time_str = est_dt.strftime("%I:%M %p").lstrip("0")
            if est_dt.date() == today_date:
                disp = f"Today, {time_str} ({num}h ago)"
            elif est_dt.date() == today_date - timedelta(days=1):
                disp = f"Yesterday, {time_str} ({num}h ago)"
            else:
                disp = est_dt.strftime("%b %d, ") + f"{time_str} ({num}h ago)"
            return est_dt.isoformat(), disp, True
        elif "day" in unit:
            est_dt = now - timedelta(days=num)
            time_str = est_dt.strftime("%I:%M %p").lstrip("0")
            if num == 1:
                disp = f"Yesterday, ~{time_str}"
            else:
                disp = f"{num}d ago ({est_dt.strftime('%b %d')})"
            return est_dt.isoformat(), disp, True
        elif "week" in unit:
            est_dt = now - timedelta(weeks=num)
            disp = f"{num}w ago ({est_dt.strftime('%b %d')})"
            return est_dt.isoformat(), disp, False
        elif "month" in unit:
            est_dt = now - timedelta(days=num * 30)
            disp = f"{num}mo ago ({est_dt.strftime('%b %d')})"
            return est_dt.isoformat(), disp, False

    # Workday formats
    low = s.lower()
    if "just posted" in low or "moments ago" in low:
        return now.isoformat(), f"Today, {now.strftime('%I:%M %p').lstrip('0')}", True
    elif "today" in low:
        iso = datetime.combine(today_date, now.time()).isoformat()
        return iso, f"Today, {now.strftime('%I:%M %p').lstrip('0')}", True
    elif "yesterday" in low:
        yd = today_date - timedelta(days=1)
        iso = datetime.combine(yd, now.time()).isoformat()
        return iso, f"Yesterday, ~{now.strftime('%I:%M %p').lstrip('0')}", True
    m_days = re.search(r"(\d+)\s+days?\s+ago", low)
    if m_days:
        num = int(m_days.group(1))
        d = today_date - timedelta(days=num)
        iso = datetime.combine(d, now.time()).isoformat()
        return iso, f"{num}d ago ({d.strftime('%b %d')})", False

    # ISO format (Greenhouse / Ashby / Workday)
    try:
        clean_s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_s)
        has_time = not (dt.hour == 0 and dt.minute == 0 and dt.second == 0)
        iso = dt.isoformat()
        d = dt.date()
        time_str = dt.strftime("%I:%M %p").lstrip("0")
        if has_time:
            if d == today_date:
                disp = f"Today, {time_str}"
            elif d == today_date - timedelta(days=1):
                disp = f"Yesterday, {time_str}"
            else:
                disp = dt.strftime("%b %d, ") + time_str
        else:
            if d == today_date:
                disp = f"Today ({d.strftime('%b %d')})"
            elif d == today_date - timedelta(days=1):
                disp = f"Yesterday ({d.strftime('%b %d')})"
            else:
                disp = d.strftime("%b %d").replace(" 0", " ")
        return iso, disp, has_time
    except Exception:
        pass

    # Formatted date strings (e.g. October 15, 2026 or 2026-10-15)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            d = dt.date()
            iso = dt.isoformat()
            if d == today_date:
                disp = f"Today ({d.strftime('%b %d')})"
            elif d == today_date - timedelta(days=1):
                disp = f"Yesterday ({d.strftime('%b %d')})"
            else:
                disp = d.strftime("%b %d").replace(" 0", " ")
            return iso, disp, False
        except Exception:
            pass

    return now.isoformat(), f"Today, {now.strftime('%I:%M %p').lstrip('0')}", True

TECH_DEGREE_PATTERN = re.compile(
    r"(?:bachelor(?:['’]s)?(?:\s+degree)?|degree|bs|b\.s\.|b\.e\.|undergraduate|4-year)\s+in\s+[^.\n;]*(?:engineering|computer science|stem|technical discipline|electrical|mechanical|software engineering|aerospace|avionics|physics|mathematics)",
    re.IGNORECASE
)

MBA_PATTERN = re.compile(
    r"\b(?:mba|master(?:['’]s)?\s+(?:of|in)\s+business|business\s+administration|degree\s+in\s+business)\b",
    re.IGNORECASE
)

def evaluate_degree_fit(title: str, description: str, track: str):
    """
    Evaluates educational alignment against candidate's profile:
    - Candidate holds an MBA in Business Administration.
    - Candidate does NOT hold an undergraduate engineering or computer science degree.
    
    Rules:
    - If job mandates a Bachelor's in Engineering/CS without business/MBA equivalence:
      Strictly disqualify from 100% match. Apply -35 pt deduction and hard cap at 65% max fit score.
      Tag: '⚠️ Requires Eng/CS Degree (MBA Gap)'
    - If job requires Engineering/CS but includes practical equivalent experience clause:
      Apply -20 pt deduction and cap at 72% max fit score.
      Tag: '⚠️ Requires Eng/CS Degree (Equiv Exp Allowed)'
    - If job explicitly values or accepts an MBA / Business degree:
      Apply +5 pt boost, full 100% eligibility.
      Tag: '🎓 MBA Preferred/Aligned'
    """
    if not description:
        if track == "Technical PM (TPM)":
            return -15, 75, ["Technical TPM Track"]
        return 0, 100, []

    clean_desc = bs4.BeautifulSoup(html.unescape(description), "html.parser").get_text(separator=" ")
    
    has_tech_deg = bool(TECH_DEGREE_PATTERN.search(clean_desc))
    has_mba = bool(MBA_PATTERN.search(clean_desc))
    has_equiv = bool(re.search(r"or\s+(?:equivalent|related\s+field|practical\s+experience|relevant\s+experience)", clean_desc, re.IGNORECASE))

    # Also check if title or core text indicates strict engineering domain
    if not has_tech_deg and re.search(r"\b(electrical|mechanical|systems|firmware|hardware)\s+engineering\b", clean_desc[:500], re.IGNORECASE) and track == "Technical PM (TPM)":
        has_tech_deg = True

    if has_tech_deg:
        if has_mba:
            return 0, 95, ["🎓 MBA Aligned (Tech/Biz)"]
        elif has_equiv:
            return -20, 72, ["⚠️ Requires Eng/CS Degree (Equiv Exp Allowed)"]
        else:
            return -35, 65, ["⚠️ Requires Eng/CS Degree (MBA Gap)"]

    if has_mba:
        return 5, 100, ["🎓 MBA Preferred/Aligned"]

    return 0, 100, []

def enrich_job(raw_job: dict, config: dict) -> dict:
    title = raw_job.get("title", "")
    desc = raw_job.get("description", "")
    raw_company = raw_job.get("company", "Unknown")

    canonical_comp, sub_brand, tier, est_base = normalize_company(raw_company)
    track = classify_strict_3way_track(title, desc, config)
    seniority = classify_seniority(title)
    sal_min, sal_max, sal_display = extract_salary(
        f"{title} {desc}", est_base, raw_job.get("salary_min"), raw_job.get("salary_max")
    )

    kb_score, matched_skills = compute_knowledge_bank_match(
        title, desc, track, config.get("knowledge_bank_text", "")
    )

    # Evaluate Educational Background (MBA vs Engineering/CS degree requirements)
    deg_penalty, deg_cap, deg_flags = evaluate_degree_fit(title, desc, track)

    # Blend Knowledge Bank Match with Company Tier, Salary Alignment & Degree Alignment
    tier_bonus = 12 if "Tier 1" in tier else 9 if "Tier 2" in tier else 6 if "Tier 3" in tier or "Tier 4" in tier else 0
    raw_score = int(kb_score * 0.88) + tier_bonus + deg_penalty
    final_score = min(deg_cap, max(20, raw_score))

    all_matched_skills = list(matched_skills)
    if deg_flags:
        all_matched_skills = deg_flags + [s for s in all_matched_skills if s not in deg_flags]

    combined_loc = f"{title} {raw_job.get('location', '')} {desc[:300]}".lower()
    work_mode = "Remote" if "remote" in combined_loc else "Hybrid" if "hybrid" in combined_loc else "Onsite / Flex"

    # Parse posted date and time granularity
    raw_date = raw_job.get("posted_raw") or raw_job.get("posted_at")
    posted_iso, posted_display, has_exact_time = parse_posted_date(raw_date)

    raw_job.update({
        "company": canonical_comp,
        "sub_brand": sub_brand,
        "tier": tier,
        "role_track": track,
        "seniority": seniority,
        "work_mode": work_mode,
        "salary_min": sal_min,
        "salary_max": sal_max,
        "salary_display": sal_display,
        "fit_score": final_score,
        "matched_skills": ", ".join(all_matched_skills),
        "posted_at": posted_iso,
        "posted_display": posted_display,
        "has_exact_time": 1 if has_exact_time else 0
    })
    return raw_job
