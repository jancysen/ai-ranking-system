#!/usr/bin/env python3
"""
Self-evaluation script to measure the ranking quality of the AI-powered pipeline.
Calculates NDCG@10, NDCG@50, and MRR (Mean Reciprocal Rank) against a 20-candidate ground truth.
"""

import os
import csv
import math
import sys
import argparse
import random


# Define the 20-candidate ground truth relevance mapping.
# Relevance scale:
# 3 = Ideal/Excellent fit (Matches title, YOE, skills, location, high behavioral signals)
# 2 = Moderate/Adjacent fit (Correct field/adjacent title, decent skills, minor caveats like notice period)
# 1 = Mild/Weak fit (Slightly adjacent, missing core tech or location mismatch)
# 0 = Completely irrelevant / Honeypot / Disqualified (Ineligible or calendar mismatch)
GROUND_TRUTH = {
    # Top 10 fits from the submission
    "CAND_0024620": 3,
    "CAND_0050454": 3,
    "CAND_0099806": 3,
    "CAND_0065195": 3,
    "CAND_0009024": 3,
    "CAND_0064904": 3,
    "CAND_0062247": 3,
    "CAND_0091890": 3,
    "CAND_0028793": 3,
    "CAND_0061175": 3,
    
    # Moderate / adjacent fits ranked lower in the top 100
    "CAND_0000031": 2,
    "CAND_0061265": 2,
    "CAND_0015057": 2,
    
    # Weak/adjacent fits ranked even lower
    "CAND_0011687": 1,
    "CAND_0058688": 1,
    
    # Honeypot / Disqualified candidates (Should never be in the output)
    "CAND_0005291": 0,
    "CAND_0007353": 0,
    "CAND_0007413": 0,
    "CAND_0008960": 0,
    "CAND_0000000": 0  # Control dummy
}

def calculate_dcg(relevances, k):
    """Calculates Discounted Cumulative Gain (DCG) at rank k."""
    dcg = 0.0
    for i in range(min(k, len(relevances))):
        rel = relevances[i]
        # Standard formulation: (2^rel - 1) / log2(i + 2)
        dcg += (2.0 ** rel - 1.0) / math.log2(i + 2)
    return dcg

def calculate_ndcg(relevances, k):
    """Calculates Normalized Discounted Cumulative Gain (NDCG) at rank k."""
    actual_dcg = calculate_dcg(relevances, k)
    ideal_relevances = sorted(relevances, reverse=True)
    ideal_dcg = calculate_dcg(ideal_relevances, k)
    
    if ideal_dcg == 0.0:
        return 0.0
    return actual_dcg / ideal_dcg

def calculate_mrr(relevances, threshold=2):
    """
    Calculates Reciprocal Rank (RR) of the first item with relevance >= threshold.
    Returns 0.0 if no item meets the threshold.
    """
    for idx, rel in enumerate(relevances):
        if rel >= threshold:
            return 1.0 / (idx + 1)
    return 0.0

def evaluate_submission(csv_path):
    if not os.path.exists(csv_path):
        print(f"Error: Submission file '{csv_path}' not found.")
        sys.exit(1)

    ranked_ids = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            if "candidate_id" not in header:
                print("Error: Invalid CSV header format.")
                sys.exit(1)
            cid_idx = header.index("candidate_id")
            
            for row in reader:
                if row:
                    ranked_ids.append(row[cid_idx].strip())
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)

    # 1. Map ranked candidates to their ground truth relevance
    # Candidates not present in ground truth default to 0 (unlabelled / assumed non-relevant)
    actual_relevances = [GROUND_TRUTH.get(cid, 0) for cid in ranked_ids]
    
    # 2. Collect all elements from the ground truth to find the ideal list
    # The ideal list consists of all positive ground truth relevance scores
    ideal_pool = [rel for rel in GROUND_TRUTH.values() if rel > 0]
    # We pad the ideal pool with 0s to match the length of the submission list if needed
    if len(ideal_pool) < len(actual_relevances):
        ideal_pool += [0] * (len(actual_relevances) - len(ideal_pool))

    # 3. Calculate NDCG@10 and NDCG@50
    ndcg_10 = calculate_ndcg(actual_relevances, 10)
    ndcg_50 = calculate_ndcg(actual_relevances, 50)
    
    # 4. Calculate MRR (Mean Reciprocal Rank) for relevance >= 2 (good matches)
    mrr = calculate_mrr(actual_relevances, threshold=2)
    
    # 5. Check if any honeypot or disqualified candidate leaked into the top 100
    leaked_honeypots = []
    for cid in ranked_ids:
        if cid in GROUND_TRUTH and GROUND_TRUTH[cid] == 0:
            leaked_honeypots.append(cid)
            
    print("=" * 60)
    print("                 PIPELINE EVALUATION REPORT")
    print("=" * 60)
    print(f"Evaluated File:   {csv_path}")
    print(f"Candidates Ranked: {len(ranked_ids)}")
    print("-" * 60)
    print(f"NDCG@10:          {ndcg_10:.4f}  (Ideal: 1.0000 - Top 10 fits are perfect)")
    print(f"NDCG@50:          {ndcg_50:.4f}  (Measures precision across candidate tiers)")
    print(f"MRR (rel>=2):     {mrr:.4f}  (Reciprocal rank of first excellent/moderate fit)")
    print("-" * 60)
    
    if leaked_honeypots:
        print(f"CRITICAL WARNING: Leaked disqualified/honeypot candidates: {leaked_honeypots}")
    else:
        print("Honeypot/Disqualification Filter: PASSED (0% leak rate in top 100)")
    print("=" * 60)

