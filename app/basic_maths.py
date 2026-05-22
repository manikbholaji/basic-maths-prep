from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Sequence


MATH_TOPICS = [
    {
        "id": "number-sense",
        "title": "Number Sense & Operations",
        "stages": ("primary", "middle"),
        "skills": ["place value", "four operations", "mental maths", "estimation"],
        "practice": "Do 10 quick mental maths questions and explain the shortcut you used.",
        "common_mistake": "Skipping estimation and making avoidable calculation errors.",
    },
    {
        "id": "fractions-decimals-percentages",
        "title": "Fractions, Decimals & Percentages",
        "stages": ("middle", "senior"),
        "skills": ["equivalence", "conversion", "percentage change", "ratio links"],
        "practice": "Convert between fractions, decimals, and percentages in both directions.",
        "common_mistake": "Forgetting to simplify or convert to the same form before comparing.",
    },
    {
        "id": "ratio-proportion",
        "title": "Ratio, Proportion & Unitary Method",
        "stages": ("middle", "senior"),
        "skills": ["sharing", "scale factors", "direct variation", "proportional reasoning"],
        "practice": "Solve 5 real-life ratio problems from recipes, maps, or pricing.",
        "common_mistake": "Cross-multiplying too early without checking if quantities are comparable.",
    },
    {
        "id": "algebra-foundations",
        "title": "Algebra Foundations",
        "stages": ("senior",),
        "skills": ["expressions", "substitution", "linear equations", "inequalities"],
        "practice": "Expand, simplify, and solve one- and two-step expressions until the steps feel automatic.",
        "common_mistake": "Mixing up signs when moving terms across the equals sign.",
    },
    {
        "id": "geometry-measurement",
        "title": "Geometry & Measurement",
        "stages": ("middle", "senior"),
        "skills": ["angles", "triangles", "congruence", "scale drawing"],
        "practice": "Draw one diagram carefully and label every known value before solving.",
        "common_mistake": "Starting calculations before the diagram is fully labeled.",
    },
    {
        "id": "mensuration",
        "title": "Mensuration & Surface Area",
        "stages": ("senior",),
        "skills": ["area", "volume", "surface area", "nets"],
        "practice": "List the formula, substitute the values, then check the units.",
        "common_mistake": "Using the wrong formula for area vs. perimeter vs. volume.",
    },
    {
        "id": "data-probability",
        "title": "Data Handling & Probability",
        "stages": ("middle", "senior"),
        "skills": ["tables", "bar graphs", "mean", "probability"],
        "practice": "Read one chart and write three observations and one conclusion.",
        "common_mistake": "Reporting the graph instead of interpreting the pattern.",
    },
    {
        "id": "exam-strategy",
        "title": "Exam Strategy & Review",
        "stages": ("primary", "middle", "senior"),
        "skills": ["timing", "error analysis", "revision cycles", "mock tests"],
        "practice": "Review every mistake notebook page and rewrite the correct method once.",
        "common_mistake": "Only practicing new questions and never revisiting weak spots.",
    },
]


STAGE_BY_GRADE = {
    "class 1": "primary",
    "class 2": "primary",
    "class 3": "primary",
    "class 4": "primary",
    "class 5": "primary",
    "class 6": "middle",
    "class 7": "middle",
    "class 8": "middle",
    "class 9": "senior",
    "class 10": "senior",
    "class 11": "senior",
    "class 12": "senior",
}


FOCUS_BY_GOAL = {
    "confidence": ["number-sense", "fractions-decimals-percentages", "geometry-measurement"],
    "exam prep": ["exam-strategy", "algebra-foundations", "mensuration"],
    "homework": ["algebra-foundations", "ratio-proportion", "data-probability"],
    "speed": ["number-sense", "exam-strategy", "fractions-decimals-percentages"],
}


def default_profile() -> Dict[str, object]:
    return {
        "student_name": "",
        "email": "",
        "grade": "Class 8",
        "board": "CBSE",
        "goal": "Exam prep",
        "weak_topics": [],
        "city": "",
        "preferred_study_time": "Evening",
        "exam_date": None,
        "pace": "Balanced",
    }


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _stage_for_grade(grade: object) -> str:
    grade_text = _clean_text(grade).lower()
    return STAGE_BY_GRADE.get(grade_text, "secondary")


def _goal_key(goal: object) -> str:
    goal_text = _clean_text(goal).lower()
    if "confidence" in goal_text:
        return "confidence"
    if "speed" in goal_text:
        return "speed"
    if "homework" in goal_text:
        return "homework"
    return "exam prep"


