import json
import re
import copy
from collections import defaultdict
from pathlib import Path

from app.api_client import AIClient
import warnings

KB_PATH = Path(__file__).resolve().parent / "knowledge_base.json"

def load_kb(path=KB_PATH):
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _tokenize_text(text):
    return set(re.findall(r"\b[a-z0-9]+\b", (text or "").lower()))


def _extract_json_from_response(text):
    if not isinstance(text, str) or not text.strip():
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    start = text.find("[")
    end = text.rfind("]")
    if 0 <= start < end:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None


def _build_pathway_prompt(field_interest, student_profile):
    location = (student_profile.get("location") or student_profile.get("city") or "").strip()
    class_level = (student_profile.get("class_level") or "").strip()
    interests = [i.strip() for i in student_profile.get("interests", []) if i and i.strip()]
    keywords = ", ".join(interests) if interests else "None"

    return (
        "You are an expert academic advisor for Indian students. "
        "Provide a complete career pathway for the chosen field of interest, "
        "including clear recommendations for Class 11 and Class 12, diploma or undergraduate routes, postgraduate options, "
        "top institution guidance, average fee estimates, and salary outlook. "
        "The output should explicitly account for the student’s current class stage, preferred city/state, and any optional keywords. "
        "Return one JSON object or a JSON array containing one object with the following keys: "
        "field, summary, class_11, class_12, career_outlook, top_institutions_by_city. "
        "class_11 should include decision guidance, recommended streams, subjects, and focus areas. "
        "class_12 should include action items, entrance exam suggestions, diploma and undergraduate/postgraduate route guidance, "
        "top institutions, average fees by route, and salary outlook. "
        "career_outlook should include career roles and salary guidance relevant to the field. "
        "If a preferred city or state is provided, include a dedicated entry under top_institutions_by_city for that city/state. "
        "Do not include any extra metadata outside the requested JSON structure. "
        f"Field of interest: {field_interest}. "
        f"Current class stage: {class_level}. "
        f"Preferred city or state: {location or 'Not specified'}. "
        f"Keywords: {keywords}. "
    )


def _find_pathway_template(field_interest, kb=None):
    """Return the best matching pathway template from the KB for a field interest."""
    if kb is None:
        kb = load_kb()

    pathways = kb.get("pathways", [])
    if not pathways:
        return None

    field = (field_interest or "").strip().lower()
    field_terms = _tokenize_text(field)
    best_item = None
    best_score = -1

    for pathway in pathways:
        aliases = [pathway.get("field", ""), *pathway.get("aliases", [])]
        alias_terms = [_tokenize_text(alias) for alias in aliases]
        score = 0

        for alias, terms in zip(aliases, alias_terms):
            alias_l = alias.lower()
            if field and alias_l == field:
                score += 12
            elif field_terms and terms and (field_terms == terms or field_terms <= terms or terms <= field_terms):
                score += 10
            elif field and field in alias_l:
                score += 8
            elif field_terms and any(term in alias_l for term in field_terms):
                score += 4

        if score > best_score:
            best_item = pathway
            best_score = score

    return copy.deepcopy(best_item) if best_item else None


def _merge_pathway_template(template, ai_item, field_interest, raw_response):
    """Merge AI output into a canonical KB template so the UI always gets a complete roadmap."""
    base = copy.deepcopy(template) if template else {}
    ai_item = ai_item if isinstance(ai_item, dict) else {}

    template_field = (base.get("field") or field_interest or "Academic pathway")
    ai_field = ai_item.get("field")
    if isinstance(ai_field, str) and ai_field.strip().lower() in {template_field.strip().lower(), (field_interest or "").strip().lower()}:
        chosen_field = ai_field
    else:
        chosen_field = template_field

    merged = {
        "field": chosen_field,
        "summary": ai_item.get("summary") or base.get("summary") or raw_response,
        "class_11": ai_item.get("class_11") if isinstance(ai_item.get("class_11"), dict) else base.get("class_11", {}),
        "class_12": ai_item.get("class_12") if isinstance(ai_item.get("class_12"), dict) else base.get("class_12", {}),
        "career_outlook": ai_item.get("career_outlook") if isinstance(ai_item.get("career_outlook"), (list, tuple)) else (base.get("career_outlook") or base.get("class_12", {}).get("career_outlook", [])),
        "top_institutions_by_city": ai_item.get("top_institutions_by_city") if isinstance(ai_item.get("top_institutions_by_city"), dict) else base.get("top_institutions_by_city", {}),
    }

    # Preserve any extra structured details from the KB template when the AI only returns partial output.
    for key in ("career_direction",):
        if key in base and key not in merged:
            merged[key] = base.get(key)

    # Fill obvious gaps from the template if the AI omitted them.
    for key in ("class_11", "class_12", "career_outlook", "top_institutions_by_city"):
        if not merged.get(key) and base.get(key):
            merged[key] = base.get(key)

    if not merged.get("career_outlook"):
        merged["career_outlook"] = base.get("class_12", {}).get("career_outlook", [])

    return merged


