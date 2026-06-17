# AI-Powered Candidate Ranking System

This repository contains our submission for **The Data & AI Challenge**. The system parses a job description, screens out simulated "honeypot" profiles, filters candidate eligibility based on experience level and company history, and outputs a trusted, ranked list of the top 100 candidates with fact-based natural language reasonings.

The pipeline is optimized to run completely offline on CPU, matching the strict compute constraints of the competition.

---

## Technical Overview & Design

### 1. Ingestion & Pre-Screening
* **Honeypot Filter**: Detects simulated traps by verifying timeline integrity (job start dates vs. duration), checking for "expert" skills with 0 months experience, validating graduation dates against stated years of experience (YOE), and identifying skill-assessment contradictions on the platform. Any anomalous profile is immediately filtered out to guarantee a **0% honeypot rate** in the top 100.
* **Experience & Title Screening**: Excludes candidates with YOE < 3.5 or YOE > 18. Non-technical titles (e.g. HR Manager, Graphic Designer, Content Writer) are strictly disqualified.
* **Consulting Firm Filter**: Disqualifies candidates whose entire career history consists *only* of IT consulting/service firms (TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini, etc.), adhering to the preferences outlined in the Job Description.

### 2. Hybrid Scoring Model
Scoring is divided into a base weighted match and a multiplicative behavioral modifier:
* **Base Score (100 pts max)**:
  * **Skills Match (35%)**: Checks candidate profile against 17 core required and 11 preferred skills, weighted by proficiency (Expert to Beginner), duration (capped at 3 years), and endorsements, plus Redrob platform assessment bonuses.
  * **Title Relevance (25%)**: Computes similarity of the current title and history (max match) to target roles (e.g. AI Engineer, Backend Engineer, ML Engineer).
  * **Seniority Target (15%)**: Grants maximum points to the 5-9 years experience band, with a smooth decay outside.
  * **Education & Location (10% + 10%)**: Rewards Tier-1/Tier-2 schools. Primary points are awarded to Noida/Pune hubs, followed by secondary cities and relocation preferences.
  * **Notice Period (5%)**: Prefers shorter notice periods (<= 30 days).
* **Behavioral Multiplier (0.4 to 1.3)**:
  * Combines response rate, active recency (penalizing inactivity > 6 months), GitHub activity score, interview completion rate, and offer acceptance history.

### 3. Fact-Based Reasoning Generator
Generates natural-sounding 1-2 sentence notes for the top 100 candidates. The generation is **100% deterministic and fact-based**, pulling values (current title, YOE, exact matched skills, location, notice period, and responsiveness) directly from the profile to ensure zero hallucinations and high style variation.

---

## Directory Structure

```
.
├── README.md                      # Setup and design documentation
├── requirements.txt               # Package dependencies
├── config.yaml                    # System weights and exclusions
├── submission_metadata.yaml       # Hackathon portal metadata
├── rank.py                        # Root CLI entry wrapper
├── data/                          # Folder for raw datasets (gitignored)
│   ├── candidates.jsonl
│   └── ...
├── src/
│   ├── __init__.py
│   ├── utils.py                   # Date & config utilities
│   ├── jd_parser.py               # Job description schema representation
│   ├── candidate_parser.py        # Honeypot & eligibility screening
│   ├── matcher.py                 # Individual match scoring features
│   ├── scorer.py                  # Scorer engine and reasoning generator
│   └── pipeline.py                # End-to-end pipeline orchestrator
├── outputs/
│   └── team_antigravity.csv       # Final ranked deliverable (validator approved)
├── docs/
│   └── approach.md                # Markdown slides for PDF deck conversion
└── tests/
    └── test_pipeline.py           # Pytest unit test suite
```

---

## Setup & Installation

1. **Prerequisites**: Python 3.10+
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Download dataset**: Place `candidates.jsonl` (and other challenge files) inside the `data/` folder.

---

## Running the Pipeline

To run the candidate ranking pipeline end-to-end and generate the output CSV, run the following command from the repository root:

```bash
python rank.py --candidates data/candidates.jsonl --out outputs/team_antigravity.csv
```

### Compute Statistics (100K Candidate Pool)
* **Hardware**: CPU Only, 8 Cores, 16 GB RAM
* **Runtime**: **~13 seconds** (well within the 5-minute limit)
* **Peak Memory**: ~120 MB RAM (due to line-by-line streaming)

---

## Running Tests

To execute the unit test suite:

```bash
python -m pytest tests/
```
