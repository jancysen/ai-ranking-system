import re

def get_target_jd():
    """Returns the parsed structured representation of the target Redrob JD."""
    return {
        "title": "Senior AI Engineer — Founding Team",
        "company": "Redrob AI",
        "min_experience": 5.0,
        "max_experience": 9.0,
        "primary_locations": ["pune", "noida"],
        "secondary_locations": ["delhi ncr", "delhi", "gurgaon", "hyderabad", "bangalore", "mumbai"],
        "core_required_skills": [
            "embeddings", "vector search", "retrieval", "vector database",
            "sentence-transformers", "pinecone", "weaviate", "qdrant",
            "milvus", "opensearch", "elasticsearch", "faiss", "python",
            "ndcg", "mrr", "map", "evaluation frameworks", "ranking evaluation"
        ],
        "preferred_skills": [
            "llm", "fine-tuning", "lora", "qlora", "peft", "learning to rank",
            "xgboost", "hr-tech", "marketplace", "nlp", "distributed systems"
        ],
        "blacklisted_companies": [
            "tcs", "tata consultancy services", "infosys", "wipro", "accenture",
            "cognizant", "capgemini", "hcl", "tech mahindra", "l&t", "lnt", "mindtree", "mphasis"
        ]
    }

def parse_jd(jd_text):
    """
    Tries to extract key structured requirements from arbitrary JD text dynamically.
    If it matches the Redrob hackathon JD, it returns the standard target JD.
    """
    if not jd_text or not jd_text.strip():
        return get_target_jd()
        
    jd_lower = jd_text.lower()
    
    # Check if this is the target Redrob hackathon JD
    if "redrob" in jd_lower and "founding team" in jd_lower:
        return get_target_jd()
        
    parsed = {
        "title": "Dynamic Position",
        "company": "Dynamic Company",
        "min_experience": 5.0,  # Default fallback
        "max_experience": 9.0,  # Default fallback
        "primary_locations": [],
        "secondary_locations": [],
        "core_required_skills": [],
        "preferred_skills": [],
        "blacklisted_companies": get_target_jd()["blacklisted_companies"]  # Standard default
    }
    
    # 1. Parse Title & Company
    title_match = re.search(r"(job title|role|position):\s*(.*)", jd_text, re.IGNORECASE)
    if title_match:
        parsed["title"] = title_match.group(2).split('\n')[0].strip()
        
    company_match = re.search(r"company:\s*(.*)", jd_text, re.IGNORECASE)
    if company_match:
        parsed["company"] = company_match.group(1).split('\n')[0].strip()
        
    # 2. Parse Experience (e.g. "5-9 years", "5 to 9 years", "5+ years")
    # Pattern A: range "5-9 years" or "5 to 9 years"
    range_match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*years?", jd_lower)
    if range_match:
        parsed["min_experience"] = float(range_match.group(1))
        parsed["max_experience"] = float(range_match.group(2))
    else:
        # Pattern B: "5+ years" or "minimum 5 years"
        plus_match = re.search(r"(\d+)\s*\+\s*years?", jd_lower)
        min_match = re.search(r"minimum\s*(\d+)\s*years?", jd_lower)
        if plus_match:
            parsed["min_experience"] = float(plus_match.group(1))
            parsed["max_experience"] = max(15.0, parsed["min_experience"] + 5)
        elif min_match:
            parsed["min_experience"] = float(min_match.group(1))
            parsed["max_experience"] = max(15.0, parsed["min_experience"] + 5)

    # 3. Parse Locations
    known_locations = [
        "noida", "pune", "delhi ncr", "delhi", "gurgaon", "hyderabad", 
        "bangalore", "mumbai", "chennai", "kolkata", "bengaluru", "jaipur"
    ]
    for loc in known_locations:
        if loc in jd_lower:
            # First matches as primary, others as secondary
            if not parsed["primary_locations"]:
                parsed["primary_locations"].append(loc)
            else:
                parsed["secondary_locations"].append(loc)
                
    # Defaults if no locations found
    if not parsed["primary_locations"]:
        parsed["primary_locations"] = ["noida", "pune"]
    if not parsed["secondary_locations"]:
        parsed["secondary_locations"] = ["delhi", "hyderabad", "bangalore"]

    # 4. Parse Skills dynamically from text
    skills_vocab = {
        # Core retrieval / vector search
        "embeddings": "core", "vector search": "core", "retrieval": "core", 
        "vector database": "core", "sentence-transformers": "core", "pinecone": "core", 
        "weaviate": "core", "qdrant": "core", "milvus": "core", "opensearch": "core", 
        "elasticsearch": "core", "faiss": "core", "python": "core", "ndcg": "core", 
        "mrr": "core", "map": "core", "evaluation": "core",
        
        # Preferred ML / adjacent
        "llm": "preferred", "fine-tuning": "preferred", "lora": "preferred", 
        "qlora": "preferred", "peft": "preferred", "learning to rank": "preferred", 
        "xgboost": "preferred", "hr-tech": "preferred", "marketplace": "preferred", 
        "nlp": "preferred", "distributed systems": "preferred", "pytorch": "preferred", 
        "tensorflow": "preferred", "scikit-learn": "preferred", "keras": "preferred",
        "sql": "preferred", "docker": "preferred", "kubernetes": "preferred",
        "aws": "preferred", "gcp": "preferred", "azure": "preferred", "mlops": "preferred"
    }
    
    for skill, category in skills_vocab.items():
        if skill in jd_lower:
            if category == "core":
                parsed["core_required_skills"].append(skill)
            else:
                parsed["preferred_skills"].append(skill)
                
    # Ensure lists are not empty
    if not parsed["core_required_skills"]:
        parsed["core_required_skills"] = ["python", "embeddings", "retrieval"]
    if not parsed["preferred_skills"]:
        parsed["preferred_skills"] = ["nlp", "pytorch", "llm"]
        
    return parsed