def _recommend_field_pathways_ai(field_interest, student_profile, ai_client):
    prompt = _build_pathway_prompt(field_interest, student_profile)
    template = _find_pathway_template(field_interest)
    messages = [
        {"role": "system", "content": "You are a helpful, practical Indian academic advisor."},
        {"role": "user", "content": prompt},
    ]
    response = ai_client.send_message(messages)
    parsed = _extract_json_from_response(response)

    if isinstance(parsed, dict):
        merged = _merge_pathway_template(template, parsed, field_interest, response)
        if _validate_pathway(merged):
            return [merged]
        # fall through to try to normalize below
    if isinstance(parsed, list):
        normalized = []
        for item in parsed:
            if isinstance(item, dict):
                merged = _merge_pathway_template(template, item, field_interest, response)
                if _validate_pathway(merged):
                    normalized.append(merged)
        if normalized:
            return normalized
    # If validation failed for parsed content, return a safe fallback using the KB template when possible.
    fallback = _merge_pathway_template(template, {}, field_interest, response)
    if _validate_pathway(fallback):
        return [fallback]
    return [{
        "field": field_interest or "Academic pathway",
        "summary": response,
        "class_11": {},
        "class_12": {},
        "career_outlook": [],
        "top_institutions_by_city": {},
    }]


def _validate_pathway(item):
    """Lightweight structural validation for AI-generated pathway objects.

    Ensures required keys exist and basic types are correct. This avoids returning
    malformed objects to the UI.
    """
    if not isinstance(item, dict):
        return False
    required_keys = ["field", "summary", "class_11", "class_12", "career_outlook", "top_institutions_by_city"]
    for k in required_keys:
        if k not in item:
            return False
    # Basic type checks
    if not isinstance(item.get("field"), str):
        return False
    if not isinstance(item.get("summary"), str):
        return False
    if not isinstance(item.get("class_11"), dict):
        return False
    if not isinstance(item.get("class_12"), dict):
        return False
    if not isinstance(item.get("career_outlook"), (list, tuple)):
        return False
    if not isinstance(item.get("top_institutions_by_city"), dict):
        return False
    return True


def _build_courses_prompt(student_profile, top_n=3):
    interests = ", ".join([i for i in student_profile.get("interests", [])]) or "None"
    completed = ", ".join([c for c in student_profile.get("completed", [])]) or "None"
    goals = student_profile.get("goals", "Not specified")
    return (
        "You are an expert academic advisor. Return a JSON array of up to "
        f"{top_n} course suggestions tailored to the student's interests and goals. "
        "Each item should include: code, name, description, tags, prerequisites, and why it's recommended. "
        f"Interests: {interests}. Completed: {completed}. Goals: {goals}."
    )


def _recommend_courses_ai(student_profile, ai_client, top_n=3):
    prompt = _build_courses_prompt(student_profile, top_n=top_n)
    messages = [
        {"role": "system", "content": "You are a helpful course recommender."},
        {"role": "user", "content": prompt},
    ]
    response = ai_client.send_message(messages)
    parsed = _extract_json_from_response(response)
    if isinstance(parsed, list):
        return parsed[:top_n]
    if isinstance(parsed, dict):
        return [parsed]
    return []


