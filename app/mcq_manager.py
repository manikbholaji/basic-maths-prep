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
            # generate 3 simple MCQs per topic
            questions = []
            # Q1: concept identification
            q1 = {
                "id": f"{domain_id}-1",
                "question": f"Which best describes '{title}'?",
                "choices": [
                    brief[:80],
                    "A topic about number patterns and simple operations.",
                    "A topic about English grammar and comprehension.",
                    "A topic about computer programming basics.",
                ],
                "answer": 0,
                "explanation": brief,
            }
            questions.append(q1)

            # Q2: true/false style
            q2 = {
                "id": f"{domain_id}-2",
                "question": f"True or False: {title} requires understanding of numeric computation or algebraic manipulation.",
                "choices": ["True", "False", "Sometimes", "None of these"],
                "answer": 0,
                "explanation": "Most maths topics require numeric or algebraic thinking; review the topic notes.",
            }
            questions.append(q2)

            # Q3: simple application prompt
            q3 = {
                "id": f"{domain_id}-3",
                "question": f"Which skill is most related to {title}?",
                "choices": [
                    "Problem solving & practice",
                    "Poetry recitation",
                    "Map reading",
                    "Cooking recipes",
                ],
                "answer": 0,
                "explanation": "Mathematics topics connect to problem solving and numeric practice.",
            }
            questions.append(q3)

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
                q = {
                    "id": qid,
                    "question": item.get("question") or item.get("prompt") or "",
                    "choices": item.get("choices") or item.get("options") or [],
                    "answer": int(item.get("answer", 0)) if item.get("answer") is not None else 0,
                    "explanation": item.get("explanation", ""),
                }
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

    random.shuffle(items)
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
            qs = dom.get("questions", [])
            return qs[:top_n]
    # Then try canonical composite id 'Top::Sub' or either side
    for lk in bank:
        for top, top_node in bank[lk].get("canonical_domains", {}).items():
            for sub, sub_node in top_node.items():
                cid = f"{top}::{sub}"
                if domain_id == cid or domain_id == sub or domain_id == top:
                    qs = sub_node.get("questions", [])
                    return qs[:top_n]
    return []


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
        return new_q

    # Quadratic handling: detect and build variants
    quad = _build_quadratic_variant(qtext, variant_index=variant_index)
    if quad:
        new_q["question"] = quad["equation"]
        new_q["choices"] = quad.get("choices", [])
        new_q["answer"] = quad.get("answer", 0)
        new_q["explanation"] = q.get("explanation", "") + " (quadratic variant)"
        return new_q

    # fallback: perturb numeric tokens in question and choices
    new_q["question"] = _perturb_number_str(qtext)
    new_choices = []
    any_changed = False
    for ch in choices:
        new_ch = _perturb_number_str(ch)
        if new_ch != ch:
            any_changed = True
        new_choices.append(new_ch)

    if not any_changed:
        new_q["question"] = qtext + " (variant)"
        new_choices = choices[:]

    new_q["choices"] = new_choices
    new_q["answer"] = int(q.get("answer", 0)) if len(new_choices) == len(choices) else 0
    new_q["explanation"] = q.get("explanation", "")
    return new_q


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
    return level_node.get("canonical_domains", {}).get(top, {}).get(sub, {}).get("questions", [])[:top_n]
