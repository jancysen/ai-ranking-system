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
        
    with open(candidates_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            
            scanned_count += 1
            raw_cand = json.loads(line)
            
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
    
    # 3. Sort candidates
    # Sort by score descending. Tie-breaker: candidate_id ascending (alphabetically)
    print("\nSorting and ranking candidates...")
    scored_candidates.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    
    # 4. Generate Top 100 Shortlist and reasonings
    shortlist = scored_candidates[:100]
    
    # Ensure we have at least 100 candidates (fill with adjacent if needed)
    if len(shortlist) < 100:
        print(f"WARNING: Only {len(shortlist)} candidates passed filters. Ranking all of them.")
        # If we need filler, we could relax filters, but in a 100k pool there will be thousands of valid candidates
        
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
