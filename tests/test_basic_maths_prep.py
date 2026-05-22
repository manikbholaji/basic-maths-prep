from pathlib import Path

from app import appointments
from app import basic_maths


def test_recommend_topics_prioritize_weak_areas():
    profile = {
        "grade": "Class 10",
        "board": "CBSE",
        "goal": "Exam prep",
        "weak_topics": ["algebra-foundations"],
        "city": "Mumbai",
    }

    recommendations = basic_maths.recommend_topics(profile, top_n=3)

    assert recommendations
    assert recommendations[0]["id"] == "algebra-foundations"
    assert "practice" in recommendations[0]


def test_week_plan_has_five_days():
    profile = {"grade": "Class 8", "goal": "Confidence building"}

    plan = basic_maths.build_week_plan(profile)

    assert len(plan) == 5
    assert plan[0]["day"] == "Mon"
    assert all("description" in item for item in plan)


def test_generate_math_reply_includes_profile_context_without_ai_client():
    profile = {
        "student_name": "Aanya",
        "grade": "Class 10",
        "board": "CBSE",
        "goal": "Exam prep",
        "city": "Pune",
        "weak_topics": ["algebra-foundations"],
    }

    reply = basic_maths.generate_math_reply("What should I revise next for maths?", profile, ai_client=None)

    assert "Class 10" in reply
    assert "Aanya" in reply or "Pune" in reply


def test_auto_schedule_appointment_uses_next_available_slot(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    appointments.DATA_DIR = str(data_dir)
    appointments.APPT_FILE = str(Path(data_dir) / "appointments.json")

    profile = {
        "student_name": "Aanya",
        "email": "aanya@example.com",
        "grade": "Class 9",
        "board": "ICSE",
        "goal": "Exam prep",
        "city": "Pune",
    }

    booking = appointments.auto_schedule_appointment(
        student_name="Aanya",
        email="aanya@example.com",
        topic="Algebra Foundations",
        profile=profile,
    )

    assert booking["student_name"] == "Aanya"
    assert booking["topic"] == "Algebra Foundations"
    assert booking["auto_scheduled"] is True
    assert Path(appointments.APPT_FILE).exists()
