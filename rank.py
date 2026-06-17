import argparse
import sys
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
    
    args = parser.parse_args()
    
    try:
        run_pipeline(args.candidates, args.out)
    except Exception as e:
        print(f"Error running ranking pipeline: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
