import streamlit as st
import json
import os
import pandas as pd
import time
from src.jd_parser import parse_jd, get_target_jd
from src.candidate_parser import check_honeypot, is_eligible, parse_candidate
from src.scorer import score_candidate, generate_reasoning
from src.matcher import compute_semantic_similarity

# Configure page
st.set_page_config(
    page_title="Redrob AI - Candidate Ranking Sandbox",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title & Description
st.title("🎯 Redrob AI - Candidate Discovery & Ranking Sandbox")
st.markdown("""
This interactive sandbox demonstrates our AI-powered candidate matching and ranking pipeline.
It screens out **simulated honeypots (impossible data)**, filters out **ineligible profiles** (experience range, consulting-only career histories),
and ranks candidates using a **two-stage hybrid semantic + behavioral scorer**.
""")

# Setup default JD text
DEFAULT_JD_TEXT = """Job Description: Senior AI Engineer — Founding Team
Company: Redrob AI (Series A AI-native talent intelligence platform)
Location: Pune/Noida, India (Hybrid)
Employment Type: Full-time
Experience Required: 5–9 years

What we actually need:
- Production experience with embeddings-based retrieval systems (sentence-transformers, OpenAI embeddings, BGE, FAISS, Pinecone, etc.).
- Strong Python skills.
- Experience with ranking evaluation metrics (NDCG, MRR, MAP).
- LLM fine-tuning experience (LoRA, QLoRA, PEFT) is a plus.
- Exclude: candidates who have spent their career only in academic labs, LangChain-only developers without pre-LLM ML experience, or candidates who have ONLY worked at IT consulting services firms (TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini, etc.).
"""

# Sidebar for controls
st.sidebar.header("⚙️ Configuration")

# 1. Dataset Selection
st.sidebar.subheader("1. Candidate Database")
data_option = st.sidebar.selectbox(
    "Select candidate pool source",
    ["Use 50-Candidate Sample (Fast)", "Upload Custom JSONL File"]
)

uploaded_file = None
if data_option == "Upload Custom JSONL File":
    uploaded_file = st.sidebar.file_uploader("Upload candidates.jsonl", type=["jsonl", "json"])

# 2. Weights sliders
st.sidebar.subheader("2. Adjust Scoring Weights")
w_skills = st.sidebar.slider("Skills Alignment Weight", 0.0, 1.0, 0.35, 0.05)
w_title = st.sidebar.slider("Title Relevance Weight", 0.0, 1.0, 0.25, 0.05)
w_exp = st.sidebar.slider("Experience Align Weight", 0.0, 1.0, 0.15, 0.05)
w_edu = st.sidebar.slider("Education Tier Weight", 0.0, 1.0, 0.10, 0.05)
w_loc = st.sidebar.slider("Location Proximity Weight", 0.0, 1.0, 0.10, 0.05)
w_notice = st.sidebar.slider("Notice Period Weight", 0.0, 1.0, 0.05, 0.05)

# Calculate sum and warn if not 1.0
weights_sum = w_skills + w_title + w_exp + w_edu + w_loc + w_notice
st.sidebar.markdown(f"**Total Weights Sum**: `{weights_sum:.2f}`")
if abs(weights_sum - 1.0) > 0.001:
    st.sidebar.warning("⚠️ Weights should sum to 1.0! Current scores will be auto-normalized.")

weights = {
    "skills": w_skills / weights_sum,
    "title": w_title / weights_sum,
    "experience": w_exp / weights_sum,
    "education": w_edu / weights_sum,
    "location": w_loc / weights_sum,
    "notice_period": w_notice / weights_sum
}

use_semantic = st.sidebar.checkbox("Enable Stage-2 Semantic Re-ranking", value=True)
semantic_weight = 0.20
if use_semantic:
    semantic_weight = st.sidebar.slider("Semantic Blend Weight (Stage-2)", 0.0, 1.0, 0.20, 0.05)


# Main Panel layout
col_jd, col_results = st.columns([1, 2])

with col_jd:
    st.header("📝 Job Description (JD)")
    jd_text_input = st.text_area(
        "Paste Job Description text here:",
        value=DEFAULT_JD_TEXT,
        height=400
    )
    
    st.subheader("Parsed JD Requirements")
    # Dynamic parsing
    parsed_jd = parse_jd(jd_text_input)
    st.write(f"**Extracted Title**: `{parsed_jd.get('title')}`")
    st.write(f"**Stated Experience**: `{parsed_jd.get('min_experience')} - {parsed_jd.get('max_experience')} years`")
    st.write(f"**Primary Hubs**: `{', '.join(parsed_jd.get('primary_locations', []))}`")
    st.write(f"**Core Skills Detected**: `{', '.join(parsed_jd.get('core_required_skills', [])[:8])}...`")

with col_results:
    st.header("🏆 Ranked Candidate Results")
    
    if st.button("🚀 Run Discovery & Ranking Pipeline", type="primary"):
        # Load candidates
        candidates = []
        try:
            if data_option == "Use 50-Candidate Sample (Fast)":
                sample_path = "data/sample_candidates.json"
                if os.path.exists(sample_path):
                    with open(sample_path, "r", encoding="utf-8") as f:
                        candidates = json.load(f)
                else:
                    st.error(f"Sample candidates file {sample_path} not found.")
            elif uploaded_file is not None:
                # Read JSONL uploaded file
                lines = uploaded_file.getvalue().decode("utf-8").split("\n")
                for line in lines:
                    if line.strip():
                        candidates.append(json.loads(line))
            else:
                st.info("Please upload a candidates file in the sidebar first.")
                st.stop()
        except Exception as e:
            st.error(f"Error loading candidates: {e}")
            st.stop()
            
        if not candidates:
            st.warning("No candidates loaded.")
            st.stop()
            
        st.info(f"Loaded {len(candidates)} candidates. Running pipeline...")
        
        # Pipeline execution
        start_time = time.time()
        scored_candidates = []
        honeypot_count = 0
        ineligible_count = 0
        passed_count = 0
        
        # Excluded companies list from config
        excluded_companies = get_target_jd()["blacklisted_companies"]
        
        # Ingestion & Screening
        for raw_cand in candidates:
            # 1. Honeypot Filter
            is_hp, _ = check_honeypot(raw_cand)
            if is_hp:
                honeypot_count += 1
                continue
                
            # 2. Eligibility
            is_elig, _ = is_eligible(raw_cand, excluded_companies)
            if not is_elig:
                ineligible_count += 1
                continue
                
            cand = parse_candidate(raw_cand)
            passed_count += 1
            
            # Base scoring
            score, base_score, multiplier, breakdown = score_candidate(cand, parsed_jd, weights)
            
            scored_candidates.append({
                "candidate_id": cand["candidate_id"],
                "name": cand["name"],
                "yoe": cand["years_of_experience"],
                "title": cand["current_title"],
                "location": cand["location"],
                "score": score,
                "base_score": base_score,
                "multiplier": multiplier,
                "breakdown": breakdown,
                "parsed_record": cand
            })
            
        # Retrieval sorting
        scored_candidates.sort(key=lambda x: (-x["score"], x["candidate_id"]))
        
        # Stage-2 Semantic Re-ranking (Top 50 for the web interface)
        if use_semantic and scored_candidates:
            st.write("Running Stage-2 Semantic Re-ranking on top candidates...")
            top_subset = scored_candidates[:50]
            jd_semantic_text = f"{parsed_jd['title']} {' '.join(parsed_jd['core_required_skills'])} {' '.join(parsed_jd['preferred_skills'])}"
            
            for item in top_subset:
                cand_text = f"{item['title']} {item['parsed_record'].get('headline', '')} {item['parsed_record'].get('summary', '')}"
                # Compute local or online cosine sim
                sem_sim = compute_semantic_similarity(cand_text, jd_semantic_text)
                
                # Combine: blend original score and semantic similarity
                combined_score = (item["score"] * (1.0 - semantic_weight)) + (sem_sim * semantic_weight)
                item["score"] = combined_score

                item["breakdown"]["semantic_similarity"] = sem_sim
                
            # Re-sort
            scored_candidates.sort(key=lambda x: (-x["score"], x["candidate_id"]))
            
        elapsed = time.time() - start_time
        
        # Metrics Row
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Scanned", len(candidates))
        col_m2.metric("Filtered Honeypots", honeypot_count)
        col_m3.metric("Filtered Ineligible", ineligible_count)
        col_m4.metric("Time Taken (s)", f"{elapsed:.3f}s")
        
        # Display Table
        st.subheader("Top Ranked Shortlist")
        
        display_data = []
        for idx, item in enumerate(scored_candidates[:15]):
            # Generate reasoning
            reasoning = generate_reasoning(
                item["parsed_record"],
                parsed_jd,
                item["score"],
                item["breakdown"]
            )
            
            display_data.append({
                "Rank": idx + 1,
                "Candidate ID": item["candidate_id"],
                "Name": item["name"],
                "Current Title": item["title"],
                "YOE": f"{item['yoe']:.1f}",
                "Location": item["location"],
                "Fit Score": f"{item['score']:.4f}",
                "Reasoning": reasoning,
                "record": item["parsed_record"]
            })
            
        if display_data:
            df = pd.DataFrame(display_data).drop(columns=["record"])
            st.dataframe(df, use_container_width=True)
            
            # Interactive Explorer
            st.subheader("🔍 Deep Profile Explorer")
            selected_name = st.selectbox(
                "Select a candidate to view their complete profile details:",
                [d["Name"] for d in display_data]
            )
            
            # Find record
            selected_item = next(d for d in display_data if d["Name"] == selected_name)
            record = selected_item["record"]
            
            col_details1, col_details2 = st.columns(2)
            with col_details1:
                st.write(f"### Profile: {record['name']}")
                st.write(f"**Headline**: {record['headline']}")
                st.write(f"**Current Company**: {record['current_company']} ({record['current_company_size']} size)")
                st.write(f"**Location**: {record['location']}, {record['country']}")
                st.write(f"**Summary**: {record['summary']}")
                
                st.write("#### Career History")
                for job in record["career_history"]:
                    st.write(f"- **{job['title']}** at **{job['company']}** ({job['duration_months']} mos)")
                    st.caption(job["description"])
                    
            with col_details2:
                st.write("#### Skills & Proficiencies")
                skills_df = pd.DataFrame(record["skills"])
                if not skills_df.empty:
                    st.dataframe(skills_df[["name", "proficiency", "duration_months", "endorsements"]], use_container_width=True)
                    
                st.write("#### Redrob Platform Behavioral Signals")
                sig = record["redrob_signals"]
                st.write(f"- **Profile Completeness**: `{sig['profile_completeness_score']}%`")
                st.write(f"- **Recruiter Response Rate**: `{int(sig['recruiter_response_rate']*100)}%` (Avg response: `{sig['avg_response_time_hours']}h`)")
                st.write(f"- **GitHub Activity Score**: `{sig['github_activity_score']}`")
                st.write(f"- **Interview Attendance Rate**: `{int(sig['interview_completion_rate']*100)}%`")
                st.write(f"- **Offer Acceptance Rate**: `{int(sig['offer_acceptance_rate']*100)}%`" if sig['offer_acceptance_rate'] != -1 else "Offer Acceptance: `No history`")
                st.write(f"- **Notice Period**: `{sig['notice_period_days']} days`")
                
                # Show assessment scores
                if sig.get("skill_assessment_scores"):
                    st.write("##### Skill Assessment Scores:")
                    for sk, sc in sig["skill_assessment_scores"].items():
                        st.write(f"  * {sk}: `{sc}/100`")
        else:
            st.warning("No candidates matched the current criteria.")
