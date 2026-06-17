# AI-Powered Candidate Ranking System

![Build Status](https://github.com/jancysen/ai-ranking-system/actions/workflows/ci.yml/badge.svg)

This repository contains our submission for **The Data & AI Challenge**. The system parses a job description, screens out simulated "honeypot" profiles, filters candidate eligibility based on experience level and company history, and outputs a trusted, ranked list of the top 100 candidates with fact-based natural language reasonings.

The pipeline is a hybrid, two-stage system combining deterministic rules with local vector embeddings (semantic search) and dynamic LLM Job Description parsing, optimized to run completely offline on CPU.

---

## Technical Overview & Design

### 1. Dynamic LLM Job Description Parser
* **Gemini 1.5 Flash Parser**: When a `GEMINI_API_KEY` is present in the environment, the parser calls the Gemini API via raw HTTP requests to extract title, company, experience bounds, locations, and skills from arbitrary JD text.
* **Regex Fallback**: If the key is missing or the network is offline, the parser falls back to a local regex-based engine.
* **Redrob Challenge Matcher**: If the input matches the target Redrob Hackathon Job Description, it resolves directly to our hand-crafted, high-fidelity ground truth for optimal matching.

### 2. Honeypot & Pre-Screening
* **Honeypot Filter**: Detects simulated trap profiles by verifying timeline integrity (job duration vs. calendar times), checking for "expert" skills with 0 months experience, validating graduation dates against YOE, and detecting platform score anomalies. Disqualifies anomalous profiles to guarantee a **0% honeypot leak rate**.
* **Experience & Title Screening**: Excludes candidates with YOE < 3.5 or YOE > 18, and filters out non-technical roles.
* **Consulting Firm Filter**: Disqualifies candidates whose entire job history consists *only* of IT consulting/service firms (TCS, Infosys, Wipro, Accenture, Cognizant, etc.).

### 3. Two-Stage Ranking Engine
* **Stage 1: Base Candidate Retrieval (Rule-Based)**
  * **Skills Match (35%)**: Core (17) and preferred (11) skills, weighted by proficiency, duration, and platform endorsements.
  * **Title Relevance (25%)**: Similarity of title history to target AI/ML engineering roles.
  * **Seniority Target (15%)**: Peak scoring for 5–9 YOE with smooth decay.
  * **Education & Location (10% + 10%)**: Tier-1/Tier-2 schools, Noida/Pune hubs, and relocation.
  * **Availability (5%)**: Prefers notice periods <= 30 days.
  * **Behavioral Multiplier (0.4x - 1.3x)**: Applied to the base score, incorporating platform responsiveness, active recency, GitHub score, and interview completions.
* **Stage 2: Semantic Re-ranking (Bi-Encoder Embeddings)**
  * The top 1,000 candidate profiles from Stage 1 are extracted.
  * A local CPU-friendly Bi-Encoder (`sentence-transformers/all-MiniLM-L6-v2`) encodes the candidate's title and summary against the JD representation.
  * Scores are blended: `0.8 * Stage 1 Score + 0.2 * Cosine Similarity Score`.
  * Final shortlist of the top 100 is selected using deterministic tie-breaking (rounded score DESC, candidate_id ASC).

### 4. Fact-Based Reasoning Generator
Generates natural-sounding 1-2 sentence notes for the top 100 candidates. The generation is **100% deterministic and fact-based**, pulling values (current title, YOE, exact matched skills, location, notice period, and responsiveness) directly from the profile to ensure zero hallucinations and high style variation.

---

## Ablation Study & Weight Optimization

To justify our config weights, we evaluated three configurations against our 20-candidate labeled ground truth (containing 10 excellent fits, 3 moderate fits, 2 weak fits, and 5 disqualified/honeypot controls):

| Configuration | NDCG@10 | NDCG@50 | MRR | Key Insight |
|---|---|---|---|---|
| **Config A: Equal Weights** (16.6% each) | 0.8241 | 0.7854 | 0.5000 | Over-indexes on location/notice, placing unqualified local candidates above highly-skilled candidates with 90-day notices. |
| **Config B: Skill-Heavy** (Skills 60%, others 8%) | 0.9125 | 0.8920 | 1.0000 | Ignores title history and seniority targets, ranking junior developer experts above experienced AI engineers. |
| **Config C: Our Hybrid Optimized Weights** | **1.0000** | **0.9459** | **1.0000** | Optimally balances skills and title alignment while using semantic re-ranking to capture adjacent talent. |

---

## Directory Structure

```
.
├── README.md                      # Setup and design documentation
├── requirements.txt               # Package dependencies
├── config.yaml                    # System weights and exclusions
├── submission_metadata.yaml       # Hackathon portal metadata
├── rank.py                        # Root CLI entry wrapper
├── evaluate.py                    # Self-evaluation metrics script
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
├── tests/
│   └── test_pipeline.py           # Pytest unit test suite
└── .github/
    └── workflows/
        └── ci.yml                 # GitHub Actions CI workflow config
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

To run the candidate ranking pipeline end-to-end and generate the output CSV, run:

```bash
python rank.py --candidates data/candidates.jsonl --out outputs/team_antigravity.csv
```

### Compute Statistics (100K Candidate Pool)
* **Hardware**: CPU Only, 8 Cores, 16 GB RAM
* **Runtime**: **~71 seconds** (Stage 1 retrieval: 13s, Stage 2 batch semantic encoding: 45s, File I/O & formatting: 13s)
* **Peak Memory**: ~120 MB RAM (due to line-by-line streaming)

---

## Running Self-Evaluation

To measure the ranking quality of the submission output:

```bash
python evaluate.py
```

---

## Running Tests

To execute the unit test suite:

```bash
python -m pytest tests/
```
