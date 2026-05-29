import json
import re
from pathlib import Path
from typing import Dict, List, Optional
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api_client import AIClient
from app.mcq_manager import load_kb, tag_question

def identify_gaps(kb: Dict) -> List[Dict]:
    gaps = []
    bank = kb.get("mcq_bank", {})
    categories = ["foundational", "conceptual", "numerical", "cbse", "exam"]
    
    for lk, level_node in bank.items():
        # Check canonical domains
        canonical = level_node.get("canonical_domains", {})
        for top, subs in canonical.items():
            for sub, sub_node in subs.items():
                qs = sub_node.get("questions", [])
                coverage = {cat: 0 for cat in categories}
                for q in qs:
                    cats = q.get("categories", {})
                    for cat in categories:
                        if cats.get(cat):
                            coverage[cat] += 1
                
                missing = [cat for cat, count in coverage.items() if count == 0]
                if missing:
                    gaps.append({
                        "level": lk,
                        "topic": f"{top} / {sub}",
                        "missing": missing,
                        "sample_q": qs[0]["question"] if qs else "No existing questions"
                    })
    return gaps

def backfill_topic(ai_client: AIClient, gap: Dict) -> List[Dict]:
    if not ai_client:
        return []
    
    prompt = (
        f"You are an expert CBSE Maths Teacher. We are missing specific types of questions for the topic '{gap['topic']}' at '{gap['level']}' level. "
        f"Missing categories: {', '.join(gap['missing'])}. "
        f"Based on this sample question: '{gap['sample_q']}', generate 1 high-quality MCQ for EACH missing category. "
        "Each question must be distinct and fill the gap (e.g., if foundational is missing, define the base concept; if exam is missing, make it a high-stakes application). "
        "Output ONLY valid JSON: a list of objects with keys: question, choices (list of 4), answer (index), explanation."
    )
    
    try:
        response = ai_client.send_message([{"role": "user", "content": prompt}])
        # simple json extraction
        match = re.search(r"\[.*\]", response, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"Error backfilling {gap['topic']}: {e}")
    return []

def run_backfill():
    kb = load_kb()
    if not kb:
        print("KB not found.")
        return
    
    gaps = identify_gaps(kb)
    if not gaps:
        print("No gaps identified. KB is comprehensive!")
        return
    
    print(f"Identified {len(gaps)} topics with coverage gaps.")
    
    # In a real scenario, we'd loop and call backfill_topic. 
    # For now, we just report the gaps as this requires an active API key.
    for g in gaps:
        print(f"- {g['level']} | {g['topic']} | Missing: {g['missing']}")

if __name__ == "__main__":
    run_backfill()
