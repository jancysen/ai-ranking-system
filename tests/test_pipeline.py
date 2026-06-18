import pytest
from src.candidate_parser import check_honeypot, is_eligible, parse_candidate
from src.jd_parser import get_target_jd, parse_jd
from src.scorer import score_candidate, generate_reasoning

@pytest.fixture
def sample_valid_candidate():
    return {
        "candidate_id": "CAND_0000001",
        "profile": {
            "anonymized_name": "Ira Vora",
            "headline": "Backend Engineer | SQL, Spark, Cloud",
            "summary": "Software engineer with 6.9 years of experience.",
            "location": "Noida",
            "country": "India",
            "years_of_experience": 6.9,
            "current_title": "Backend Engineer",
            "current_company": "Startup Co",
            "current_company_size": "11-50",
            "current_industry": "Software"
        },
        "career_history": [
            {
                "company": "Startup Co",
                "title": "Backend Engineer",
                "start_date": "2024-03-08",
                "end_date": None,
                "duration_months": 27,
                "is_current": True,
                "industry": "Software",
                "company_size": "11-50",
                "description": "Building backend APIs in Python."
            }
        ],
        "education": [
            {
                "institution": "IIT Delhi",
                "degree": "B.Tech",
                "field_of_study": "Computer Science",
                "start_year": 2015,
                "end_year": 2019,
                "tier": "tier_1"
            }
        ],
        "skills": [
            {
                "name": "Python",
                "proficiency": "advanced",
                "duration_months": 36,
                "endorsements": 15
            },
            {
                "name": "embeddings",
                "proficiency": "advanced",
                "duration_months": 24,
                "endorsements": 10
            }
        ],
        "redrob_signals": {
            "profile_completeness_score": 90,
            "signup_date": "2024-01-01",
            "last_active_date": "2026-06-10",
            "open_to_work_flag": True,
            "recruiter_response_rate": 0.8,
            "skill_assessment_scores": {"embeddings": 80.0},
            "notice_period_days": 15,
            "willing_to_relocate": True,
            "github_activity_score": 45
        }
    }

def test_check_honeypot_valid(sample_valid_candidate):
    is_hp, reasons = check_honeypot(sample_valid_candidate)
    assert not is_hp
    assert len(reasons) == 0

def test_check_honeypot_mismatch_duration(sample_valid_candidate):
    # Mess up career history dates
    # start_date is 2024-03-08 (calculated months to 2026-06-17 is 27), but dur is 120
    sample_valid_candidate["career_history"][0]["duration_months"] = 120
    is_hp, reasons = check_honeypot(sample_valid_candidate)
    assert is_hp
    assert any("job_duration_mismatch" in r for r in reasons)

def test_check_honeypot_mismatch_skills(sample_valid_candidate):
    # Expert skills with 0 duration
    sample_valid_candidate["skills"] = [
        {"name": "Python", "proficiency": "expert", "duration_months": 0, "endorsements": 0},
        {"name": "SQL", "proficiency": "expert", "duration_months": 0, "endorsements": 0},
        {"name": "Docker", "proficiency": "expert", "duration_months": 0, "endorsements": 0}
    ]
    is_hp, reasons = check_honeypot(sample_valid_candidate)
    assert is_hp
    assert any("multiple_expert_zero_duration_skills" in r for r in reasons)

def test_eligibility_checks(sample_valid_candidate):
    # Valid candidate should pass
    is_elig, reason = is_eligible(sample_valid_candidate)
    assert is_elig
    
    # Too junior
    sample_valid_candidate["profile"]["years_of_experience"] = 2.0
    is_elig, reason = is_eligible(sample_valid_candidate)
    assert not is_elig
    assert "insufficient_experience" in reason

def test_scoring_and_reasoning(sample_valid_candidate):
    jd = get_target_jd()
    weights = {
        "skills": 0.35,
        "title": 0.25,
        "experience": 0.15,
        "education": 0.10,
        "location": 0.10,
        "notice_period": 0.05
    }
    parsed = parse_candidate(sample_valid_candidate)
    score, base_score, multiplier, breakdown = score_candidate(parsed, jd, weights)
    
    assert 0.0 <= score <= 1.0
    assert 0.0 <= base_score <= 100.0
    
    reasoning = generate_reasoning(parsed, jd, score, breakdown)
    assert len(reasoning) > 10
    assert "6.9-year" in reasoning or "6.9 years" in reasoning or "6.9" in reasoning

def test_check_honeypot_graduation_mismatch(sample_valid_candidate):
    # Candidate graduated in 2024 (earliest degree end year), but claims 12 YOE.
    # Years since graduation = 2026 - 2024 = 2. 12 YOE is impossible.
    sample_valid_candidate["profile"]["years_of_experience"] = 12.0
    sample_valid_candidate["education"][0]["end_year"] = 2024
    is_hp, reasons = check_honeypot(sample_valid_candidate)
    assert is_hp
    assert any("yoe_exceeds_post_grad_years" in r for r in reasons)

def test_check_honeypot_assessment_mismatch(sample_valid_candidate):
    # Candidate claims advanced/expert in embeddings, but scored 15 on assessment
    sample_valid_candidate["redrob_signals"]["skill_assessment_scores"] = {"embeddings": 15.0}
    is_hp, reasons = check_honeypot(sample_valid_candidate)
    assert is_hp
    assert any("high_prof_low_assessment_score" in r for r in reasons)

