from datetime import datetime
from src.utils import parse_date
from src.candidate_parser import REFERENCE_DATE
from src.matcher import (
    compute_title_relevance,
    evaluate_skills,
    evaluate_location,
    evaluate_education,
    evaluate_experience,
    evaluate_notice_period
)

_DEFAULT_RECENCY_CONFIG = None

def score_candidate(candidate, jd, weights, recency_config=None):
    """
    Computes candidate overall score.
    Returns (final_score, base_score, behavioral_multiplier, breakdown_dict).
    """
    # 1. Title alignment
    current_title = candidate.get("current_title", "")
    current_title_score = compute_title_relevance(current_title)
    
    # Check max of previous titles
    max_prev_title_score = 0.0
    for job in candidate.get("career_history", []):
        if not job.get("is_current"):
            title_score = compute_title_relevance(job.get("title", ""))
            max_prev_title_score = max(max_prev_title_score, title_score)
            
    # Combine titles: current is 70%, max previous is 30%
    combined_title_score = (current_title_score * 0.7) + (max_prev_title_score * 0.3)
    
    # 2. Skills matching
    signals = candidate.get("redrob_signals", {})
    assessments = signals.get("skill_assessment_scores", {})
    skills_score, matched_core, matched_pref = evaluate_skills(
        candidate.get("skills", []),
        jd["core_required_skills"],
        jd["preferred_skills"],
        assessments
    )
    
    # 3. Experience alignment
    yoe = candidate.get("years_of_experience", 0)
    exp_score = evaluate_experience(yoe, jd["min_experience"], jd["max_experience"])
    
    # 4. Education tiering
    edu_score = evaluate_education(candidate.get("education", []))
    
    # 5. Location matching
    willing_relocate = signals.get("willing_to_relocate", False)
    loc_score = evaluate_location(
        candidate.get("location", ""),
        jd["primary_locations"],
        jd["secondary_locations"],
        willing_relocate
    )
    
    # 6. Notice period
    notice_days = signals.get("notice_period_days", 60)
    notice_score = evaluate_notice_period(notice_days)
    
    # Compute Base Score
    base_score = (
        (combined_title_score * weights["title"]) +
        (skills_score * weights["skills"]) +
        (exp_score * weights["experience"]) +
        (edu_score * weights["education"]) +
        (loc_score * weights["location"]) +
        (notice_score * weights["notice_period"])
    )
    
    # 7. Behavioral Multiplier
    # Default = 1.0
    bm_response = 1.0
    response_rate = signals.get("recruiter_response_rate", 0.5)
    if response_rate < 0.1:
        bm_response = 0.7
    elif response_rate < 0.3:
        bm_response = 0.9
    elif response_rate >= 0.7:
        bm_response = 1.15
        
    bm_recency = 1.0
    last_active_str = signals.get("last_active_date")
    if last_active_str:
        last_active = parse_date(last_active_str)
        if last_active:
            days_inactive = (REFERENCE_DATE - last_active).days
            
            # Resolve recency configuration
            if recency_config is None:
                global _DEFAULT_RECENCY_CONFIG
                if _DEFAULT_RECENCY_CONFIG is None:
                    try:
                        from src.utils import load_config
                        config = load_config()
                        _DEFAULT_RECENCY_CONFIG = config.get("recency_multipliers", {
                            30: 1.15,
                            90: 1.05,
                            180: 0.85,
                            "default": 0.50
                        })
                    except Exception:
                        _DEFAULT_RECENCY_CONFIG = {
                            30: 1.15,
                            90: 1.05,
                            180: 0.85,
                            "default": 0.50
                        }
                recency_config = _DEFAULT_RECENCY_CONFIG
            
            # Normalize keys to allow both integer thresholds and defaults
            standard_recency = {}
            for k, v in recency_config.items():
                if str(k).isdigit():
                    standard_recency[int(k)] = float(v)
                else:
                    standard_recency[k] = float(v)
            
            thresholds = sorted([k for k in standard_recency.keys() if isinstance(k, int)])
            matched = False
            for t in thresholds:
                if days_inactive <= t:
                    bm_recency = standard_recency[t]
                    matched = True
                    break
            if not matched:
                bm_recency = standard_recency.get("default", 0.50)
                
    bm_open = 1.05 if signals.get("open_to_work_flag", False) else 0.95
    
    bm_github = 1.0
    github_score = signals.get("github_activity_score", -1)
    if github_score > 50:
        bm_github = 1.15
    elif github_score > 20:
        bm_github = 1.05
        
    bm_interview = 1.0
    interview_rate = signals.get("interview_completion_rate", 1.0)
    if interview_rate < 0.5:
        bm_interview = 0.8
    elif interview_rate >= 0.85:
        bm_interview = 1.05
        
    bm_offer = 1.0
    offer_rate = signals.get("offer_acceptance_rate", -1)
    if offer_rate != -1 and offer_rate < 0.3:
        bm_offer = 0.85
    elif offer_rate >= 0.75:
        bm_offer = 1.05
        
    # Calculate aggregate behavioral multiplier
    behavioral_multiplier = bm_response * bm_recency * bm_open * bm_github * bm_interview * bm_offer
    
    # Cap behavioral multiplier to avoid extreme variance
    behavioral_multiplier = max(0.4, min(behavioral_multiplier, 1.3))
    
    # Final normalized score (scale from 0 to 1)
    final_score = (base_score / 100.0) * behavioral_multiplier
    # Ensure it stays within [0.0, 1.0]
    final_score = max(0.0, min(final_score, 1.0))
    
    breakdown = {
        "title_score": combined_title_score,
        "skills_score": skills_score,
        "experience_score": exp_score,
        "education_score": edu_score,
        "location_score": loc_score,
        "notice_score": notice_score,
        "matched_core": matched_core,
        "matched_pref": matched_pref
    }
    
    return final_score, base_score, behavioral_multiplier, breakdown