def profile_summary(profile: Dict[str, object]) -> str:
    grade = _clean_text(profile.get("grade") or "Class 8")
    board = _clean_text(profile.get("board") or "Board")
    goal = _clean_text(profile.get("goal") or "Exam prep")
    city = _clean_text(profile.get("city"))
    parts = [f"Grade: {grade}", f"Board: {board}", f"Goal: {goal}"]
    if city:
        parts.append(f"City: {city}")
    return " • ".join(parts)


def quick_starters(profile: Dict[str, object]) -> List[str]:
    stage = _stage_for_grade(profile.get("grade"))
    if stage == "primary":
        return [
            "Help me build a simple daily maths routine.",
            "Explain fractions with one real-life example.",
            "Give me 5 quick mental maths practice questions.",
        ]
    if stage == "middle":
        return [
            "Which topics should I revise first this week?",
            "Show me a smart way to solve ratio questions.",
            "How do I avoid calculation mistakes in maths tests?",
        ]
    return [
        "Make a 7-day maths revision plan.",
        "Help me improve speed in algebra and geometry.",
        "Which topics are most likely to lose marks in exams?",
    ]


def _topic_score(topic: Dict[str, object], profile: Dict[str, object]) -> int:
    score = 0
    stage = _stage_for_grade(profile.get("grade"))
    goal_key = _goal_key(profile.get("goal"))
    weak_topics = {str(item).strip().lower() for item in profile.get("weak_topics", []) if item}

    if stage in topic.get("stages", ()):
        score += 5
    if goal_key in FOCUS_BY_GOAL and topic["id"] in FOCUS_BY_GOAL[goal_key]:
        score += 4
    if topic["id"] in weak_topics:
        score += 6
    if stage == "senior" and topic["id"] in {"algebra-foundations", "mensuration", "exam-strategy"}:
        score += 2
    if stage == "primary" and topic["id"] in {"number-sense", "fractions-decimals-percentages"}:
        score += 2
    return score


def recommend_topics(profile: Dict[str, object], top_n: int = 4) -> List[Dict[str, object]]:
    ranked = sorted(MATH_TOPICS, key=lambda item: (_topic_score(item, profile), item["title"]), reverse=True)
    recommendations = []
    for topic in ranked[:top_n]:
        recommendations.append(
            {
                "id": topic["id"],
                "title": topic["title"],
                "why": _build_reason(topic, profile),
                "practice": topic["practice"],
                "common_mistake": topic["common_mistake"],
                "skills": list(topic["skills"]),
            }
        )
    return recommendations


def _build_reason(topic: Dict[str, object], profile: Dict[str, object]) -> str:
    stage = _stage_for_grade(profile.get("grade"))
    goal_key = _goal_key(profile.get("goal"))
    reasons = []
    if stage in topic.get("stages", ()):
        reasons.append(f"fits the {stage} stage")
    if topic["id"] in profile.get("weak_topics", []):
        reasons.append("matches a selected weak topic")
    if topic["id"] in FOCUS_BY_GOAL.get(goal_key, []):
        reasons.append("supports the current study goal")
    if not reasons:
        reasons.append("keeps the foundation balanced")
    return ", ".join(reasons[:2]).capitalize()


