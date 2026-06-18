import argparse
import sys
import os
from src.pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser(
        description="Rank candidates against a job description offline."
    )
    parser.add_argument(
        "--candidates",
        type=str,
        default="data/candidates.jsonl",
        help="Path to candidate jsonl database."
    )
    parser.add_argument(
        "--out",
        type=str,
        default="outputs/team_antigravity.csv",
        help="Output CSV file path."
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run quickly on sample data (data/sample_candidates.json) for testing."
    )
    parser.add_argument(
        "--jd",
        type=str,
        default=None,
        help="Path to custom job description text file to parse and rank against."
    )
    
    args = parser.parse_args()
    
    candidates_file = args.candidates
    output_file = args.out
    
    if args.sample:
        candidates_file = "data/sample_candidates.json"
        output_file = "outputs/sample_ranked.csv"
        print("Running pipeline on SAMPLE data...")
        
    try:
        run_pipeline(candidates_file, output_file, jd_path=args.jd)
    except Exception as e:
        print(f"Error running ranking pipeline: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
