import re

def compute_title_relevance(title):
    """
    Computes a title relevance score from 0 to 100.
    Rewards AI/ML, NLP, Backend engineering, and software development.
    """
    if not title:
        return 0.0
        
    title_lower = title.lower()
    score = 0.0
    
    # AI/ML core title match (highest leverage)
    ai_ml_keywords = [
        "machine learning", "ml engineer", "ai engineer", "artificial intelligence",
        "nlp", "natural language", "computer vision", "deep learning", "data scientist",
        "reinforcement learning", "speech engineer", "search engineer", "information retrieval"
    ]
    for kw in ai_ml_keywords:
        if kw in title_lower:
            score = max(score, 100.0)
            
    # Software/Backend title match (strong fit)
    backend_keywords = [
        "backend engineer", "backend developer", "software engineer", "software developer",
        "full stack developer", "full stack engineer", "systems engineer", "platform engineer",
        "data engineer", "infrastructure engineer", "technical lead", "tech lead"
    ]
    for kw in backend_keywords:
        if kw in title_lower:
            score = max(score, 75.0)
            
    # General developer/analyst match
    general_keywords = [
        "developer", "engineer", "programmer", "analyst"
    ]
    for kw in general_keywords:
        if kw in title_lower:
            score = max(score, 40.0)
            
    # Penalize management-only titles unless tech-focused
    if "manager" in title_lower or "director" in title_lower or "vp" in title_lower or "head of" in title_lower:
        # If it doesn't contain tech terms, apply a heavy penalty
        has_tech = any(t in title_lower for t in ["engineer", "developer", "technology", "software", "ml", "ai"])
        if not has_tech:
            score = min(score, 20.0)
            
    return score


def evaluate_skills(candidate_skills, core_required, preferred, skill_assessments):
    """
    Evaluates candidate skills against the JD requirement.
    Returns (raw_score, matched_core_count, matched_pref_count).
    """
    if not candidate_skills:
        return 0.0, 0, 0
        
    score = 0.0
    matched_core = 0
    matched_pref = 0
    
    # Skill proficiency multipliers
    prof_mults = {
        "expert": 1.0,
        "advanced": 0.85,
        "intermediate": 0.60,
        "beginner": 0.25
    }
    
    # Normalize inputs
    core_set = {s.lower() for s in core_required}
    pref_set = {s.lower() for s in preferred}
    
    for skill in candidate_skills:
        sname = skill.get("name", "").strip().lower()
        prof = skill.get("proficiency", "intermediate").strip().lower()
        dur = skill.get("duration_months", 12)
        endorsements = skill.get("endorsements", 0)
        
        # Calculate skill weights
        prof_w = prof_mults.get(prof, 0.60)
        
        # Duration multiplier: reward experience, cap at 3 years (36 months)
        dur_w = min(dur, 36) / 24.0  # 2 years is 1.0, max is 1.5
        
        # Endorsements multiplier: slight reward for external validation
        end_w = 1.0 + (min(endorsements, 50) / 100.0) # max 1.5
        
        skill_power = prof_w * dur_w * end_w
        
        # Check if skill is core required
        if sname in core_set:
            # Check if there is an assessment score on Redrob
            assess_bonus = 0.0
            if skill_assessments and sname in {k.lower() for k in skill_assessments.keys()}:
                # Find the exact key case
                exact_key = next((k for k in skill_assessments.keys() if k.lower() == sname), None)
                if exact_key:
                    assess_bonus = skill_assessments[exact_key] / 100.0  # 0.0 to 1.0 bonus
            
            score += (10.0 * skill_power) + (5.0 * assess_bonus)
            matched_core += 1
            
        # Check if skill is preferred (nice-to-have)
        elif sname in pref_set:
            score += 5.0 * skill_power
            matched_pref += 1
            
    # Normalize score out of 100
    # Core matches count for more, capped at 100
    normalized_score = min(score * 1.5, 100.0)
    
    return normalized_score, matched_core, matched_pref