def build_dashboard_metrics(profile: Dict[str, object], practice_attempts: int = 0) -> Dict[str, object]:
    weak_topics = list(profile.get("weak_topics", []) or [])
    stage = _stage_for_grade(profile.get("grade"))
    progress = 72 if stage == "primary" else 65 if stage == "middle" else 58
    progress = max(30, progress - (len(weak_topics) * 3))
    accuracy = max(42, min(98, 88 - len(weak_topics) * 4 + (practice_attempts // 2)))
    next_level = {
        "primary": "Middle-school confidence",
        "middle": "Secondary problem solving",
        "senior": "Exam-ready algebra",
    }.get(stage, "Exam-ready algebra")
    return {
        "progress": progress,
        "accuracy": accuracy,
        "next_level": next_level,
        "weak_spots": len(weak_topics) or 3,
        "attempts": practice_attempts,
    }


def build_week_plan(profile: Dict[str, object]) -> List[Dict[str, object]]:
    stage = _stage_for_grade(profile.get("grade"))
    recommendations = recommend_topics(profile, top_n=3)
    primary_focus = recommendations[0]["title"] if recommendations else "Core maths"

    if stage == "primary":
        plan = [
            ("Mon", "Number games", "10 minutes of mental maths and skip-counting."),
            ("Tue", "Visual practice", "Draw and label shapes or number lines."),
            ("Wed", "Fractions", f"Practice {primary_focus.lower()} using real objects."),
            ("Thu", "Timed review", "Solve a short worksheet without help."),
            ("Fri", "Explain it aloud", "Teach one topic to a parent or friend."),
        ]
    elif stage == "middle":
        plan = [
            ("Mon", "Warm-up", "Mental maths and formula recall for 15 minutes."),
            ("Tue", "Concept build", f"Study {primary_focus.lower()} with worked examples."),
            ("Wed", "Practice set", "Solve 8 mixed questions and mark every error."),
            ("Thu", "Application", "Use ratios, percentages, or geometry in word problems."),
            ("Fri", "Mini test", "Attempt a timed quiz and correct it immediately."),
        ]
    else:
        plan = [
            ("Mon", "Formula recap", "Review formulas, identities, and shortcut rules."),
            ("Tue", "Solved examples", f"Work on {primary_focus.lower()} with board-style questions."),
            ("Wed", "Timed drill", "Attempt a 30-minute mixed practice set."),
            ("Thu", "Error log", "Rewrite every incorrect answer and note the mistake type."),
            ("Fri", "Mock revision", "Finish with a short mock test and score it honestly."),
        ]

    return [
        {"day": day, "title": title, "description": description}
        for day, title, description in plan
    ]


def build_revision_timeline(profile: Dict[str, object]) -> List[Dict[str, str]]:
    exam_date = profile.get("exam_date")
    if isinstance(exam_date, date):
        remaining = max((exam_date - date.today()).days, 0)
    else:
        remaining = 45

    checkpoints = [
        ("Now", "Cover the strongest weak topic first and build one-page notes."),
        ("This week", "Complete one timed practice set and review mistakes."),
        ("Next 2 weeks", "Start mixed-topic revision and improve speed."),
        ("Final stretch", f"Run two mock tests before the exam ({remaining} days remaining)."),
    ]

    return [{"label": label, "note": note} for label, note in checkpoints]


def build_topic_cards(profile: Dict[str, object]) -> List[Dict[str, object]]:
    cards = []
    for item in recommend_topics(profile, top_n=4):
        cards.append(
            {
                "title": item["title"],
                "subtitle": item["why"],
                "practice": item["practice"],
                "mistake": item["common_mistake"],
            }
        )
    return cards


def _heuristic_reply(prompt: str, profile: Dict[str, object]) -> str:
    prompt_text = _clean_text(prompt).lower()
    stage = _stage_for_grade(profile.get("grade"))
    recommendations = recommend_topics(profile, top_n=3)
    first_topic = recommendations[0]["title"] if recommendations else "Core maths"
    profile_text = profile_summary(profile)

    if any(word in prompt_text for word in ["fractions", "percent", "ratio", "decimal"]):
        return (
            f"For {profile_text}, focus on one clean conversion method and practice it step by step. "
            f"Start with {first_topic}, then solve 5 short problems and check every unit or percentage change."
        )
    if any(word in prompt_text for word in ["plan", "schedule", "revision", "timetable"]):
        return (
            f"For {profile_text}, a good {stage} revision plan should mix recap, practice, and correction. "
            f"Use {first_topic} as the main focus, keep one timed drill each week, and finish with error-log review."
        )
    if any(word in prompt_text for word in ["speed", "fast", "quick", "timed"]):
        return (
            f"For {profile_text}, build speed by using short timed sets, writing steps clearly, and checking the answer only after each question. "
            "The fastest gains usually come from number sense and one strong algebra routine."
        )
    return (
        f"Here is a practical next step for {profile_text}: "
        f"work on {first_topic}, solve a few mixed questions, and review one mistake before moving on."
    )


def generate_math_reply(prompt: str, profile: Dict[str, object], ai_client=None) -> str:
    if ai_client is not None:
        system_prompt = (
            "You are a friendly Basic Maths Prep coach for school students. "
            "Give short, structured advice that fits the learner's grade, board, city, and goal. "
            "Always include a practical next step and keep the answer grounded in basic maths revision."
        )
        user_prompt = (
            f"Student profile: {profile_summary(profile)}. "
            f"Weak topics: {', '.join(profile.get('weak_topics', [])) or 'None'}. "
            f"Question: {prompt}"
        )
        try:
            response = ai_client.send_message(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            if isinstance(response, str) and response.strip():
                return response.strip()
        except Exception:
            pass
    return _heuristic_reply(prompt, profile)


def build_learning_summary(profile: Dict[str, object]) -> Dict[str, object]:
    recommendations = recommend_topics(profile)
    return {
        "profile_summary": profile_summary(profile),
        "quick_starters": quick_starters(profile),
        "recommendations": recommendations,
        "week_plan": build_week_plan(profile),
        "revision_timeline": build_revision_timeline(profile),
        "topic_cards": build_topic_cards(profile),
        "dashboard": build_dashboard_metrics(profile),
    }


def ensure_date(value: object):
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value).date()
        except Exception:
            return None
    return None