def recommend_courses(student_profile, kb=None, top_n=3, ai_client=None):
    """Recommend courses. Uses AI when `ai_client` is provided; otherwise falls back to KB rules."""
    if ai_client is not None:
        try:
            return _recommend_courses_ai(student_profile, ai_client, top_n=top_n)
        except Exception:
            pass

    if kb is None:
        kb = load_kb()

    courses = kb.get("courses", [])
    scores = defaultdict(int)

    interests = [i.lower() for i in student_profile.get("interests", [])]
    completed = set([c.upper() for c in student_profile.get("completed", [])])
    goals = student_profile.get("goals", "").lower()
    board = (student_profile.get("board") or "").lower()
    class_level = (student_profile.get("class_level") or "").lower()

    for c in courses:
        code = c.get("code")
        name = c.get("name", "")
        tags = [t.lower() for t in c.get("tags", [])]
        desc = c.get("description", "").lower()

        # Base score
        score = 0
        # Prefer courses matching interests or goals
        for it in interests:
            if it in tags or it in desc or it in name.lower():
                score += 3
        if any(g in desc or g in name.lower() or g in tags for g in goals.split()):
            score += 2
        # Boost if course explicitly targets the student's board
        if board:
            if board in " ".join(tags) or board.replace(' ', '') in code.lower():
                score += 4
            # Treat state-board style profiles as a match for state-board content.
            if board in ("state board", "stateboard", "regional board") and any(t for t in tags if "state" in t):
                score += 3
        # Boost if course is targeted at the student's class level (e.g., class 10)
        if class_level:
            cls_tag = class_level.replace(' ', '').replace('-', '').lower()
            # common forms: "class10", "class 10", "class10-math" etc.
            if any(cls_tag in t.replace(' ', '').lower() for t in tags) or cls_tag in desc.replace(' ', ''):
                score += 3
        # Penalize if already completed
        if code in completed:
            score -= 100
        # Prefer foundational courses
        if "found" in tags or "foundations" in desc:
            score += 1
        # Add small boost for no prerequisites (good for starters)
        if not c.get("prerequisites"):
            score += 1

        scores[code] = score

    # Return top_n course dicts
    ranked = sorted([c for c in courses], key=lambda x: scores.get(x.get("code"), 0), reverse=True)
    return ranked[:top_n]


