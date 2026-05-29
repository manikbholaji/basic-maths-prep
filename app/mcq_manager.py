from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
import zipfile

KB_FILE = Path(__file__).resolve().parent / "mcq_kb.json"


LEVELS = {
    "primary": "Primary (Class 3-5)",
    "middle": "Secondary (Class 6-8)",
    "senior": "Senior Secondary (Class 9-12)",
}


KEYWORD_TO_LEVEL = {
    # basic arithmetic
    "add": "primary",
    "addition": "primary",
    "subtract": "primary",
    "subtraction": "primary",
    "division": "primary",
    "multiply": "primary",
    "fractions": "middle",
    "ratio": "middle",
    "proportion": "middle",
    "algebra": "senior",
    "polynomial": "senior",
    "discriminant": "senior",
    "pythagor": "senior",
    "geometry": "middle",
    "mensuration": "senior",
    "statistics": "middle",
    "probability": "middle",
}


def _clean_title(name: str) -> str:
    name = Path(name).stem
    name = name.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", name).strip().title()


def _choose_level_from_name(name: str) -> str:
    n = name.lower()
    for k, v in KEYWORD_TO_LEVEL.items():
        if k in n:
            return v
    # If file mentions ch- or numbers, default to senior for advanced topics
    if re.search(r"ch[-_]?\d+|class|polynomial|equation|discriminant", n):
        return "senior"
    # fallback
    return "middle"


def _extract_brief(tex: str) -> str:
    # Try to extract the first normal sentence from TeX content
    text = re.sub(r"\\[a-zA-Z]+\{.*?\}", "", tex)
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\[^\s]+", "", text)
    sentences = re.split(r"[\.\?\!]\s+", text)
    for s in sentences:
        s = s.strip()
        if len(s) > 20:
            return re.sub(r"\s+", " ", s)[:200]
    # fallback to first 80 chars of file
    return re.sub(r"\s+", " ", tex)[:200]


def categorize_question(q: Dict) -> Dict[str, bool]:
    """Determine multi-dimensional categories for a question based on heuristics."""
    text = (str(q.get("question", "")) + " " + str(q.get("explanation", ""))).lower()
    
    # Foundational: Basic definitions or very simple first-principles
    is_foundational = any(w in text for w in ["basic", "simple", "foundation", "definition", "primary", "concept of", "what is"])
    
    # Conceptual: Focuses on "why" or theory rather than just calculation
    is_conceptual = any(w in text for w in ["why", "concept", "principle", "reason", "because", "define", "statement", "theory", "explain"])
    
    # Numerical: Involves explicit calculations or numbers
    is_numerical = bool(re.search(r"\d|\$|\\frac|\\sqrt|x\^|x\b|=", text))
    
    # Difficulty levels
    is_basic = not is_numerical or (len(text) < 60 and "solve" not in text)
    is_intermediate = is_numerical and len(text) >= 60 and not any(w in text for w in ["complex", "advanced", "hard", "difficult"])
    
    # Board / Exam Relevance
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
    """Add multi-dimensional categories to a question dictionary."""
    q["categories"] = categorize_question(q)
    return q


def _question_numeric_score(question: Dict) -> int:
    parts = [str(question.get("question", ""))]
    parts.extend(str(choice) for choice in (question.get("choices", []) or []))
    text = " ".join(parts)
    score = 0
    if re.search(r"\$.*\$|\\frac|\\sqrt|x\^|x\b|=", text):
        score += 4
    if re.search(r"\d", text):
        score += 3
    if re.search(r"[+\-*/]", text):
        score += 2
    if re.search(r"solve|find|calculate|evaluate|simplify|what is|how many|cost|percent|ratio", text, re.I):
        score += 2
    return score


def _prioritize_questions(items: List[Dict]) -> List[Dict]:
    tagged = list(items)
    random.shuffle(tagged)
    return sorted(tagged, key=lambda q: _question_numeric_score(q), reverse=True)


def _int_choices(correct: int, spread: int = 3) -> List[str]:
    candidates = [correct, correct + 1, correct - 1, correct + spread]
    seen = set()
    choices = []
    for value in candidates:
        if value not in seen:
            seen.add(value)
            choices.append(str(value))
    while len(choices) < 4:
        value = correct + len(choices) + 1
        if value not in seen:
            seen.add(value)
            choices.append(str(value))
    return choices[:4]


