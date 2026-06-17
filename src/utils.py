import os
import json
import yaml
from datetime import datetime

def load_config(config_path="config.yaml"):
    """Loads configuration yaml file."""
    if not os.path.exists(config_path):
        # Fallback defaults if config does not exist
        return {
            "participant_id": "submission",
            "candidates_file": "data/candidates.jsonl",
            "output_file": "outputs/submission.csv",
            "weights": {
                "skills": 0.35,
                "title": 0.25,
                "experience": 0.15,
                "education": 0.10,
                "location": 0.10,
                "notice_period": 0.05
            },
            "excluded_companies": []
        }
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def parse_date(date_str):
    """Safely parse YYYY-MM-DD date strings."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