def recommend_program_paths(student_profile, kb=None, top_n=5, ai_client=None):
    """Recommend diploma, undergraduate, and postgraduate pathways in India.

    If `ai_client` is provided, use the AI to generate program path recommendations.
    The knowledge-base fallback is deprecated and will be removed in a future release.
    """
    if ai_client is not None:
        # Build a small prompt for program path recommendations
        interests = ", ".join([i for i in student_profile.get("interests", [])]) or "None"
        level = student_profile.get("level", "Any")
        prompt = (
            "You are an expert academic advisor. Return a JSON array of recommended program pathways "
            f"for interests: {interests}. Desired level: {level}. Include level, field, title, best_for, institutions, note, and entry_after."
        )
        messages = [
            {"role": "system", "content": "You are a helpful academic program recommender."},
            {"role": "user", "content": prompt},
        ]
        try:
            resp = ai_client.send_message(messages)
            parsed = _extract_json_from_response(resp)
            if isinstance(parsed, list):
                return parsed[:top_n]
            if isinstance(parsed, dict):
                return [parsed]
        except Exception:
            pass

    warnings.warn("KB fallback for program path recommendations is deprecated; provide an `ai_client` for best results.", UserWarning)
    if kb is None:
        kb = load_kb()

    programs = kb.get("programs", [])
    if not programs:
        return []

    interests = [item.lower() for item in student_profile.get("interests", [])]
    goals = (student_profile.get("goals") or "").lower()
    desired_level = (student_profile.get("level") or "").strip().lower()
    class_level = (student_profile.get("class_level") or "").lower()
    location = (student_profile.get("location") or student_profile.get("city") or "").lower()

    ranked = []
    for program in programs:
        score = 0
        haystack = " ".join([
            program.get("level", ""),
            program.get("field", ""),
            program.get("title", ""),
            program.get("best_for", ""),
            " ".join(program.get("keywords", [])),
            " ".join(program.get("institutions", [])),
        ]).lower()

        if desired_level and desired_level in program.get("level", "").lower():
            score += 6
        elif not desired_level:
            score += 1

        if any(term in haystack for term in interests):
            score += 4
        if any(term in haystack for term in goals.split()):
            score += 2
        if "class 10" in class_level and "Diploma" in program.get("level", ""):
            score += 3
        if "class 12" in class_level and program.get("level") == "Undergraduate":
            score += 3
        if "ug" in class_level or "graduat" in class_level or "post" in class_level:
            score += 1
        if location and any(location in institution.lower() for institution in program.get("institutions", [])):
            score += 2

        ranked.append(
            {
                "level": program.get("level", ""),
                "field": program.get("field", ""),
                "title": program.get("title", ""),
                "best_for": program.get("best_for", ""),
                "institutions": program.get("institutions", []),
                "note": program.get("note", ""),
                "entry_after": program.get("entry_after", []),
                "score": score,
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:top_n]


def recommend_field_pathways(field_interest, student_profile=None, kb=None, top_n=3, ai_client=None):
    """Return complete class 11 through postgraduate pathways for a field of interest.

    If an AI client is provided, pathway recommendations are generated via the API.
    Otherwise legacy KB-based scoring is used as a fallback.
    """
    profile = student_profile or {}
    if ai_client is not None:
        return _recommend_field_pathways_ai(field_interest, profile, ai_client)

    if kb is None:
        kb = load_kb()

    pathways = kb.get("pathways", [])
    if not pathways:
        return []

    interests = [item.lower() for item in profile.get("interests", [])]
    location = (profile.get("location") or profile.get("city") or "").lower()
    class_level = (profile.get("class_level") or "").lower()
    field = (field_interest or "").strip().lower()

    field_terms = _tokenize_text(field)
    location_terms = _tokenize_text(location)
    ranked = []
    matching_field_paths = []
    for pathway in pathways:
        aliases = [pathway.get("field", ""), *pathway.get("aliases", [])]
        alias_terms_list = [_tokenize_text(alias) for alias in aliases]
        haystack = " ".join([alias.lower() for alias in aliases] + interests)
        score = 0

        field_matches = False
        if field_terms:
            for alias, alias_terms in zip(aliases, alias_terms_list):
                if alias.lower() == field or field_terms == alias_terms:
                    field_matches = True
                    break
                if alias_terms and field_terms and (field_terms <= alias_terms or alias_terms <= field_terms):
                    field_matches = True
                    break

        if field_matches:
            score += 8

        interest_hits = sum(1 for term in interests if re.search(rf"\b{re.escape(term)}\b", haystack))
        if interest_hits:
            score += 3 + min(2, interest_hits - 1)

        if class_level:
            if "class 10" in class_level:
                if pathway.get("class_11"):
                    score += 2
                if "class 10" in pathway.get("class_12", {}).get("diploma_route", {}).get("available_after", "").lower():
                    score += 1
            if "class 11" in class_level:
                if pathway.get("class_11"):
                    score += 3
                if pathway.get("class_12", {}).get("undergraduate_routes"):
                    score += 2
            if "class 12" in class_level:
                if pathway.get("class_12", {}).get("undergraduate_routes"):
                    score += 4
                if pathway.get("class_12", {}).get("diploma_route"):
                    score += 2
            if any(tok in class_level for tok in ["ug", "undergraduate", "graduat", "completion"]):
                if pathway.get("class_12", {}).get("postgraduate_routes"):
                    score += 5

        institution_names = (
            pathway.get("class_12", {}).get("undergraduate_institutions", [])
            + pathway.get("class_12", {}).get("postgraduate_institutions", [])
            + pathway.get("class_12", {}).get("diploma_route", {}).get("institutions", [])
        )
        if location:
            location_matches = sum(1 for institution in institution_names if location in institution.lower())
            score += min(location_matches, 3)
            if location_terms and any(term in " ".join(institution_names).lower() for term in location_terms):
                score += 1

        item = {
            **pathway,
            "score": score,
        }
        ranked.append(item)
        if field_matches:
            matching_field_paths.append(item)

    if field and matching_field_paths:
        matching_field_paths.sort(key=lambda item: item["score"], reverse=True)
        return matching_field_paths[:top_n]

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:top_n]

if __name__ == "__main__":
    demo = {"interests": ["Programming", "Python"], "completed": [], "goals": "software developer"}
    kb = load_kb()
    print(recommend_courses(demo, kb))