def _make_numerical_topic_questions(title: str, brief: str, level: str, seed: int) -> List[Dict]:
    a = seed % 9 + 3
    b = (seed // 3) % 8 + 2
    c = (seed // 7) % 6 + 2
    topic_note = brief[:90] or f"Practice focus for {title}."

    if level == "primary":
        q1_ans = a + b
        q2_ans = a * c
        q3_ans = q2_ans - b
        return [
            tag_question({
                "id": f"{title}-num-1",
                "question": f"What is ${a} + {b}$?",
                "choices": _int_choices(q1_ans),
                "answer": 0,
                "explanation": f"Add the numbers directly. {topic_note}",
            }),
            tag_question({
                "id": f"{title}-num-2",
                "question": f"A student solves {a} questions each day for {c} days. How many questions are solved in all?",
                "choices": _int_choices(q2_ans),
                "answer": 0,
                "explanation": f"Multiply the daily count by the number of days. {topic_note}",
            }),
            tag_question({
                "id": f"{title}-num-3",
                "question": f"What is ${a * c} - {b}$?",
                "choices": _int_choices(q3_ans),
                "answer": 0,
                "explanation": f"Subtract carefully and check the count. {topic_note}",
            }),
        ]

    if level == "middle":
        q1_ans = a * 25
        q2_ans = a * b
        q3_ans = (c * 3) + a
        return [
            tag_question({
                "id": f"{title}-num-1",
                "question": f"What is {a * 25}% of 100?",
                "choices": _int_choices(q1_ans),
                "answer": 0,
                "explanation": f"Convert the percentage to a value out of 100. {topic_note}",
            }),
            tag_question({
                "id": f"{title}-num-2",
                "question": f"The ratio of pens to pencils is 1:{b}. If there are {a} pens, how many pencils are there?",
                "choices": _int_choices(q2_ans),
                "answer": 0,
                "explanation": f"Use the ratio to scale the second quantity. {topic_note}",
            }),
            tag_question({
                "id": f"{title}-num-3",
                "question": f"What is $3 \\times {c} + {a}$?",
                "choices": _int_choices(q3_ans),
                "answer": 0,
                "explanation": f"Follow order of operations. {topic_note}",
            }),
        ]

    q1_ans = a * b - c
    q2_ans = 2 * a + 3 * b
    q3_ans = a * a - b
    return [
        tag_question({
            "id": f"{title}-num-1",
            "question": f"Solve $2x + {b} = {2 * a + b}$.",
            "choices": _int_choices(a),
            "answer": 0,
            "explanation": f"Subtract {b} from both sides and divide by 2. {topic_note}",
        }),
        tag_question({
            "id": f"{title}-num-2",
            "question": f"If $x = {a}$, what is the value of $2x + 3 \\times {b}$?",
            "choices": _int_choices(q2_ans),
            "answer": 0,
            "explanation": f"Substitute the value of x and evaluate carefully. {topic_note}",
        }),
        tag_question({
            "id": f"{title}-num-3",
            "question": f"If $x = {a}$, what is the value of $x^2 - {b}$?",
            "choices": _int_choices(q3_ans),
            "answer": 0,
            "explanation": f"Square first, then subtract. {topic_note}",
        }),
    ]


def build_kb_from_zip(zip_path: str, out_path: Optional[str] = None, regenerate: bool = False) -> Dict:
    """Read .tex files from a zip and auto-generate an MCQ KB.

    The generated KB is advisory and marked as auto-generated; manual review is recommended.
    """
    zip_path = Path(zip_path)
    if out_path:
        kb_path = Path(out_path)
    else:
        kb_path = KB_FILE

    if kb_path.exists() and not regenerate:
        try:
            return json.loads(kb_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    content = defaultdict(lambda: {"domains": {}})
    if not zip_path.exists():
        raise FileNotFoundError(f"Zip not found: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as z:
        for name in z.namelist():
            if not name.lower().endswith(".tex"):
                continue
            try:
                raw = z.read(name).decode("utf-8", errors="ignore")
            except Exception:
                raw = ""
            title = _clean_title(name)
            level = _choose_level_from_name(name)
            brief = _extract_brief(raw)

            domain_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or title
            questions = _make_numerical_topic_questions(title, brief, level, seed=sum(ord(ch) for ch in f"{title}{brief}"))

            content[level]["domains"][domain_id] = {
                "title": title,
                "source_file": name,
                "brief": brief,
                "auto_generated": True,
                "questions": questions,
            }

    out = {"levels": LEVELS, "mcq_bank": content}
    try:
        kb_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return out


def load_kb(kb_path: Optional[str] = None) -> Dict:
    path = Path(kb_path) if kb_path else KB_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _expand_kb_with_ai(ai_client, level: str, needed: int, kb: Optional[Dict] = None) -> int:
    """Attempt to expand the KB using the provided ai_client.

    Returns the number of questions added.
    """
    if ai_client is None or needed <= 0:
        return 0

    kb = kb or load_kb()
    prompt = (
        f"Generate {needed} multiple-choice math questions suitable for students at the '{level}' level. "
        "Return output as JSON: a list of objects with keys: question, choices (list of 4), answer (index), explanation, domain (optional)."
    )
    try:
        text = ai_client.send_message([{"role": "user", "content": prompt}])
    except Exception:
        return 0

    # Extract JSON from markdown code blocks if present (Gemini wraps in ```json...```)
    if text.strip().startswith("```"):
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1).strip()

    # Try to parse JSON from the assistant
    try:
        data = json.loads(text)
        if isinstance(data, list):
            added = 0
            # append under an 'ai_generated' domain
            domain_id = f"ai-generated-{level}"
            level_node = kb.setdefault("mcq_bank", {}).setdefault(level, {}).setdefault("domains", {})
            if domain_id not in level_node:
                level_node[domain_id] = {"title": "AI generated questions", "source_file": None, "brief": "AI-generated", "auto_generated": True, "questions": []}
            for idx, item in enumerate(data, start=1):
                qid = f"{domain_id}-{len(level_node[domain_id]['questions'])+1}"
                q = tag_question({
                    "id": qid,
                    "question": item.get("question") or item.get("prompt") or "",
                    "choices": item.get("choices") or item.get("options") or [],
                    "answer": int(item.get("answer", 0)) if item.get("answer") is not None else 0,
                    "explanation": item.get("explanation", ""),
                })
                level_node[domain_id]["questions"].append(q)
                added += 1

            # persist KB
            try:
                KB_FILE.write_text(json.dumps(kb, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
            return added
    except Exception:
        # best-effort: can't parse
        return 0


def sample_diagnostic(level: str, num_questions: int = 30, kb: Optional[Dict] = None, ai_client=None, allow_ai: bool = False) -> List[Dict]:
    kb = kb or load_kb()
    bank = kb.get("mcq_bank", {})
    level_key = level
    items = []
    def _collect_questions_from_level(lk_node):
        q = []
        # legacy domains
        for d in lk_node.get("domains", {}).values():
            q.extend(d.get("questions", []))
        # canonical domains
        for top, top_node in lk_node.get("canonical_domains", {}).items():
            for sub, sub_node in top_node.items():
                q.extend(sub_node.get("questions", []))
        return q

    if level_key not in bank:
        # fallback: pick from any level
        for lk in bank:
            items.extend(_collect_questions_from_level(bank[lk]))
    else:
        items.extend(_collect_questions_from_level(bank[level_key]))

    # If insufficient questions and AI is allowed, try to expand (heuristic-first behavior)
    if len(items) < num_questions and allow_ai and ai_client is not None:
        needed = num_questions - len(items)
        added = _expand_kb_with_ai(ai_client, level_key, needed, kb=kb)
        # reload KB and rebuild items
        if added > 0:
            kb = load_kb()
            bank = kb.get("mcq_bank", {})
            items = []
            if level_key not in bank:
                for lk in bank:
                    for d in bank[lk].get("domains", {}).values():
                        items.extend(d.get("questions", []))
            else:
                for d in bank[level_key].get("domains", {}).values():
                    items.extend(d.get("questions", []))

    if not items:
        return []

    items = _prioritize_questions(items)
    return items[:min(num_questions, len(items))]


def evaluate_responses(responses: Dict[str, int], kb: Optional[Dict] = None) -> Dict:
    """responses: mapping question_id -> selected_choice_index"""
    kb = kb or load_kb()
    bank = kb.get("mcq_bank", {})
    wrong_by_domain = defaultdict(int)
    total_by_domain = defaultdict(int)

    # build map question_id -> (domain, title)
    qmap = {}
    for lk, level_data in bank.items():
        # legacy domains
        for did, domain in level_data.get("domains", {}).items():
            title = domain.get("title") or did
            for q in domain.get("questions", []):
                qmap[q["id"]] = (lk, did, title, q)
        # canonical domains: use composite domain name for user-friendly output
        for top, top_node in level_data.get("canonical_domains", {}).items():
            for sub, sub_node in top_node.items():
                cid = f"{top}::{sub}"
                title = f"{top} / {sub}"
                for q in sub_node.get("questions", []):
                    qmap[q["id"]] = (lk, cid, title, q)

    correct = 0
    total = 0
    wrong_questions = []
    for qid, sel in responses.items():
        total += 1
        meta = qmap.get(qid)
        if not meta:
            continue
        lk, did, domain_title, q = meta
        total_by_domain[did] += 1
        if int(sel) == int(q.get("answer", 0)):
            correct += 1
        else:
            wrong_by_domain[did] += 1
            wrong_questions.append({
                "id": qid,
                "question": q.get("question"),
                "selected": sel,
                "answer": q.get("answer"),
                "domain": domain_title,
            })

    # prepare recommendation: domains with highest wrong counts
    domains_sorted = sorted(wrong_by_domain.items(), key=lambda x: x[1], reverse=True)
    recommendations = []
    for did, wrong_count in domains_sorted:
        # find a representative domain title from qmap
        rep_title = None
        for _, meta in qmap.items():
            if meta[1] == did:
                rep_title = meta[2]
                break
        rep_title = rep_title or did
        # suggest practice: scale with wrong_count
        suggested_practice = max(5, wrong_count * 3)
        suggested_minutes = suggested_practice * 3  # estimate 3 minutes per question
        recommendations.append(
            {
                "domain_id": did,
                "domain": rep_title,
                "wrong": wrong_count,
                "total": total_by_domain.get(did, 0),
                "suggested_practice": suggested_practice,
                "suggested_minutes": suggested_minutes,
                "actions": [
                    "Review the concept summary (10-15 minutes)",
                    f"Attempt {suggested_practice} targeted MCQs for this domain",
                    "Do one timed mini-test (20-30 minutes)",
                    "Revisit explanations for incorrect answers and note mistakes",
                ],
            }
        )

    score_pct = round((correct / total * 100) if total else 0)
    coach_notes = ""
    if recommendations:
        top_domains = ", ".join([rec["domain"] for rec in recommendations[:3]])
        coach_notes = (
            f"Diagnostic score: {correct}/{total} ({score_pct}%). "
            f"Primary focus: {top_domains}. Follow the suggested actions for each domain: review, targeted practice, and a timed mini-test. "
            "If you find multiple domains challenging, consider scheduling a coaching session for focused support."
        )
    else:
        coach_notes = (
            "Excellent performance — you answered all diagnostic questions correctly. "
            "Keep a weekly practice habit and attempt a full-length mock test every 2-3 weeks to maintain readiness."
        )

    return {
        "total": total,
        "correct": correct,
        "wrong": len(wrong_questions),
        "details": wrong_questions,
        "recommendations": recommendations,
        "coach_notes": coach_notes,
    }


def get_domain_practice(domain_id: str, kb: Optional[Dict] = None, top_n: int = 10) -> List[Dict]:
    kb = kb or load_kb()
    bank = kb.get("mcq_bank", {})
    # first try legacy domains
    for lk in bank:
        dom = bank[lk].get("domains", {}).get(domain_id)
        if dom:
            qs = _prioritize_questions(dom.get("questions", []))
            return qs[:top_n]
    # Then try canonical composite id 'Top::Sub' or either side
    for lk in bank:
        for top, top_node in bank[lk].get("canonical_domains", {}).items():
            for sub, sub_node in top_node.items():
                cid = f"{top}::{sub}"
                if domain_id == cid or domain_id == sub or domain_id == top:
                    qs = _prioritize_questions(sub_node.get("questions", []))
                    return qs[:top_n]
    return []


def sample_numerical_practice(level: str = "middle", num_questions: int = 20, kb: Optional[Dict] = None) -> List[Dict]:
    """Return a prioritized list of questions from the `numerical-practice` domain for quick practice.

    This is a convenience wrapper used by the app to load numerical practice sets.
    """
    kb = kb or load_kb()
    # attempt to read the specific domain under the requested level
    domain = kb.get("mcq_bank", {}).get(level, {}).get("domains", {}).get("numerical-practice")
    if domain and domain.get("questions"):
        return _prioritize_questions(domain.get("questions", []))[:min(num_questions, len(domain.get("questions", [])))]
    # fallback: gather high-scoring numeric questions across the KB
    items = []
    for lk, level_data in kb.get("mcq_bank", {}).items():
        for did, dom in level_data.get("domains", {}).items():
            for q in dom.get("questions", []):
                if _question_numeric_score(q) >= 4:
                    items.append(q)
    if not items:
        return []
    items = _prioritize_questions(items)
    return items[:min(num_questions, len(items))]


def _find_question_in_kb(qid: str, kb: Optional[Dict] = None):
    kb = kb or load_kb()
    bank = kb.get("mcq_bank", {})
    for lk, level_data in bank.items():
        for did, domain in level_data.get("domains", {}).items():
            for q in domain.get("questions", []):
                if q.get("id") == qid:
                    return q, did
        for top, top_node in level_data.get("canonical_domains", {}).items():
            for sub, sub_node in top_node.items():
                for q in sub_node.get("questions", []):
                    if q.get("id") == qid:
                        cid = f"{top}::{sub}"
                        return q, cid
    return None, None


def _perturb_number_str(s: str) -> str:
    # replace numeric tokens in a string by similar values
    def repl(m):
        try:
            val = float(m.group(0))
            if abs(val) > 1:
                factor = random.uniform(0.8, 1.25)
                newv = int(round(val * factor))
                return str(newv)
            else:
                # small values: add or subtract 1
                newv = round(val + random.choice([-1, 1]) * max(1, abs(val)), 2)
                # trim trailing .0
                if newv == int(newv):
                    return str(int(newv))
                return str(newv)
        except Exception:
            return m.group(0)

    return re.sub(r"-?\d+\.?\d*", repl, s)


def _try_parse_linear_equation(s: str):
    # Match ax + b = c or a x + b = c (allow spaces), simple integer coefficients
    m = re.search(r"([+-]?\d+)\s*([a-zA-Z])\s*([+-]\s*\d+)?\s*=\s*([+-]?\d+)", s.replace('^', ''))
    if not m:
        return None
    a = int(m.group(1))
    var = m.group(2)
    b_raw = m.group(3) or "+0"
    b = int(b_raw.replace(' ', ''))
    c = int(m.group(4))
    return {"a": a, "b": b, "c": c, "var": var, "match": m}


def _build_linear_variant(s: str, variant_index: int = 1):
    parsed = _try_parse_linear_equation(s)
    if not parsed:
        return None
    a = parsed["a"]
    b = parsed["b"]
    c = parsed["c"]
    var = parsed["var"]
    # perturb coefficients mildly
    a2 = int(max(1, round(a * random.uniform(0.7, 1.4))))
    b2 = int(round(b * random.uniform(0.7, 1.35)))
    c2 = int(round(c * random.uniform(0.7, 1.35)))
    # build new equation text
    def fmt_coef(coef, var):
        if coef == 1:
            return f"{var}"
        return f"{coef}{var}"

    new_eq = f"{fmt_coef(a2, var)} {('+' if b2>=0 else '-') } {abs(b2)} = {c2}"
    # compute solution x = (c - b)/a
    try:
        x_val = (c - b) / a
        x2 = (c2 - b2) / a2
    except Exception:
        return None
    return {"equation": new_eq, "x": x2}


def _try_parse_factorable(s: str):
    # detect simple factorable form like (x+2)(x+3)=0 or (x-2)(2x+1)=0
    m = re.search(r"\(([^\)]+)\)\s*\(([^\)]+)\)\s*=\s*0", s.replace(' ', ''))
    if not m:
        return None
    f1 = m.group(1)
    f2 = m.group(2)
    def parse_factor(f):
        # handle ax+b or x+b
        fm = re.match(r"([+-]?\d*)([a-zA-Z])?([+-]?\d+)?", f)
        if not fm:
            return None
        a_raw = fm.group(1)
        var = fm.group(2)
        b_raw = fm.group(3)
        a = int(a_raw) if a_raw and a_raw not in ['+', '-'] else (1 if a_raw in ['', '+', None] else -1)
        b = int(b_raw) if b_raw else 0
        return {"a": a, "b": b, "var": var}
    p1 = parse_factor(f1)
    p2 = parse_factor(f2)
    if not p1 or not p2:
        return None
    # root from each factor ax + b = 0 => x = -b/a
    try:
        r1 = -p1["b"] / p1["a"]
        r2 = -p2["b"] / p2["a"]
    except Exception:
        return None
    return {"roots": [r1, r2], "f1": f1, "f2": f2}


def _try_parse_quadratic_equation(s: str):
    # Normalize and look for pattern ax^2 + bx + c = 0 or = d
    t = s.replace(' ', '').replace('^2', 'x2').replace('X^2', 'x2')
    # replace unicode superscript
    t = t.replace('²', 'x2')
    # ensure variable symbol is x
    t = re.sub(r'([a-zA-Z])x2', 'x2', t)
    # try to find a, b, c
    a = 0; b = 0; c = 0
    ma = re.search(r'([+-]?\d*)x2', t)
    if ma:
        a_raw = ma.group(1)
        a = int(a_raw) if a_raw not in ['', '+', None, '-'] else (1 if a_raw in ['', '+', None] else -1)
    else:
        return None
    mb = re.search(r'([+-]?\d+)x(?!2)', t)
    if mb:
        b = int(mb.group(1))
    mc = re.search(r'([+-]?\d+)(?:$|=)', t)
    if mc:
        # take the last standalone number as c (may pick RHS); if RHS present, move to LHS
        last = mc.group(1)
        c = int(last)
    # attempt to find RHS and normalize to =0
    rhs = 0
    m_eq = re.search(r'=([+-]?\d+)', t)
    if m_eq:
        rhs = int(m_eq.group(1))
        c = c - rhs
    return {"a": a, "b": b, "c": c}


def _build_quadratic_variant(s: str, variant_index: int = 1):
    parsed = _try_parse_quadratic_equation(s)
    if not parsed:
        # try factorable form
        fact = _try_parse_factorable(s)
        if fact:
            roots = fact.get('roots', [])
            # create a variant by perturbing roots slightly
            r1 = roots[0] + random.choice([-1, 1]) * variant_index
            r2 = roots[1] + random.choice([-1, 1]) * variant_index
            # build equation from perturbed roots: a(x - r1)(x - r2)
            a = 1
            # generate quadratic coefficients
            A = a
            B = int(-a * (r1 + r2))
            C = int(a * r1 * r2)
            eq = f"{A}x^2 {'+' if B>=0 else '-'} {abs(B)}x {'+' if C>=0 else '-'} {abs(C)} = 0"
            # produce choices: pick one root as correct
            correct = r1
            opts = [correct, r2, correct + 1, correct - 1]
            opts = [str(int(o)) if abs(o - int(o))<1e-6 else str(round(o,2)) for o in opts[:4]]
            return {"equation": eq, "choices": opts, "answer": 0}
        return None
    a = parsed['a']; b = parsed['b']; c = parsed['c']
    # perturb coefficients
    a2 = int(max(1, round(a * random.uniform(0.7, 1.3))))
    b2 = int(round(b * random.uniform(0.7, 1.3)))
    c2 = int(round(c * random.uniform(0.7, 1.3)))
    # compute discriminant and roots
    disc = b2 * b2 - 4 * a2 * c2
    if disc < 0:
        return None
    import math
    r1 = (-b2 + math.sqrt(disc)) / (2 * a2)
    r2 = (-b2 - math.sqrt(disc)) / (2 * a2)
    # build equation string
    eq = f"{a2}x^2 {'+' if b2 >= 0 else '-'} {abs(b2)}x {'+' if c2 >= 0 else '-'} {abs(c2)} = 0"
    # create distractors intelligently:
    from fractions import Fraction

    def fmt_number(x):
        # represent rational numbers as fractions where appropriate
        f = Fraction(x).limit_denominator(20)
        if abs(f.numerator / f.denominator - x) < 1e-6 and f.denominator != 1:
            return f"{f.numerator}/{f.denominator}"
        if abs(x - int(x)) < 1e-6:
            return str(int(x))
        return str(round(x, 2))

    candidates = []
    candidates.append(r1)
    candidates.append(r2)
    # sign-swapped
    candidates.append(-r1)
    candidates.append(-r2)
    # small offsets
    candidates.append(r1 + 1)
    candidates.append(r1 - 1)
    candidates.append(r2 + 1)
    candidates.append(r2 - 1)
    # unique and formatted
    seen = set()
    opts = []
    for c in candidates:
        val = fmt_number(c)
        if val not in seen:
            seen.add(val)
            opts.append(val)
        if len(opts) >= 4:
            break

    # ensure correct answer included
    correct_val = fmt_number(r1)
    if correct_val not in opts:
        opts = opts[:3] + [correct_val]

    # shuffle options but keep track of answer index
    import random
    order = list(range(len(opts)))
    random.shuffle(order)
    shuffled = [opts[i] for i in order]
    answer_index = shuffled.index(correct_val)

    return {"equation": eq, "choices": shuffled, "answer": answer_index}


def generate_variant_question(q: Dict, variant_index: int = 1) -> Dict:
    """Create a variant of a question by perturbing numeric tokens or lightly paraphrasing.

    The variant preserves the correct choice index when possible.
    """
    new_q = dict(q)
    # update id to avoid collision
    base_id = q.get("id") or "q"
    new_q["id"] = f"{base_id}-v{variant_index}"

    qtext = q.get("question", "")
    # Special handling: linear algebraic equation variants
    lin = _build_linear_variant(qtext, variant_index=variant_index)
    choices = q.get("choices", []) or []
    if lin:
        new_q["question"] = lin["equation"]
        # build numeric choices around solution
        correct = lin["x"]
        # format numeric answer nicely
        def fmt(v):
            if abs(v - int(v)) < 1e-6:
                return str(int(v))
            return str(round(v, 2))

        # create distractors
        opts = [correct, correct + 1, correct - 1, correct + 2]
        opts = [fmt(o) for o in opts[:4]]
        # keep the same number of choices as original if possible
        if len(choices) >= 4:
            new_q["choices"] = opts[:len(choices)]
        else:
            new_q["choices"] = opts[:4]
        # place correct answer at index 0
        new_q["answer"] = 0
        new_q["explanation"] = q.get("explanation", "") + " (variant equation)"
        return tag_question(new_q)

    # Quadratic handling: detect and build variants
    quad = _build_quadratic_variant(qtext, variant_index=variant_index)
    if quad:
        new_q["question"] = quad["equation"]
        new_q["choices"] = quad.get("choices", [])
        new_q["answer"] = quad.get("answer", 0)
        new_q["explanation"] = q.get("explanation", "") + " (quadratic variant)"
        return tag_question(new_q)

    # fallback: perturb numeric tokens in question and choices
    new_q["question"] = _perturb_number_str(qtext)
    # use pedagogical distractor generation when possible
    gen_choices = _generate_distractors_for_question(q)
    new_q["choices"] = gen_choices
    new_q["answer"] = 0
    new_q["explanation"] = q.get("explanation", "") + " (variant with pedagogical distractors)"
    return tag_question(new_q)


def _generate_distractors_for_question(q: Dict, n_opts: int = 4) -> List[str]:
    """Return a list of `n_opts` choices with the correct answer first using problem-type heuristics."""
    from fractions import Fraction

    choices = []
    orig_choices = q.get("choices") or []
    # If original choices exist, prefer to use them (but re-order/generate pedagogical distractors)
    if orig_choices:
        try:
            correct_idx = int(q.get("answer", 0))
            correct_val = str(orig_choices[correct_idx])
        except Exception:
            correct_val = str(orig_choices[0])
    else:
        # no choices; try to infer answer from 'answer' field
        correct_val = str(q.get("answer", ""))

    # helpers
    def as_frac_parts(s: str):
        m = re.search(r"(\d+)\s*/\s*(\d+)", s)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None
    def as_mixed_frac(s: str):
        # match formats like '1 1/2' or '1\t1/2'
        m = re.search(r"(\d+)\s+(\d+)\s*/\s*(\d+)", s)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
        return None

    # Try fraction-like: produce pedagogical distractors (swap, wrong simplification, common-denominator mistakes)
    fp = as_frac_parts(correct_val) or as_frac_parts(q.get("question", ""))
    if fp:
        a, b = fp
        if b == 0:
            choices = [correct_val]
        else:
            correct = Fraction(a, b)
            # common student mistakes
            swapped = Fraction(b, a) if a != 0 else correct
            # wrong simplification (e.g., cancel a factor incorrectly)
            simp_wrong = None
            if a % 2 == 0 and b % 2 == 0:
                simp_wrong = Fraction(a // 2, b // 2 + 1)
            # common-denominator error for addition/subtraction: treat numerators as if denominators equal
            cd_error = Fraction(a + b, b)
            cand = [correct, swapped, cd_error]
            if simp_wrong:
                cand.append(simp_wrong)
            # ensure we have n_opts candidates
            i = 1
            while len(cand) < n_opts:
                cand.append(Fraction(a + i, b + i))
                i += 1
            choices = [str(int(c)) if c.denominator == 1 else f"{c.numerator}/{c.denominator}" for c in cand[:n_opts]]
        return choices[:n_opts]

    # Percent handling: detect '%' or 'percent' in question or correct_val
    if '%' in correct_val or re.search(r'percent|%', q.get('question', ''), re.I):
        # attempt to parse numeric part
        m = re.search(r"(-?\d+\.?\d*)\s*%", correct_val) or re.search(r"(\d+\.?\d*)\s*%", q.get('question',''))
        if m:
            base = float(m.group(1))
            # distractors: mis-scaled by 10x, off-by-10, decimal misplacement
            cand = [f"{base}%", f"{base*10}%", f"{base/10}%", f"{round(base+10,2)}%"]
            return [str(c) for c in cand[:n_opts]]

    # Mixed fraction handling (e.g., '1 1/2')
    mf = as_mixed_frac(correct_val) or as_mixed_frac(q.get('question',''))
    if mf:
        whole, nume, den = mf
        from fractions import Fraction
        correct = Fraction(whole * den + nume, den)
        # distractors: wrong conversion (forget whole), swap numerator/denominator in fractional part, off-by-one
        forget_whole = Fraction(nume, den)
        swap_frac = Fraction(den, nume) if nume != 0 else forget_whole
        off_by = Fraction(whole * den + nume + 1, den)
        cand = [correct, forget_whole, swap_frac, off_by]
        choices = [str(int(c)) if c.denominator == 1 else f"{c.numerator}/{c.denominator}" for c in cand[:n_opts]]
        return choices[:n_opts]

    # Algebraic: if question asks to solve simple linear equation, build distractors using parser
    try:
        lin = _try_parse_linear_equation(q.get('question',''))
        if lin:
            # correct solution x = (c - b)/a
            a = lin['a']; b = lin['b']; c = lin['c']
            try:
                correct_x = (c - b) / a
                opts = [correct_x, -correct_x, correct_x + 1, correct_x - 1]
                choices = [str(int(o)) if abs(o - int(o))<1e-9 else str(round(o,2)) for o in opts[:n_opts]]
                return choices[:n_opts]
            except Exception:
                pass
    except Exception:
        pass
    else:
        # try numeric parse
        try:
            num = float(correct_val)
            # decimal-like if has '.' or not integer
            if abs(num - int(num)) > 1e-9:
                # decimal distractors: decimal-shift, misplaced decimal, rounding, off-by-ten
                shifted = num * 10
                misplaced = num / 10
                rounded = round(num, 1) if abs(num - round(num, 1)) > 1e-9 else round(num + 0.1, 1)
                cand = [num, shifted, misplaced, rounded]
                choices = [str(round(c, 6)).rstrip('0').rstrip('.') for c in cand]
            else:
                n = int(round(num))
                # integer distractors: off-by-one, swapped digits, sign error
                swapped = int(str(n)[::-1]) if n >= 10 else n + 2
                cand = [n, n + 1, n - 1, swapped]
                # ensure uniqueness
                seen = []
                for c in cand:
                    if c not in seen:
                        seen.append(c)
                choices = [str(c) for c in seen[:n_opts]]
        except Exception:
            # Non-numeric: fallback to original choices or simple paraphrases
            if orig_choices:
                choices = orig_choices[:n_opts]
            else:
                # fabricate simple options (keep correct first)
                choices = [correct_val or "Option A"]
                i = 1
                while len(choices) < n_opts:
                    choices.append(f"Option {chr(65 + i)}")
                    i += 1

    # normalize length and ensure correct is first and unique
    uniq = []
    # place correct value first (normalize)
    corr = str(choices[0])
    uniq.append(corr)
    for c in choices[1:]:
        cs = str(c)
        if cs not in uniq:
            uniq.append(cs)
    i = 1
    while len(uniq) < n_opts:
        cand = f"{corr}+{i}"
        if cand not in uniq:
            uniq.append(cand)
        i += 1
    return uniq[:n_opts]


def generate_retry_questions(result: Dict, kb: Optional[Dict] = None, variants_per_question: int = 1) -> List[Dict]:
    """Given an evaluate_responses result, generate variant questions for incorrect ones.

    Returns a flat list of variant questions (one or more per wrong question).
    """
    kb = kb or load_kb()
    wrongs = result.get("details", []) or []
    out = []
    for idx, w in enumerate(wrongs, start=1):
        qid = w.get("id")
        orig_q, domain = _find_question_in_kb(qid, kb=kb)
        if not orig_q:
            continue
        for vi in range(1, variants_per_question + 1):
            vq = generate_variant_question(orig_q, variant_index=vi)
            out.append(vq)
    return out


def get_canonical_topics(level: str, kb: Optional[Dict] = None) -> List[Dict]:
    """Return list of canonical topics for a level as dicts: {top, sub, count}"""
    kb = kb or load_kb()
    bank = kb.get("mcq_bank", {})
    level_node = bank.get(level, {})
    out = []
    for top, top_node in level_node.get("canonical_domains", {}).items():
        for sub, sub_node in top_node.items():
            out.append({"top": top, "sub": sub, "count": len(sub_node.get("questions", []))})
    return out


def get_practice_by_canonical(level: str, top: str, sub: str, top_n: int = 10, kb: Optional[Dict] = None) -> List[Dict]:
    kb = kb or load_kb()
    bank = kb.get("mcq_bank", {})
    level_node = bank.get(level, {})
    qs = level_node.get("canonical_domains", {}).get(top, {}).get(sub, {}).get("questions", [])
    return _prioritize_questions(qs)[:top_n]
