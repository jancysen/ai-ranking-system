import os
import json
import csv
import time
from src.utils import load_config
from src.jd_parser import get_target_jd
from src.candidate_parser import check_honeypot, is_eligible, parse_candidate
from src.scorer import score_candidate, generate_reasoning

def run_pipeline(candidates_path, output_path, config_path="config.yaml"):
    """
    Orchestrates the candidate ranking pipeline from end to end.
    """
    start_time = time.time()
    print("="*60)
    print("AI-Powered Candidate Ranking System Pipeline")
    print("="*60)
    print(f"Candidates file: {candidates_path}")
    print(f"Output file: {output_path}")
    
    # 1. Load config and job description
    config = load_config(config_path)
    weights = config.get("weights", {
        "skills": 0.35,
        "title": 0.25,
        "experience": 0.15,
        "education": 0.10,
        "location": 0.10,
        "notice_period": 0.05
    })
    excluded_companies = config.get("excluded_companies", [])
    semantic_weight = config.get("semantic_re_rank_weight", 0.2)

    
    # Get the parsed job description
    jd = get_target_jd()
    print(f"Target JD: {jd['title']} at {jd['company']}")
    
    # 2. Process candidate pool line by line to keep memory low
    scored_candidates = []
    scanned_count = 0
    honeypot_count = 0
    ineligible_count = 0
    passed_count = 0
    
    # We will read candidates.jsonl line-by-line
    if not os.path.exists(candidates_path):
        raise FileNotFoundError(f"Candidate pool file not found: {candidates_path}")
        
    # Check if the file is a JSON array (like sample_candidates.json) or JSONL
    is_json_array = candidates_path.endswith(".json")
    
    with open(candidates_path, "r", encoding="utf-8") as f:
        if is_json_array:
            try:
                candidates_list = json.load(f)
            except Exception as e:
                print(f"Failed to parse as JSON array: {e}. Trying line-by-line.")
                f.seek(0)
                candidates_list = None
        else:
            candidates_list = None
            
        def get_candidates():
            if candidates_list is not None:
                for c in candidates_list:
                    yield c
            else:
                for line in f:
                    if line.strip():
                        yield json.loads(line)
                        
        for raw_cand in get_candidates():
            scanned_count += 1
            
            # A. Honeypot check
            is_hp, hp_reasons = check_honeypot(raw_cand)
            if is_hp:
                honeypot_count += 1
                continue
                
            # B. Eligibility check
            is_elig, elig_reason = is_eligible(raw_cand, excluded_companies)
            if not is_elig:
                ineligible_count += 1
                continue
                
            # C. Parse candidate
            cand = parse_candidate(raw_cand)
            passed_count += 1
            
            # D. Score candidate
            score, base_score, behavioral_multiplier, breakdown = score_candidate(cand, jd, weights)
            
            scored_candidates.append({
                "candidate_id": cand["candidate_id"],
                "score": score,
                "breakdown": breakdown,
                "parsed_record": cand
            })
            
            # Logging progress
            if scanned_count % 20000 == 0:
                print(f"Processed {scanned_count} candidates...")
                
    print(f"\nProcessing summary:")
    print(f"  - Total candidates scanned: {scanned_count}")
    print(f"  - Honeypots filtered out: {honeypot_count}")
    print(f"  - Ineligible candidates filtered: {ineligible_count}")
    print(f"  - Valid candidates scored: {passed_count}")
    
    # 3. First Stage Retrieval (Sort by base rule score to extract top 1,000)
    print("\nSorting candidates for retrieval...")
    scored_candidates.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    
    # Take top 1,000 candidates for semantic re-ranking
    re_ranking_limit = min(1000, len(scored_candidates))
    top_candidates = scored_candidates[:re_ranking_limit]
    remaining_candidates = scored_candidates[re_ranking_limit:]
    
    # 4. Second Stage Semantic Re-ranking
    if re_ranking_limit > 0:
        print(f"Running Stage 2: Semantic Re-ranking on top {re_ranking_limit} candidates...")
        try:
            from src.matcher import get_sentence_transformer
            from sentence_transformers import util
            
            re_rank_start = time.time()
            model = get_sentence_transformer("models/all-MiniLM-L6-v2")
            
            # Construct a comprehensive JD text representation and embed once
            jd_semantic_text = f"{jd['title']}. Core requirements: {', '.join(jd['core_required_skills'])}. Nice-to-haves: {', '.join(jd['preferred_skills'])}."
            jd_emb = model.encode(jd_semantic_text, convert_to_tensor=True)
            
            # Collect all candidate texts
            profile_texts = []
            for item in top_candidates:
                cand = item["parsed_record"]
                profile_text = f"{cand['current_title']}. Headline: {cand['headline']}. Summary: {cand['summary']}."
                profile_texts.append(profile_text)
                
            # Batch encode all candidate profiles in a single call
            print(f"Batch encoding {len(profile_texts)} profiles on CPU...")
            cand_embs = model.encode(profile_texts, convert_to_tensor=True, show_progress_bar=False)
            
            # Compute similarities
            similarities = util.cos_sim(cand_embs, jd_emb)
            
            for idx, item in enumerate(top_candidates):
                similarity = similarities[idx].item()
                # Scale similarity to [0, 1]
                similarity = max(0.0, min(similarity, 1.0))
                
                # Update score: blend weighted rule-based fit and semantic similarity match
                combined_score = (item["score"] * (1.0 - semantic_weight)) + (similarity * semantic_weight)
                item["score"] = combined_score

                item["breakdown"]["semantic_similarity"] = similarity
                
            print(f"Semantic re-ranking completed in {time.time() - re_rank_start:.2f} seconds.")
        except Exception as e:
            print(f"WARNING: Semantic re-ranking failed. Falling back to rule-based retrieval. Error: {e}")
            
    # Combine back and re-sort
    all_scored = top_candidates + remaining_candidates
    # Sort by 4-decimal rounded score descending, and tie-break by candidate_id ascending.
    # This aligns the sorting order exactly with how scores are printed in the final CSV,
    # ensuring the validator's tie-break check is correctly satisfied.
    all_scored.sort(key=lambda x: (-round(x["score"], 4), x["candidate_id"]))
    
    # 5. Generate Top 100 Shortlist and reasonings
    shortlist = all_scored[:100]
    
    # Ensure we have at least 100 candidates
    if len(shortlist) < 100:
        print(f"WARNING: Only {len(shortlist)} candidates passed filters. Ranking all of them.")
        
    # Write output to CSV
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as out_f:
        writer = csv.writer(out_f)
        # Header
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for idx, item in enumerate(shortlist):
            rank = idx + 1
            cid = item["candidate_id"]
            # Round score to 4 decimal places as in sample_submission.csv
            score_rounded = round(item["score"], 4)
            
            # Generate reasoning
            reasoning = generate_reasoning(
                item["parsed_record"],
                jd,
                item["score"],
                item["breakdown"]
            )
            
            writer.writerow([cid, rank, f"{score_rounded:.4f}", reasoning])
            
    elapsed_time = time.time() - start_time
    print("="*60)
    print(f"Pipeline executed successfully in {elapsed_time:.2f} seconds!")
    print(f"Results saved to: {output_path}")
    print("="*60)
    return output_path
