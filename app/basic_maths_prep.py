from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from app import appointments


BOARD_GUIDANCE = {
    "cbse": {
        "exam_style": "NCERT-first, stepwise practice, and chapter weightage tracking",
        "planning": "Use short daily drills and a weekly mock test to prevent backlog.",
    },
    "icse": {
        "exam_style": "concept clarity, written explanation, and mixed-format question practice",
        "planning": "Blend theory revision with timed problem sets and presentation practice.",
    },
    "state board": {
        "exam_style": "textbook mastery, worked examples, and board-paper pattern practice",
        "planning": "Follow the official syllabus sequence and revise every chapter twice.",
    },
}


TOPIC_LIBRARY = {
    "foundation": [
        "number sense and arithmetic fluency",
        "fractions, decimals, ratios, and percentages",
        "speed, accuracy, and mental calculation habits",
    ],
    "middle_school": [
        "factors, multiples, primes, and integers",
        "simple equations and pattern recognition",
        "geometry basics, perimeter, area, and angle rules",
    ],
    "class_9": [
        "linear equations in one variable",
        "coordinate geometry and graph reading",
        "mensuration and data handling",
    ],
    "class_10": [
        "algebraic identities and quadratic fundamentals",
        "surface area, volume, and trigonometry basics",
        "statistics, probability, and board-style reasoning",
    ],
    "advanced": [
        "functions, transformations, and proof-style reasoning",
        "application-based problem solving",
        "time-bound revision and mock analysis",
    ],
}


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _class_bucket(class_level: Optional[str]) -> str:
    normalized = _normalize(class_level)
    if normalized.startswith("class 6") or normalized.startswith("class 7") or normalized.startswith("class 8"):
        return "middle_school"
    if normalized.startswith("class 9"):
        return "class_9"
    if normalized.startswith("class 10"):
        return "class_10"
    if normalized.startswith("class 11") or normalized.startswith("class 12"):
        return "advanced"
    return "foundation"


def _profile_summary(profile: Dict[str, str]) -> str:
    pieces = []
    for label, key in [("Board", "board"), ("Class", "class_level"), ("Goal", "goal"), ("City", "city")]:
        value = (profile.get(key) or "").strip()
        if value and value.lower() != "auto":
            pieces.append(f"{label}: {value}")
    return " • ".join(pieces) if pieces else "Self-paced maths prep"


def build_recommendations(profile: Dict[str, str], weak_topics: Optional[List[str]] = None) -> List[Dict[str, str]]:
    class_bucket = _class_bucket(profile.get("class_level"))
    board = _normalize(profile.get("board"))
    board_hint = BOARD_GUIDANCE.get(board, BOARD_GUIDANCE["cbse"])

    topic_focus = TOPIC_LIBRARY[class_bucket]
    recommendations = [
        {
            "title": "Priority topic ladder",
            "detail": f"Start with {topic_focus[0]}, then move to {topic_focus[1]}, and finish with {topic_focus[2]}. This keeps practice ordered and visible.",
            "action": "Make one page of notes for each topic and solve 15 questions before moving on.",
        },
        {
            "title": "Board-aligned practice",
            "detail": f"{board.upper() if board else 'Your board'} works best with {board_hint['exam_style']}. {board_hint['planning']}",
            "action": "Add one board-pattern worksheet to every study session.",
        },
        {
            "title": "Exam-confidence routine",
            "detail": "Use a 3-step cycle: concept recap, timed problem set, then a short error-log review. It improves recall without burning time.",
            "action": "Close every session by writing one formula, one mistake, and one corrected answer.",
        },
    ]

    if weak_topics:
        focus_text = ", ".join(topic.strip() for topic in weak_topics if topic.strip())
        if focus_text:
            recommendations.insert(
                1,
                {
                    "title": "Weak-topic recovery",
                    "detail": f"Your current focus areas are {focus_text}. Revisit them in short bursts before practice papers so the gap closes faster.",
                    "action": "Spend 20 minutes on each weak topic, then solve 5 mixed questions.",
                },
            )

    if class_bucket == "advanced":
        recommendations.append(
            {
                "title": "Mock-test strategy",
                "detail": "For Class 11 and 12 students, the best lift comes from timed full-length papers and reviewing every skipped question.",
                "action": "Run one full mock each weekend and note every error category.",
            }
        )

    return recommendations[:4]


def build_study_plan(profile: Dict[str, str], days: int = 7) -> List[Dict[str, str]]:
    class_bucket = _class_bucket(profile.get("class_level"))
    topic_focus = TOPIC_LIBRARY[class_bucket]
    plan = []
    for index in range(days):
        day_number = index + 1
        topic = topic_focus[index % len(topic_focus)]
        plan.append(
            {
                "day": f"Day {day_number}",
                "focus": topic,
                "task": f"Complete a 25-minute concept review, a 20-minute timed drill, and a 10-minute error-log correction on {topic}.",
            }
        )
    return plan


def build_quiz_bank(profile: Dict[str, str]) -> List[Dict[str, str]]:
    class_bucket = _class_bucket(profile.get("class_level"))
    if class_bucket == "advanced":
        return [
            {"topic": "Functions", "question": "What does a function graph tell you about growth and turning points?"},
            {"topic": "Probability", "question": "How do you identify the sample space before calculating probability?"},
            {"topic": "Vectors", "question": "What is the difference between magnitude and direction?"},
        ]
    if class_bucket == "class_10":
        return [
            {"topic": "Algebra", "question": "Why do algebraic identities help you factorise faster?"},
            {"topic": "Trigonometry", "question": "When should you use sine, cosine, or tangent in a right triangle?"},
            {"topic": "Statistics", "question": "How do mean, median, and mode describe a data set differently?"},
        ]
    if class_bucket == "class_9":
        return [
            {"topic": "Linear Equations", "question": "How do you isolate the variable in a one-variable equation?"},
            {"topic": "Graphs", "question": "What does the slope of a line show in coordinate geometry?"},
            {"topic": "Mensuration", "question": "Why is unit consistency important in area and volume problems?"},
        ]
    return [
        {"topic": "Foundations", "question": "How do place value and estimation improve calculation speed?"},
        {"topic": "Patterns", "question": "How do you spot a repeating pattern in a sequence?"},
        {"topic": "Geometry", "question": "What is the difference between perimeter and area?"},
    ]


def suggest_next_slot(preferred_date: Optional[date] = None) -> Tuple[date, str]:
    target_date = preferred_date or date.today()
    slots = appointments.list_working_hours(start_hour=10, end_hour=18, step_minutes=30)
    if slots:
        return target_date, slots[0]
    return target_date + timedelta(days=1), "10:00"


def auto_schedule_appointment(
    student_name: str,
    email: str,
    profile: Dict[str, str],
    notes: str = "",
    preferred_date: Optional[date] = None,
):
    appointment_date, appointment_time = suggest_next_slot(preferred_date)
    appointment_when = datetime.combine(
        appointment_date,
        datetime.strptime(appointment_time, "%H:%M").time(),
    ).isoformat(timespec="minutes")
    combined_notes = notes.strip()
    profile_note = _profile_summary(profile)
    if profile_note:
        combined_notes = f"{combined_notes} | Profile: {profile_note}".strip(" |")
    return appointments.book_appointment(student_name, email, appointment_when, advisor="Basic Maths Prep Coach", notes=combined_notes)


def build_recommendation_header(profile: Dict[str, str]) -> str:
    return f"Personalized for {_profile_summary(profile)}"
