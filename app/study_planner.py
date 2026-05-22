"""Simple class-wise study plans for Indian boards (CBSE/ICSE/PSEB).

This is a minimal, data-driven planner that returns a short guidance outline for Classes 9-12.
"""

PLANS = {
    "cbse": {
        "class 9": "Focus on building concepts in Mathematics and Science. Weekly plan: 4 theory sessions, 2 problem-solving sessions, 1 revision/notes session. Keep NCERT solved examples up to date.",
        "class 10": "Prioritise NCERT chapter-wise practice, past year questions, and sample papers. Monthly full-length tests and focused weak-topic drills.",
        "class 11": "Start stream foundations: Physics/Chemistry/Maths fundamentals for Science; strengthen basics for Commerce/Arts. Regular assignments and lab skills for Science streams.",
        "class 12": "Board-focused revision: timed practice papers, concept mapping, formula sheet consolidation, and practical mock exams. Plan 8-10 weeks of dedicated revision before boards.",
    },
    "icse": {
        "class 9": "Emphasise English language and project skills along with strong topic understanding in Science and Math. Regular writing practice and project checkpoints.",
        "class 10": "Balanced focus on literature and language, project work completion, and disciplined revision schedule. Use sample ICSE papers for practice.",
        "class 11": "Build analytical habits and long-answer practice for humanities, or mathematical rigour for science. Begin NCERT/ICSE references early.",
        "class 12": "ICSE board prep requires past papers, project polish, and timed writing practice for language papers. Ensure project submission standards are met.",
    },
    "pseb": {
        "class 9": "Follow PSEB textbooks closely; strengthen Punjabi/English comprehension and basic science lab skills. Weekly chapter revision and exercise completion.",
        "class 10": "Punjab board exam prep: chapter-wise revision, previous PSEB papers, and practical preparations. Maintain attendance and internal assessment submissions.",
        "class 11": "Stream selection guidance: begin subject depth and practical work for Science; commerce basics for business studies aspirants.",
        "class 12": "Senior Secondary focus: exam-oriented practice, subject-specific revision plans, project and practical readiness, and time management drills.",
    }
}


def get_study_plan(board, class_level):
    if not board:
        return "Please specify a board (CBSE, ICSE, or PSEB) to get a tailored study plan."
    b = board.strip().lower()
    cl = (class_level or "").strip().lower()
    # Normalize common inputs
    if cl.startswith("class"):
        key = cl
    elif cl.startswith("9"):
        key = "class 9"
    elif cl.startswith("10"):
        key = "class 10"
    elif cl.startswith("11"):
        key = "class 11"
    elif cl.startswith("12"):
        key = "class 12"
    else:
        key = cl or "class 10"

    if b in PLANS and key in PLANS[b]:
        return PLANS[b][key]

    # fallback: try mapping pseb -> state
    if b in ("punjab", "pseb") and key in PLANS.get("pseb", {}):
        return PLANS["pseb"][key]

    return "No study plan found for the selected board/class. You can choose CBSE, ICSE, or PSEB and Class 9-12."


if __name__ == "__main__":
    print(get_study_plan("CBSE", "Class 10"))
