import json
from pathlib import Path
import re
from typing import Dict

# Minimal categorization logic mirrored from mcq_manager.py for the script
def categorize_question(q: Dict) -> Dict[str, bool]:
    text = (str(q.get("question", "")) + " " + str(q.get("explanation", ""))).lower()
    is_foundational = any(w in text for w in ["basic", "simple", "foundation", "definition", "primary", "concept of", "what is"])
    is_conceptual = any(w in text for w in ["why", "concept", "principle", "reason", "because", "define", "statement", "theory", "explain"])
    is_numerical = bool(re.search(r"\d|\$|\\frac|\\sqrt|x\^|x\b|=", text))
    is_basic = not is_numerical or (len(text) < 60 and "solve" not in text)
    is_intermediate = is_numerical and len(text) >= 60 and not any(w in text for w in ["complex", "advanced", "hard", "difficult"])
    is_cbse = any(w in text for w in ["cbse", "ncert", "board", "syllabus", "grade", "class"])
    is_common = any(w in text for w in ["common", "frequent", "usually", "often", "standard"])
    is_exam = any(w in text for w in ["exam", "test", "important", "previous year", "sample paper", "mark"]) or is_cbse
    return {
        "foundational": is_foundational,
        "conceptual": is_conceptual,
        "numerical": is_numerical,
        "basic": is_basic,
        "intermediate": is_intermediate,
        "cbse": is_cbse,
        "common": is_common,
        "exam": is_exam
    }

def tag_question(q: Dict) -> Dict:
    q["categories"] = categorize_question(q)
    return q

def process_kb():
    kb_file = Path("app/mcq_kb.json")
    if not kb_file.exists():
        print("KB file not found.")
        return

    kb = json.loads(kb_file.read_text(encoding="utf-8"))
    bank = kb.get("mcq_bank", {})
    
    count = 0
    for lk in bank:
        # Legacy domains
        for did in bank[lk].get("domains", {}):
            for q in bank[lk]["domains"][did].get("questions", []):
                tag_question(q)
                count += 1
        # Canonical domains
        for top in bank[lk].get("canonical_domains", {}):
            for sub in bank[lk]["canonical_domains"][top]:
                for q in bank[lk]["canonical_domains"][top][sub].get("questions", []):
                    tag_question(q)
                    count += 1
    
    kb_file.write_text(json.dumps(kb, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated {count} questions with categories.")

if __name__ == "__main__":
    process_kb()