def generate_reasoning(candidate, jd, score, breakdown):
    """
    Generates a personalized, highly accurate 1-2 sentence justification for the candidate's rank.
    Differentiates candidates highlighting their top assets (GitHub, Assessments, Education, or Responsiveness)
    to ensure highly varied, non-repetitive descriptions across the spreadsheet.
    """
    profile_title = candidate.get("current_title", "Software Engineer")
    yoe = candidate.get("years_of_experience", 0)
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})
    location = candidate.get("location", "")
    notice = signals.get("notice_period_days", 60)
    response_rate = signals.get("recruiter_response_rate", 0.5)
    response_time = signals.get("avg_response_time_hours", 24.0)
    github_score = signals.get("github_activity_score", -1)
    assessments = signals.get("skill_assessment_scores", {})
    current_company = candidate.get("current_company", "")
    current_company_size = candidate.get("current_company_size", "")
    open_to_work = signals.get("open_to_work_flag", False)
    completeness = signals.get("profile_completeness_score", 0)
    
    # 1. Identify key matching skills
    candidate_skill_names = {s["name"].lower() for s in skills}
    core_matches = [s for s in jd["core_required_skills"] if s.lower() in candidate_skill_names]
    pref_matches = [s for s in jd["preferred_skills"] if s.lower() in candidate_skill_names]
    all_matches = core_matches + pref_matches
    highlight_skills = all_matches[:3]
    skills_phrase = f"strong in {', '.join(highlight_skills)}" if highlight_skills else "matching adjacent engineering skills"

    # 2. Find education info
    education = candidate.get("education", [])
    edu_phrase = ""
    edu_inst = ""
    if education:
        tier_ranks = {"tier_1": "Tier-1", "tier_2": "Tier-2"}
        for edu in education:
            t = edu.get("tier", "unknown")
            if t in tier_ranks:
                edu_phrase = f"academic background from a {tier_ranks[t]} school"
                edu_inst = edu.get("institution", "")
                break

    # 3. Find top assessment score
    top_assess_skill = ""
    top_assess_score = 0
    if assessments:
        for sname, sscore in assessments.items():
            if sscore > top_assess_score:
                top_assess_score = sscore
                top_assess_skill = sname

    # 4. Construct lead clause based on top differentiator
    lead_clause = ""
    if github_score > 45:
        lead_clause = f"Active open-source contributor with a high GitHub activity score of {github_score:.0f} and {yoe:.1f} years of experience as a {profile_title}"
    elif top_assess_score > 75 and top_assess_skill:
        lead_clause = f"Proven technical expert with a {top_assess_score:.0f}% score on the Redrob {top_assess_skill} assessment and {yoe:.1f} years of experience"
    elif edu_phrase and edu_inst:
        lead_clause = f"Educated at elite {edu_inst} ({edu_phrase}) with a strong engineering trajectory and {yoe:.1f} years of experience"
    elif response_rate > 0.75:
        lead_clause = f"Highly responsive candidate ({int(response_rate*100)}% response rate, {response_time:.1f}h avg response) with {yoe:.1f} years of experience"
    elif open_to_work:
        lead_clause = f"Active job seeker ready for immediate deployment with {yoe:.1f} years of experience as a {profile_title}"
    elif completeness > 90:
        lead_clause = f"Fully verified professional with a comprehensive profile and {yoe:.1f} years of experience as a {profile_title}"
    elif current_company and current_company_size in ["10001+", "5001-10000", "1001-5000"]:
        lead_clause = f"Experienced {profile_title} with {yoe:.1f} years of experience, currently at large enterprise {current_company}"
    elif current_company and current_company_size in ["11-50", "51-200", "201-500"]:
        lead_clause = f"Scrappy product engineer with {yoe:.1f} years of experience, currently at growing startup {current_company}"
    else:
        lead_clause = f"Competent {profile_title} with {yoe:.1f} years of experience"

    # 5. Construct middle clause summarizing skills
    middle_clause = f", demonstrated by being {skills_phrase}"

    # 6. Construct close clause summarizing logistics and minor gaps
    logistics_parts = []
    if location:
        logistics_parts.append(f"based in {location}")
    if notice <= 30:
        logistics_parts.append("immediately available (<=30d notice)")
    else:
        logistics_parts.append(f"subject to a {notice}-day notice period")
        
    logistics_clause = f"; {', '.join(logistics_parts)}"

    # 7. Add concern/gap note if any
    gap_note = ""
    if notice > 90:
        gap_note = f" (Note: longer {notice}-day notice is a minor constraint)"
    elif yoe > jd["max_experience"] + 3:
        gap_note = " (Note: experience is significantly above target range)"
    elif yoe < jd["min_experience"]:
        gap_note = " (Note: candidate is slightly more junior than target)"

    # Combine
    reasoning = f"{lead_clause}{middle_clause}{logistics_clause}{gap_note}."
    return reasoning

