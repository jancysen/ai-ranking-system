import os
from datetime import datetime
from src.utils import parse_date

# Target date for the hackathon dataset timeline (June 2026)
REFERENCE_DATE = datetime(2026, 6, 17)

def check_honeypot(candidate):
    """
    Checks if a candidate is a honeypot (has impossible or highly contradictory data).
    Returns (is_honeypot_flag, list_of_reasons).
    """
    reasons = []
    profile = candidate.get("profile", {})
    yoe = profile.get("years_of_experience", 0)
    history = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    education = candidate.get("education", [])
    signals = candidate.get("redrob_signals", {})
    assessments = signals.get("skill_assessment_scores", {})
    
    # 1. Career duration vs Dates mismatch
    # If a job says duration_months is 166 but calendar dates only allow 33 months
    total_duration_months = 0
    for job in history:
        start_str = job.get("start_date")
        end_str = job.get("end_date")
        duration_months = job.get("duration_months", 0)
        total_duration_months += duration_months
        
        if start_str:
            try:
                start_date = parse_date(start_str)
                if start_date:
                    if end_str:
                        end_date = parse_date(end_str)
                    else:
                        end_date = REFERENCE_DATE
                    
                    if end_date:
                        actual_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
                        # Flag if there is a massive mismatch (more than 4 months difference)
                        if abs(duration_months - actual_months) > 4:
                            reasons.append(f"job_duration_mismatch: {job.get('company')} start={start_str} end={end_str} dur={duration_months} calculated={actual_months}")
            except Exception:
                pass

    # 2. Total Job Duration vs Stated Years of Experience
    total_job_years = total_duration_months / 12.0
    if total_job_years > yoe + 2.0:
        reasons.append(f"total_job_duration_exceeds_yoe: job_years={total_job_years:.1f}, yoe={yoe}")
    elif yoe > 3.0 and total_job_years < yoe * 0.3:
        reasons.append(f"total_job_duration_too_low: job_years={total_job_years:.1f}, yoe={yoe}")

    # 3. Skills Duration Anomalies (expert/advanced with 0 duration)
    expert_zero_dur = 0
    advanced_zero_dur = 0
    for s in skills:
        prof = s.get("proficiency")
        dur = s.get("duration_months", 0)
        if prof == "expert" and dur == 0:
            expert_zero_dur += 1
        if prof == "advanced" and dur == 0:
            advanced_zero_dur += 1
            
    if expert_zero_dur >= 3:
        reasons.append(f"multiple_expert_zero_duration_skills: {expert_zero_dur}")
    elif expert_zero_dur + advanced_zero_dur >= 5:
        reasons.append(f"multiple_high_prof_zero_duration_skills: expert={expert_zero_dur}, advanced={advanced_zero_dur}")

    # 4. Graduation Date vs Experience Mismatch
    if education:
        grad_years = [e["end_year"] for e in education if e.get("end_year") and 1970 <= e["end_year"] <= 2035]
        if grad_years:
            earliest_grad = min(grad_years)
            years_since_grad = REFERENCE_DATE.year - earliest_grad
            # Allow 1.5 years of leeway for pre-grad experience, but more is highly anomalous
            if yoe > years_since_grad + 2.0:
                reasons.append(f"yoe_exceeds_post_grad_years: yoe={yoe}, graduated={earliest_grad}")

    # 5. Assessment Mismatch (expert/advanced but fails platform skill test)
    for sname, score in assessments.items():
        matching_skill = next((s for s in skills if s["name"].lower() == sname.lower()), None)
        if matching_skill:
            prof = matching_skill.get("proficiency")
            if prof in ["expert", "advanced"] and score < 25.0:
                reasons.append(f"high_prof_low_assessment_score: skill={sname}, proficiency={prof}, score={score}")

    return len(reasons) > 0, reasons


def is_eligible(candidate, excluded_companies=None):
    """
    Checks if a candidate passes baseline eligibility criteria.
    Returns (eligible_flag, reason).
    """
    profile = candidate.get("profile", {})
    yoe = profile.get("years_of_experience", 0)
    current_title = profile.get("current_title", "")
    history = candidate.get("career_history", [])
    
    # 1. Experience level: Target is 5-9 years, exclude if way out of range
    if yoe < 3.5:
        return False, f"insufficient_experience: yoe={yoe}"
    if yoe > 18.0:
        return False, f"excessive_experience: yoe={yoe}"

    # 2. Exclude strictly non-technical current titles
    if not is_relevant_title(current_title):
        return False, f"irrelevant_current_title: {current_title}"

    # 3. Exclude if career history consists ONLY of IT services/consulting firms
    if excluded_companies and history:
        # Check if ALL companies in history are in excluded_companies
        all_consulting = True
        for job in history:
            company = job.get("company", "").strip().lower()
            # Check if company name contains any of the excluded strings
            is_excluded = any(ex in company for ex in excluded_companies)
            if not is_excluded:
                all_consulting = False
                break
        if all_consulting:
            return False, "only_worked_at_consulting_firms"

    return True, "eligible"


def is_relevant_title(title):
    """Checks if a title is relevant to engineering, software, product or data roles."""
    if not title:
        return False
    title_lower = title.lower()
    
    blacklist = [
        "hr manager", "hr recruiter", "recruiter", "human resources",
        "content writer", "copywriter", "writer", "blogger", "journalist",
        "graphic designer", "designer", "illustrator", "ui designer", "ux designer",
        "accountant", "bookkeeper", "finance manager", "accounting", "cfo", "auditor",
        "sales executive", "sales representative", "sales manager", "business development",
        "civil engineer", "mechanical engineer", "electrical engineer", "chemical engineer",
        "marketing manager", "digital marketer", "social media manager", "public relations"
    ]
    
    # Check if any blacklist item is in the title
    for item in blacklist:
        if item in title_lower:
            # Check for saving grace tech keywords
            if "software" in title_lower or "machine learning" in title_lower or "ai" in title_lower or "developer" in title_lower:
                continue
            return False
            
    return True


def parse_candidate(candidate):
    """
    Parses raw candidate data into structured representation.
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    
    parsed = {
        "candidate_id": candidate["candidate_id"],
        "name": profile.get("anonymized_name", ""),
        "headline": profile.get("headline", ""),
        "summary": profile.get("summary", ""),
        "years_of_experience": profile.get("years_of_experience", 0),
        "current_title": profile.get("current_title", ""),
        "current_company": profile.get("current_company", ""),
        "current_company_size": profile.get("current_company_size", ""),
        "current_industry": profile.get("current_industry", ""),
        "location": profile.get("location", ""),
        "country": profile.get("country", ""),
        "skills": candidate.get("skills", []),
        "career_history": candidate.get("career_history", []),
        "education": candidate.get("education", []),
        "certifications": candidate.get("certifications", []),
        "languages": candidate.get("languages", []),
        "redrob_signals": signals
    }
    return parsed