def test_dynamic_jd_parser():
    custom_jd = """
    Job Title: Machine Learning Developer
    Company: Tech Labs
    Experience required: 3 to 7 years
    Location: Noida preferred, Bangalore as backup.
    Required skills: PyTorch, Docker, SQL, LLM.
    """
    parsed = parse_jd(custom_jd)
    assert parsed["title"] == "Machine Learning Developer"
    assert parsed["company"] == "Tech Labs"
    assert parsed["min_experience"] == 3.0
    assert parsed["max_experience"] == 7.0
    assert "noida" in parsed["primary_locations"]
    assert "bangalore" in parsed["secondary_locations"]
    assert "pytorch" in parsed["preferred_skills"]

def test_gemini_jd_parser_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    custom_jd = """
    Role: Data Scientist
    Company: Uber
    Experience: 4+ years
    """
    parsed = parse_jd(custom_jd)
    # Falls back to regex parser
    assert parsed["title"] == "Data Scientist"
    assert parsed["company"] == "Uber"
    assert parsed["min_experience"] == 4.0

def test_gemini_jd_parser_mocked(monkeypatch):
    # Mock GEMINI_API_KEY environment variable
    monkeypatch.setenv("GEMINI_API_KEY", "mock_key")
    
    # Mock urllib.request.urlopen to return a mock JSON response
    class MockResponse:
        def read(self):
            return b"""
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "{\\\"title\\\": \\\"Senior AI Research Scientist\\\", \\\"company\\\": \\\"Google DeepMind\\\", \\\"min_experience\\\": 6.0, \\\"max_experience\\\": 12.0, \\\"primary_locations\\\": [\\\"London\\\"], \\\"secondary_locations\\\": [\\\"Mountain View\\\"], \\\"core_required_skills\\\": [\\\"jax\\\", \\\"deep learning\\\"], \\\"preferred_skills\\\": [\\\"rl\\\"], \\\"blacklisted_companies\\\": []}"
                                }
                            ]
                        }
                    }
                ]
            }
            """
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_urlopen(req, timeout=None):
        return MockResponse()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    custom_jd = "Role: Senior AI Research Scientist at Google DeepMind."
    parsed = parse_jd(custom_jd)
    
    assert parsed["title"] == "Senior AI Research Scientist"
    assert parsed["company"] == "Google DeepMind"
    assert parsed["min_experience"] == 6.0
    assert parsed["max_experience"] == 12.0
    assert "london" in parsed["primary_locations"]
    assert "jax" in parsed["core_required_skills"]

def test_evaluation_metrics():
    from evaluate import calculate_dcg, calculate_ndcg, calculate_mrr
    
    # 1. Simple DCG / NDCG test
    relevances = [3, 2, 0, 1]
    
    ndcg_2 = calculate_ndcg(relevances, 2)
    assert 0.0 <= ndcg_2 <= 1.0
    
    # Ideal NDCG must be 1.0
    assert calculate_ndcg([3, 2, 1, 0], 4) == 1.0
    
    # 2. MRR test
    assert calculate_mrr([0, 0, 2, 3], threshold=2) == 1.0 / 3
    assert calculate_mrr([0, 0, 1, 0], threshold=2) == 0.0
    assert calculate_mrr([3, 0, 0, 0], threshold=2) == 1.0

def test_title_blacklist_bug_fix():
    from src.candidate_parser import is_relevant_title
    
    # 1. Title that has blacklist items with no saving grace (should be False)
    assert not is_relevant_title("Civil Engineer and HR Manager")
    assert not is_relevant_title("HR Manager and Writer")
    
    # 2. Title that has blacklist items but also saving grace (should be True)
    assert is_relevant_title("UI Designer and Software Developer")
    assert is_relevant_title("Software Developer and Civil Engineer")
    
    # 3. Standard valid titles
    assert is_relevant_title("Backend Engineer")
    assert is_relevant_title("Machine Learning Scientist")

def test_dynamic_recency_multiplier():
    from src.scorer import score_candidate
    from src.candidate_parser import REFERENCE_DATE
    from datetime import timedelta
    
    jd = get_target_jd()
    weights = {
        "skills": 0.35,
        "title": 0.25,
        "experience": 0.15,
        "education": 0.10,
        "location": 0.10,
        "notice_period": 0.05
    }
    
    def make_candidate_with_date(date_str):
        return {
            "candidate_id": "CAND_TEST",
            "current_title": "Senior AI Engineer",
            "years_of_experience": 7.0,
            "skills": [{"name": "Python", "proficiency": "expert", "duration_months": 24}],
            "education": [],
            "redrob_signals": {
                "last_active_date": date_str,
                "recruiter_response_rate": 0.8,
                "github_activity_score": 10,
                "open_to_work_flag": False,
                "notice_period_days": 15
            }
        }
        
    # Standard configuration
    custom_recency = {
        "30": 1.15,
        "90": 1.05,
        "180": 0.85,
        "default": 0.50
    }
    
    # Test cases matching different thresholds
    cand_30 = make_candidate_with_date((REFERENCE_DATE - timedelta(days=20)).strftime("%Y-%m-%d"))
    cand_90 = make_candidate_with_date((REFERENCE_DATE - timedelta(days=70)).strftime("%Y-%m-%d"))
    cand_180 = make_candidate_with_date((REFERENCE_DATE - timedelta(days=150)).strftime("%Y-%m-%d"))
    cand_default = make_candidate_with_date((REFERENCE_DATE - timedelta(days=200)).strftime("%Y-%m-%d"))
    
    _, _, mult_30, _ = score_candidate(cand_30, jd, weights, recency_config=custom_recency)
    _, _, mult_90, _ = score_candidate(cand_90, jd, weights, recency_config=custom_recency)
    _, _, mult_180, _ = score_candidate(cand_180, jd, weights, recency_config=custom_recency)
    _, _, mult_default, _ = score_candidate(cand_default, jd, weights, recency_config=custom_recency)
    
    assert mult_30 > mult_90 > mult_180 > mult_default