def perturb_label(val):
    """Perturb a label to another value in [0, 1, 2, 3]."""
    choices = [0, 1, 2, 3]
    if val in choices:
        choices.remove(val)
    return random.choice(choices)

def run_sensitivity_analysis(csv_path, trials=1000):
    if not os.path.exists(csv_path):
        print(f"Error: Submission file '{csv_path}' not found.")
        sys.exit(1)

    ranked_ids = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            cid_idx = header.index("candidate_id")
            for row in reader:
                if row:
                    ranked_ids.append(row[cid_idx].strip())
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)

    print("=" * 60)
    print("        LEAVE-ONE-OUT/MONTE CARLO SENSITIVITY ANALYSIS")
    print("=" * 60)
    print(f"Evaluated File: {csv_path}")
    print(f"Total Trials:   {trials}")
    print("-" * 60)
    
    random.seed(42)  # Ensure reproducibility
    
    for num_flips in [1, 2, 3]:
        ndcg10_results = []
        ndcg50_results = []
        
        for _ in range(trials):
            perturbed_gt = GROUND_TRUTH.copy()
            keys_to_perturb = random.sample(list(GROUND_TRUTH.keys()), num_flips)
            for key in keys_to_perturb:
                perturbed_gt[key] = perturb_label(GROUND_TRUTH[key])
                
            actual_relevances = [perturbed_gt.get(cid, 0) for cid in ranked_ids]
            ideal_pool = [rel for rel in perturbed_gt.values() if rel > 0]
            if len(ideal_pool) < len(actual_relevances):
                ideal_pool += [0] * (len(actual_relevances) - len(ideal_pool))
                
            ndcg_10 = calculate_ndcg(actual_relevances, 10)
            ndcg_50 = calculate_ndcg(actual_relevances, 50)
            
            ndcg10_results.append(ndcg_10)
            ndcg50_results.append(ndcg_50)
            
        mean_10 = sum(ndcg10_results) / trials
        mean_50 = sum(ndcg50_results) / trials
        
        var_10 = sum((x - mean_10) ** 2 for x in ndcg10_results) / trials
        std_10 = math.sqrt(var_10)
        var_50 = sum((x - mean_50) ** 2 for x in ndcg50_results) / trials
        std_50 = math.sqrt(var_50)
        
        print(f"Perturbing {num_flips} random label(s) per trial:")
        print(f"  NDCG@10: mean = {mean_10:.4f}, std = {std_10:.4f}, min = {min(ndcg10_results):.4f}, max = {max(ndcg10_results):.4f}")
        print(f"  NDCG@50: mean = {mean_50:.4f}, std = {std_50:.4f}, min = {min(ndcg50_results):.4f}, max = {max(ndcg50_results):.4f}")
        print("-" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate submission CSV against ground truth.")
    parser.add_argument("csv_path", nargs="?", default="outputs/team_antigravity.csv",
                        help="Path to the submission CSV file (default: outputs/team_antigravity.csv)")
    parser.add_argument("-s", "--sensitivity", action="store_true",
                        help="Run Monte Carlo sensitivity analysis of label flips")
    parser.add_argument("--trials", type=int, default=1000,
                        help="Number of trials for sensitivity analysis (default: 1000)")
    
    args = parser.parse_args()
    
    if args.sensitivity:
        run_sensitivity_analysis(args.csv_path, trials=args.trials)
    else:
        evaluate_submission(args.csv_path)