def evaluate_location(candidate_loc, primary_locs, secondary_locs, willing_to_relocate):
    """
    Evaluates candidate's location match.
    Noida/Pune = 100.
    Secondary locations (Bangalore, Hyderabad, Mumbai, Delhi NCR) = 70.
    Willing to relocate = 60.
    Otherwise = 20.
    """
    if not candidate_loc:
        return 60.0 if willing_to_relocate else 20.0
        
    loc_lower = candidate_loc.lower()
    
    # Check primary locations
    for pl in primary_locs:
        if pl in loc_lower:
            return 100.0
            
    # Check secondary locations
    for sl in secondary_locs:
        if sl in loc_lower:
            return 70.0
            
    if willing_to_relocate:
        return 60.0
        
    return 20.0


def evaluate_education(education_list):
    """
    Evaluates candidate's education prestige.
    tier_1 = 100, tier_2 = 70, tier_3 = 40, tier_4 = 10, unknown = 20.
    """
    if not education_list:
        return 20.0
        
    best_tier = "unknown"
    tier_ranks = {
        "tier_1": 4,
        "tier_2": 3,
        "tier_3": 2,
        "tier_4": 1,
        "unknown": 0
    }
    
    for edu in education_list:
        tier = edu.get("tier", "unknown")
        if tier not in tier_ranks:
            tier = "unknown"
        if tier_ranks[tier] > tier_ranks[best_tier]:
            best_tier = tier
            
    tier_scores = {
        "tier_1": 100.0,
        "tier_2": 70.0,
        "tier_3": 40.0,
        "tier_4": 15.0,
        "unknown": 20.0
    }
    
    return tier_scores[best_tier]


def evaluate_experience(yoe, min_exp=5.0, max_exp=9.0):
    """
    Evaluates Years of Experience.
    Maximum score in the 5-9 target range.
    Smooth decay outside the range.
    """
    if yoe < min_exp:
        # Too junior (min_exp is 5.0)
        # 4.0 YOE gets 70, 3.5 YOE gets 50
        diff = min_exp - yoe
        score = max(0.0, 100.0 - (diff * 35.0))
        return score
    elif yoe <= max_exp:
        # Perfect target range (5-9 YOE)
        return 100.0
    else:
        # Too senior (max_exp is 9.0)
        # 10.0 YOE gets 90, 12.0 YOE gets 70, 15.0 YOE gets 40
        diff = yoe - max_exp
        score = max(20.0, 100.0 - (diff * 10.0))
        return score


def evaluate_notice_period(notice_days):
    """
    Evaluates notice period/availability.
    <= 30 days = 100.
    <= 60 days = 80.
    <= 90 days = 50.
    > 90 days = 20.
    """
    if notice_days is None:
        return 50.0
    if notice_days <= 30:
        return 100.0
    elif notice_days <= 60:
        return 80.0
    elif notice_days <= 90:
        return 50.0
    else:
        return 20.0


# --- Semantic Similarity Functions ---
import os

_MODEL_INSTANCE = None

def get_sentence_transformer(model_path="models/all-MiniLM-L6-v2"):
    """
    Lazy loads and returns the SentenceTransformer model from a local path.
    """
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        from sentence_transformers import SentenceTransformer
        # Resolve path - check if model files exist inside the path
        has_model_file = False
        if os.path.exists(model_path):
            has_model_file = os.path.exists(os.path.join(model_path, "model.safetensors")) or os.path.exists(os.path.join(model_path, "pytorch_model.bin"))
            
        if not os.path.exists(model_path) or not has_model_file:
            print(f"Local model path {model_path} or model weights not found. Loading online all-MiniLM-L6-v2...")
            _MODEL_INSTANCE = SentenceTransformer("all-MiniLM-L6-v2")
        else:
            print(f"Loading local model from {model_path}...")
            _MODEL_INSTANCE = SentenceTransformer(model_path)
    return _MODEL_INSTANCE

def compute_semantic_similarity(profile_text, jd_text, model_path="models/all-MiniLM-L6-v2"):
    """
    Computes cosine similarity between profile text and job description.
    Returns similarity score (float in range [0, 1]).
    """
    try:
        from sentence_transformers import util
        model = get_sentence_transformer(model_path)
        # Encode
        emb1 = model.encode(profile_text, convert_to_tensor=True)
        emb2 = model.encode(jd_text, convert_to_tensor=True)
        # Cosine similarity
        similarity = util.cos_sim(emb1, emb2).item()
        # Scale/normalize to [0, 1] range
        return max(0.0, min(similarity, 1.0))
    except Exception as e:
        print(f"Error in semantic similarity calculation: {e}")
        return 0.5  # Neutral fallback

