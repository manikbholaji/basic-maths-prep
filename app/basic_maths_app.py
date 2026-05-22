from __future__ import annotations

import os
import sys
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api_client import AIClient
from app import analytics_module
from app import appointments
from app import basic_maths
from app import mcq_manager


def _render_math_text(txt: str):
    """Render text preferring LaTeX/math formatting when appropriate."""
    if not txt:
        return
    s = str(txt)
    # If the string already contains LaTeX markers, render as markdown (Streamlit will render math)
    if '$' in s or '\\(' in s or '\\)' in s or '\\frac' in s or '\\sqrt' in s:
        st.markdown(s)
        return
    # Heuristic: if it looks like an equation or contains x, =, ^, /, or digits with variables, render as latex
    if re.search(r"=|\^|\\frac|\\sqrt|\bx\b|\d+[a-zA-Z]|[a-zA-Z]\^\d|/", s):
        try:
            # try to render as LaTeX math
            st.latex(s)
            return
        except Exception:
            st.markdown(s)
            return
    # default: markdown paragraph
    st.markdown(s)


st.set_page_config(
    page_title="Basic Maths Prep",
    page_icon="➗",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
<style>
    :root {
        --paper: #f6fafb;
        --ink: #10233f;
        --muted: #5a6b7b;
        --accent: #0f6b6a;
        --accent-soft: #e7f5f4;
        --line: #dde7ec;
        --shadow: rgba(16, 35, 63, 0.06);
    }

    .stApp {
        background: var(--paper);
        color: var(--ink);
        font-family: "Aptos", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    }

    h1, h2, h3, h4 {
        font-family: "Aptos Display", "Aptos", "Segoe UI", Arial, sans-serif;
        color: var(--ink) !important;
        letter-spacing: -0.01em;
    }

    p, li, label, .stMarkdown, .stTextInput, .stSelectbox, .stRadio, .stCheckbox {
        color: var(--ink);
    }

    .bm-hero-title {
        font-weight: 700;
        font-size: clamp(1.8rem, 4vw, 3rem);
        line-height: 1.02;
        margin: 0 0 0.5rem 0;
        max-width: 42ch;
    }

    .bm-hero-copy {
        color: var(--muted);
        font-size: 1rem;
        line-height: 1.6;
        max-width: 62ch;
    }

    .bm-eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 0.72rem;
        color: var(--muted);
        margin-bottom: 0.6rem;
    }

    .bm-panel {
        background: white;
        border: 1px solid var(--line);
        border-radius: 10px;
        box-shadow: 0 6px 18px var(--shadow);
        padding: 1rem;
    }

    .bm-index-item { padding: 0.5rem 0; border-bottom: 1px dashed var(--line); }
    .bm-index-item:last-child { border-bottom: none; }

    .bm-card { background: white; border: 1px solid var(--line); border-radius: 10px; padding: 1rem; height:100%; }
    .bm-card h4 { margin-top: 0; margin-bottom: 0.35rem; }
    .bm-card p { margin: 0; color: var(--muted); }

    .bm-pill { display:inline-block; border-radius:999px; border:1px solid var(--line); padding:0.25rem 0.6rem; margin:0.2rem; font-size:0.78rem; color:var(--ink); background:var(--accent-soft); }

    .bm-divider { height:1px; background:linear-gradient(90deg,var(--line),transparent); margin:1rem 0; }

    .bm-note {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 0.85rem 1rem;
        color: var(--muted);
    }

    .stButton > button { border-radius:8px; border: none; background: var(--accent); color: white; font-weight:600; padding:0.6rem 0.85rem }
    .stButton > button:hover { filter:brightness(0.95); }

    section[data-testid="stSidebar"] { background: linear-gradient(180deg,#ffffff 0%, #f7fbfc 100%); border-right: 1px solid var(--line); }
</style>
""",
    unsafe_allow_html=True,
)


def _load_secrets():
    try:
        return {
            "OPENAI_API_KEY": st.secrets.get("OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY"),
            "GOOGLE_API_KEY": st.secrets.get("GOOGLE_API_KEY", None) or os.environ.get("GOOGLE_API_KEY"),
        }
    except Exception:
        return {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY"),
        }


def _resolve_provider(choice, secrets):
    if choice == "Auto (recommended)":
        if secrets.get("OPENAI_API_KEY"):
            return "OpenAI"
        if secrets.get("GOOGLE_API_KEY"):
            return "Google"
        return "Mock"
    return choice


def _provider_key(provider, secrets):
    if provider == "OpenAI":
        return secrets.get("OPENAI_API_KEY")
    if provider == "Google":
        return secrets.get("GOOGLE_API_KEY")
    return None


def _debug_mode_enabled(secrets: dict | None = None) -> bool:
    env_value = str(os.environ.get("MATHS_SHOW_ADMIN", "")).strip().lower()
    if env_value in {"1", "true", "yes", "on"}:
        return True
    try:
        if secrets and str(secrets.get("MATHS_SHOW_ADMIN", "")).strip().lower() in {"1", "true", "yes", "on"}:
            return True
    except Exception:
        pass
    return False


def _init_state():
    defaults = basic_maths.default_profile()
    if "maths_profile_saved" not in st.session_state:
        st.session_state.maths_profile_saved = deepcopy(defaults)
    if "maths_profile_draft" not in st.session_state:
        st.session_state.maths_profile_draft = deepcopy(st.session_state.maths_profile_saved)
    if "maths_nav" not in st.session_state:
        st.session_state.maths_nav = "Dashboard"
    if "maths_prompt" not in st.session_state:
        st.session_state.maths_prompt = ""
    if "maths_chat" not in st.session_state:
        st.session_state.maths_chat = []
    if "maths_quiz_result" not in st.session_state:
        st.session_state.maths_quiz_result = None
    if "maths_booking" not in st.session_state:
        st.session_state.maths_booking = None


def _draft_profile_from_state() -> dict:
    return {
        "student_name": st.session_state.get("maths_draft_student_name", ""),
        "email": st.session_state.get("maths_draft_email", ""),
        "grade": st.session_state.get("maths_draft_grade", "Class 8"),
        "board": st.session_state.get("maths_draft_board", "CBSE"),
        "goal": st.session_state.get("maths_draft_goal", "Exam prep"),
        "weak_topics": st.session_state.get("maths_draft_weak_topics", []),
        "city": st.session_state.get("maths_draft_city", ""),
        "preferred_study_time": st.session_state.get("maths_draft_study_time", "Evening"),
        "exam_date": st.session_state.get("maths_draft_exam_date"),
        "pace": st.session_state.get("maths_draft_pace", "Balanced"),
    }


def _sync_draft_widgets(profile: dict):
    st.session_state.maths_draft_student_name = profile.get("student_name", "")
    st.session_state.maths_draft_email = profile.get("email", "")
    st.session_state.maths_draft_grade = profile.get("grade", "Class 8")
    st.session_state.maths_draft_board = profile.get("board", "CBSE")
    st.session_state.maths_draft_goal = profile.get("goal", "Exam prep")
    st.session_state.maths_draft_weak_topics = list(profile.get("weak_topics", []))
    st.session_state.maths_draft_city = profile.get("city", "")
    st.session_state.maths_draft_study_time = profile.get("preferred_study_time", "Evening")
    st.session_state.maths_draft_exam_date = profile.get("exam_date")
    st.session_state.maths_draft_pace = profile.get("pace", "Balanced")


def _build_ai_client():
    secrets = _load_secrets()
    with st.sidebar.expander("Teacher / admin settings", expanded=False):
        st.caption("Use this only while testing the assistant backend.")
        provider_choice = st.selectbox("AI provider", ["Auto (recommended)", "OpenAI", "Google", "Mock"], index=0)
    provider = _resolve_provider(provider_choice, secrets)
    api_key = _provider_key(provider, secrets)
    if provider == "Mock":
        return AIClient(provider="Mock"), provider
    return AIClient(provider=provider, api_key=api_key), provider


def _render_profile_form():
    topics = [topic["title"] for topic in basic_maths.MATH_TOPICS]
    exam_default = st.session_state.maths_profile_saved.get("exam_date") or (date.today() + timedelta(days=60))

    with st.sidebar.form("maths_profile_form", clear_on_submit=False):
        st.markdown("<div class='bm-note'>Profile details are used only to personalise maths recommendations, diagnostics, and scheduling.</div>", unsafe_allow_html=True)
        st.text_input("Student name", key="maths_draft_student_name")
        st.text_input("Email", key="maths_draft_email")
        st.selectbox("Grade", ["Class 3", "Class 4", "Class 5", "Class 6", "Class 7", "Class 8", "Class 9", "Class 10", "Class 11", "Class 12"], key="maths_draft_grade")
        st.selectbox("Board", ["CBSE", "ICSE", "State Board", "Other"], key="maths_draft_board")
        st.selectbox("Goal", ["Exam prep", "Homework help", "Confidence building", "Speed and accuracy"], key="maths_draft_goal")
        st.multiselect("Weak topics", topics, key="maths_draft_weak_topics")
        st.text_input("City / district", key="maths_draft_city")
        st.selectbox("Preferred study time", ["Morning", "Afternoon", "Evening", "Weekend"], key="maths_draft_study_time")
        st.selectbox("Pace", ["Light", "Balanced", "Intensive"], key="maths_draft_pace")
        st.date_input("Exam date", value=exam_default, min_value=date.today(), key="maths_draft_exam_date")
        save_clicked = st.form_submit_button("Save profile")

    st.session_state.maths_profile_draft = _draft_profile_from_state()
    if save_clicked:
        st.session_state.maths_profile_saved = deepcopy(st.session_state.maths_profile_draft)
        st.success("Study folio saved. The tutor will now use this profile.")
        st.rerun()

    st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='bm-eyebrow'>Saved profile</div>", unsafe_allow_html=True)
    st.caption(basic_maths.profile_summary(st.session_state.maths_profile_saved))
    if st.session_state.maths_profile_saved.get("weak_topics"):
        st.caption("Weak spots: " + ", ".join(st.session_state.maths_profile_saved.get("weak_topics", [])))


def _render_hero(profile, summary, dashboard):
    col_left, col_right = st.columns([1.7, 1.1])
    with col_left:
        st.markdown("<div class='bm-eyebrow'>Adaptive CBSE Maths Coaching</div>", unsafe_allow_html=True)
        st.markdown("<h1 class='bm-hero-title'>Personalised practice, precise diagnostics, and guided study planning.</h1>", unsafe_allow_html=True)
        st.markdown(
            "<p class='bm-hero-copy'>A professional maths prep desk for school learners. Choose your level, complete a 30-question diagnostic, receive domain-specific recommendations, and follow a study plan designed for CBSE success.</p>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='bm-panel'><div class='bm-eyebrow'>What this app delivers</div>"
            "<div class='bm-index-item'><strong>Diagnostic clarity</strong><br/><span style='color:#5a6b7b'>30 questions curated by grade and topic readiness.</span></div>"
            "<div class='bm-index-item'><strong>Targeted recommendations</strong><br/><span style='color:#5a6b7b'>Review incorrect answers and focus on the exact skills that need attention.</span></div>"
            "<div class='bm-index-item'><strong>Academic planning</strong><br/><span style='color:#5a6b7b'>Week-by-week practice tailored to the student stage and goals.</span></div>"
            "<div class='bm-index-item'><strong>Appointment scheduling</strong><br/><span style='color:#5a6b7b'>Auto-book coaching slots based on availability.</span></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        btn_left, btn_right = st.columns(2)
        if btn_left.button("Start a diagnostic"):
            st.session_state.maths_nav = "Practice Lab"
        if btn_right.button("Schedule support"):
            st.session_state.maths_nav = "Appointments"

        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        pills = [profile.get("grade", "Class 8"), profile.get("board", "CBSE"), profile.get("goal", "Exam prep"), profile.get("preferred_study_time", "Evening")]
        for value in pills:
            st.markdown(f"<span class='bm-pill'>{value}</span>", unsafe_allow_html=True)

    with col_right:
        next_practice = 'Weekly review'
        if isinstance(summary.get('week_plan'), list) and summary['week_plan']:
            next_practice = summary['week_plan'][0].get('title', next_practice)

        st.markdown(
            "<div class='bm-panel'>"
            "<div class='bm-eyebrow'>Study snapshot</div>"
            f"<div class='bm-index-item'><strong>Profile</strong><br/><span style='color:#6f6159'>{basic_maths.profile_summary(profile)}</span></div>"
            f"<div class='bm-index-item'><strong>Recommended focus</strong><br/><span style='color:#6f6159'>{summary['recommendations'][0]['title'] if summary['recommendations'] else 'Balanced review'}</span></div>"
            f"<div class='bm-index-item'><strong>Next practice</strong><br/><span style='color:#6f6159'>{next_practice}</span></div>"
            "</div>",
            unsafe_allow_html=True,
        )

    metrics = st.columns(4)
    metrics[0].metric("Attempts", dashboard["attempts"])
    metrics[1].metric("Accuracy", f"{dashboard['accuracy']}%")
    metrics[2].metric("Next level", dashboard["next_level"])
    metrics[3].metric("Weak topics", dashboard["weak_spots"])


def _render_topic_cards(profile):
    cards = basic_maths.build_topic_cards(profile)
    cols = st.columns(2)
    for index, card in enumerate(cards):
        with cols[index % 2]:
            st.markdown(
                f"""
                <div class='bm-card'>
                  <h4>{card['title']}</h4>
                  <p><strong>Why now:</strong> {card['subtitle']}</p>
                  <div class='bm-divider'></div>
                  <p><strong>Practice:</strong> {card['practice']}</p>
                  <p style='margin-top:0.45rem'><strong>Common mistake:</strong> {card['mistake']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_week_plan(profile):
    plan = basic_maths.build_week_plan(profile)
    cols = st.columns(5)
    for idx, item in enumerate(plan):
        with cols[idx % 5]:
            st.markdown(
                f"""
                <div class='bm-card'>
                  <h4>{item['day']}</h4>
                  <p><strong>{item['title']}</strong></p>
                  <p>{item['description']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_revision_timeline(profile):
    timeline = basic_maths.build_revision_timeline(profile)
    cols = st.columns(len(timeline))
    for idx, item in enumerate(timeline):
        with cols[idx]:
            st.markdown(
                f"""
                <div class='bm-card'>
                  <h4>{item['label']}</h4>
                  <p>{item['note']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_practice_lab(profile, ai_client, provider):
    st.markdown("<div class='bm-eyebrow'>Practice lab</div>", unsafe_allow_html=True)
    st.subheader("Ask the tutor")
    # If a practice set was requested from a recommendation card, render it first
    if st.session_state.get("maths_practice_questions"):
        questions = st.session_state.get("maths_practice_questions") or []
        with st.form("practice_form"):
            st.markdown(f"<div class='bm-eyebrow'>Practice: {len(questions)} questions</div>", unsafe_allow_html=True)
            for q in questions:
                _render_math_text(q.get("question", ""))
                choices = q.get("choices", []) or []
                labels = [chr(65 + i) for i in range(len(choices))]
                for idx_c, choice in enumerate(choices):
                    st.markdown(f"**{labels[idx_c]}.** ")
                    _render_math_text(choice)
                st.radio("Choose", labels, key=f"prac-{q['id']}")
            submit_practice = st.form_submit_button("Submit practice")

        if submit_practice:
            responses = {}
            for q in questions:
                sel = st.session_state.get(f"prac-{q['id']}")
                if isinstance(sel, str) and len(sel) == 1 and sel.isalpha():
                    idx = ord(sel.upper()) - 65
                else:
                    idx = 0
                responses[q["id"]] = max(0, min(idx, len(q.get("choices", [])) - 1))

            result = mcq_manager.evaluate_responses(responses)
            st.session_state.maths_practice_result = result
            try:
                del st.session_state["maths_practice_questions"]
            except Exception:
                pass
            analytics_module.log_interaction(profile.get("student_name") or "maths-student", "practice", str(result))

    if st.session_state.get("maths_practice_result"):
        pres = st.session_state.get("maths_practice_result")
        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        st.subheader("Practice results")
        st.metric("Score", f"{pres.get('correct',0)}/{pres.get('total',0)}")
        if pres.get("coach_notes"):
            st.info(pres.get("coach_notes"))
        if pres.get("recommendations"):
            st.markdown("**Follow-up recommendations**")
            for rec in pres.get("recommendations", []):
                domain_label = rec.get('domain') or rec.get('domain_id')
                st.markdown(f"- {domain_label}: {rec['wrong']} incorrect out of {rec['total']}")
        # Offer a retry of incorrect ones with variants
        if pres.get("details"):
            if st.button("Retry incorrect ones (variants)"):
                # generate variants (1 per wrong question) and open preview for review
                variants = mcq_manager.generate_retry_questions(pres, variants_per_question=1)
                if not variants:
                    st.info("No retry variants could be generated for the incorrect questions.")
                else:
                    st.session_state.maths_variant_preview = variants
                    st.session_state.maths_show_preview = True
                    st.experimental_rerun()
    starters = basic_maths.quick_starters(profile)
    starter_cols = st.columns(len(starters))
    for idx, starter in enumerate(starters):
        if starter_cols[idx].button(starter):
            st.session_state.maths_prompt = starter

    prompt = st.text_area("Write a maths question", value=st.session_state.maths_prompt, height=130, placeholder="Ask about fractions, algebra, speed, or exam strategy.")
    response_style = st.radio("Response style", ["Text", "Study card", "Bullet steps"], horizontal=True)
    if st.button("Generate coach reply"):
        if not prompt.strip():
            st.warning("Type a question first.")
        else:
            reply = basic_maths.generate_math_reply(prompt, profile, ai_client=ai_client)
            st.session_state.maths_chat.append({"role": "user", "content": prompt})
            st.session_state.maths_chat.append({"role": "assistant", "content": reply})
            analytics_module.log_interaction(profile.get("student_name") or "maths-student", "user", prompt)
            analytics_module.log_interaction(profile.get("student_name") or "maths-student", "assistant", reply)
            st.session_state.maths_prompt = prompt
            st.session_state.maths_quiz_result = reply

    if st.session_state.maths_quiz_result:
        reply = st.session_state.maths_quiz_result
        if response_style == "Bullet steps":
            bullets = [line.strip("-• ") for line in reply.split(".") if line.strip()]
            st.markdown("\n".join([f"- {bullet}" for bullet in bullets[:5]]))
        elif response_style == "Study card":
            st.markdown(f"<div class='bm-card'><h4>Coach reply</h4><p>{reply}</p></div>", unsafe_allow_html=True)
        else:
            st.write(reply)

    if st.session_state.maths_chat:
        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        st.subheader("Conversation")
        for message in st.session_state.maths_chat[-6:]:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
    st.subheader("Sit a quiz")
    # Present canonical taxonomy topics for practice
    topics = []
    topic_meta = []
    for lk in mcq_manager.LEVELS:
        for t in mcq_manager.get_canonical_topics(lk):
            disp = f"{t['top']} / {t['sub']} ({t['count']}) [{lk}]"
            topics.append(disp)
            topic_meta.append((lk, t['top'], t['sub']))
    if not topics:
        st.info("No canonical practice topics available. Generate KB first.")
        quiz_topic = None
    else:
        # if a practice preference was set (from diagnostic recommendations), preselect it
        default_idx = 0
        pref = st.session_state.get("maths_practice_pref")
        if pref:
            try:
                for idx, meta in enumerate(topic_meta):
                    lk_meta, top_meta, sub_meta = meta
                    if "::" in str(pref):
                        top_pref, sub_pref = str(pref).split("::", 1)
                        if top_pref == top_meta and sub_pref == sub_meta:
                            default_idx = idx
                            break
            except Exception:
                default_idx = 0

        sel_idx = st.selectbox("Choose a topic", topics, index=default_idx if topics else None)
        quiz_topic = topic_meta[topics.index(sel_idx)] if sel_idx else None
        # clear the preference after it's been used
        if st.session_state.get("maths_practice_pref"):
            try:
                del st.session_state["maths_practice_pref"]
            except KeyError:
                pass

    if st.button("Generate a quick check-in quiz"):
        if not quiz_topic:
            st.warning("Select a topic first or generate the KB.")
        else:
            lvl, top, sub = quiz_topic
            questions = mcq_manager.get_practice_by_canonical(lvl, top, sub, top_n=3)
            if not questions:
                st.info("No practice questions found for this topic.")
            else:
                st.session_state.maths_quiz_result = "\n".join([f"- {q.get('question')}" for q in questions])

    st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
    st.subheader("30-question diagnostic")
    level_map = mcq_manager.LEVELS
    level_choice = st.selectbox("Choose a level", list(level_map.keys()), format_func=lambda k: level_map.get(k, k))
    # Allow scope selection: entire level or a canonical topic
    scope = st.radio("Diagnostic scope", ["Level-wide", "Canonical topic"], horizontal=True)

    canonical_choice = None
    if scope == "Canonical topic":
        c_topics = mcq_manager.get_canonical_topics(level_choice)
        if not c_topics:
            st.info("No canonical topics available for this level.")
        else:
            choices = [f"{t['top']} / {t['sub']} ({t['count']})" for t in c_topics]
            sel = st.selectbox("Choose canonical topic", choices)
            idx = choices.index(sel)
            canonical_choice = (c_topics[idx]['top'], c_topics[idx]['sub'])

    if st.button("Start 30-question diagnostic"):
        # Use heuristic-only MCQs (no AI expansion)
        num_q = 30
        questions = []
        if scope == "Level-wide" or not canonical_choice:
            questions = mcq_manager.sample_diagnostic(level_choice, num_questions=num_q, ai_client=ai_client, allow_ai=False)
        else:
            top, sub = canonical_choice
            canonical_qs = mcq_manager.get_practice_by_canonical(level_choice, top, sub, top_n=num_q)
            # If canonical has fewer than requested, pad from level-wide (excluding duplicates)
            if len(canonical_qs) >= num_q:
                questions = canonical_qs[:num_q]
            else:
                needed = num_q - len(canonical_qs)
                level_wide = mcq_manager.sample_diagnostic(level_choice, num_questions=num_q, ai_client=ai_client, allow_ai=False)
                # filter out canonical ids
                existing_ids = {q['id'] for q in canonical_qs}
                filler = [q for q in level_wide if q['id'] not in existing_ids]
                questions = canonical_qs + filler[:needed]

        if not questions:
            st.warning("No diagnostic questions available for this level/topic. Generate the KB first.")
        else:
            st.session_state.maths_diagnostic_questions = questions
            # clear any previous responses in session
            for q in questions:
                key = f"diag-{q['id']}"
                if key in st.session_state:
                    del st.session_state[key]

    if st.session_state.get("maths_diagnostic_questions"):
        questions = st.session_state.maths_diagnostic_questions
        with st.form("diagnostic_form"):
            st.markdown(f"<div class='bm-eyebrow'>Diagnostic: {len(questions)} questions</div>", unsafe_allow_html=True)
            for q in questions:
                _render_math_text(q.get("question", ""))
                choices = q.get("choices", []) or []
                labels = [chr(65 + i) for i in range(len(choices))]
                for idx_c, choice in enumerate(choices):
                    st.markdown(f"**{labels[idx_c]}.** ")
                    _render_math_text(choice)
                st.radio("Choose", labels, key=f"diag-{q['id']}")
            submit_diag = st.form_submit_button("Submit diagnostic")

        if submit_diag:
            responses = {}
            for q in questions:
                sel = st.session_state.get(f"diag-{q['id']}")
                if isinstance(sel, str) and len(sel) == 1 and sel.isalpha():
                    idx = ord(sel.upper()) - 65
                else:
                    idx = 0
                responses[q["id"]] = max(0, min(idx, len(q.get("choices", [])) - 1))

            result = mcq_manager.evaluate_responses(responses)
            st.session_state.maths_quiz_result = result
            # clear questions after submission
            del st.session_state.maths_diagnostic_questions
            analytics_module.log_interaction(profile.get("student_name") or "maths-student", "diagnostic", str(result))

    # Show diagnostic results if present
    if isinstance(st.session_state.maths_quiz_result, dict):
        res = st.session_state.maths_quiz_result
        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        st.subheader("Diagnostic results")
        st.metric("Score", f"{res.get('correct',0)}/{res.get('total',0)}")
        coach = res.get("coach_notes") or res.get("feedback")
        if coach:
            st.info(coach)

        recs = res.get("recommendations", []) or []
        if recs:
            st.markdown("**Recommended focus areas**")
            cols = st.columns(2)
            for i, rec in enumerate(recs):
                with cols[i % 2]:
                    domain_label = rec.get('domain') or rec.get('domain_id')
                    actions_html = "".join([f"<li>{a}</li>" for a in rec.get('actions', [])])
                    st.markdown(
                        f"<div class='bm-card'><h4>{domain_label}</h4>"
                        f"<p><strong>Incorrect:</strong> {rec.get('wrong',0)}/{rec.get('total',0)}</p>"
                        f"<p><strong>Suggested practice:</strong> {rec.get('suggested_practice',0)} Qs · ~{rec.get('suggested_minutes',0)} mins</p>"
                        f"<div class='bm-divider'></div>"
                        f"<p><strong>Actions:</strong></p><ul>{actions_html}</ul>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    practice = mcq_manager.get_domain_practice(rec.get('domain_id'), top_n=5)
                    if practice:
                        st.caption(f"Practice set available: {len(practice)} questions — open Practice Lab to attempt them.")

                    # quick action: open Practice Lab focused on this domain
                    btn_key = f"pract-{i}"
                    if st.button("Practice this domain", key=btn_key):
                        st.session_state.maths_practice_pref = rec.get('domain_id')
                        st.session_state.maths_nav = "Practice Lab"
                        st.experimental_rerun()

                    # immediate attempt: generate a short practice set and open it
                    attempt_key = f"attempt-{i}"
                    if st.button("Attempt practice now", key=attempt_key):
                        domain_id = rec.get('domain_id')
                        top_n = rec.get('suggested_practice', 5) or 5
                        try:
                            questions = mcq_manager.get_domain_practice(domain_id, top_n=top_n)
                        except Exception:
                            questions = []
                        if not questions:
                            st.warning("No practice questions available for this domain.")
                        else:
                            # set modal questions and request modal display
                            st.session_state.maths_modal_questions = questions
                            st.session_state.maths_show_modal = True
                            st.experimental_rerun()


def _render_appointments(profile):
    st.markdown("<div class='bm-eyebrow'>Appointment desk</div>", unsafe_allow_html=True)
    st.subheader("Automated coaching schedule")
    slots = appointments.suggest_appointment_slots(profile.get("exam_date") or (date.today() + timedelta(days=1)))
    if slots:
        slot_cards = st.columns(3)
        for idx, slot in enumerate(slots[:3]):
            with slot_cards[idx]:
                st.markdown(
                    f"""
                    <div class='bm-card'>
                      <h4>Slot {idx + 1}</h4>
                      <p><strong>{slot['date']}</strong></p>
                      <p>{slot['time']}</p>
                      <p>Auto-selected based on your goals.</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No appointment slots are available right now. Please try a different date.")

    st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
    st.subheader("Request a coaching session")
    with st.form("auto_booking_form"):
        student_name = st.text_input("Student name", value=profile.get("student_name") or "")
        email = st.text_input("Email", value=profile.get("email") or "")
        topic = st.selectbox("Session focus", [item["title"] for item in basic_maths.MATH_TOPICS])
        preferred_date = st.date_input("Preferred date", value=profile.get("exam_date") or (date.today() + timedelta(days=1)), min_value=date.today())
        notes = st.text_area("Notes", placeholder="Anything the coach should know?", height=90)
        booked = st.form_submit_button("Auto-schedule next slot")

    if booked:
        booking = appointments.auto_schedule_appointment(
            student_name=student_name,
            email=email,
            topic=topic,
            profile=profile,
            preferred_date=preferred_date,
            notes=notes,
        )
        st.session_state.maths_booking = booking
        analytics_module.log_interaction(student_name or "maths-student", "user", f"Booked appointment for {topic} on {booking['when']}")
        st.success(f"Appointment booked for {booking['when']} with {booking['advisor']}")
        st.caption(booking.get("notes", ""))

    if st.session_state.maths_booking:
        booking = st.session_state.maths_booking
        st.markdown(
            f"""
            <div class='bm-card'>
              <h4>Latest booked session</h4>
              <p><strong>{booking['student_name']}</strong></p>
              <p>{booking['scheduled_for']['date']} · {booking['scheduled_for']['time']}</p>
              <p>{booking.get('notes', '')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    upcoming = appointments.list_upcoming_appointments(limit=5)
    if upcoming:
        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        st.subheader("Upcoming sessions")
        for item in upcoming:
            st.markdown(
                f"""
                <div class='bm-card'>
                  <h4>{item.get('student_name', 'Student')}</h4>
                  <p>{item.get('when', '')} · {item.get('advisor', '')}</p>
                  <p>{item.get('notes', '')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_analytics(profile):
    st.markdown("<div class='bm-eyebrow'>Reading desk</div>", unsafe_allow_html=True)
    st.subheader("Study activity")

    try:
        df = analytics_module.load_interactions()
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        st.info("No practice logs yet. Ask a question or book a session to populate the analytics desk.")
        return

    trends = analytics_module.prepare_interaction_trends(df)
    if not trends.empty:
        chart_cols = st.columns(2)
        with chart_cols[0]:
            st.plotly_chart(px.bar(trends, x="date", y="interactions", title="Interactions per day"), use_container_width=True)
        with chart_cols[1]:
            st.plotly_chart(px.line(trends, x="date", y="avg_compound", markers=True, title="Average sentiment"), use_container_width=True)

    stats = analytics_module.simple_stats(df)
    metrics = st.columns(3)
    metrics[0].metric("Total logs", stats.get("total", 0))
    metrics[1].metric("Positive logs", stats.get("by_sentiment", {}).get("positive", 0))
    metrics[2].metric("Top user", next(iter(stats.get("top_users", {}) or {"None": 0})))

    st.caption("Recent activity")
    st.dataframe(df.tail(10), use_container_width=True)


def main():
    _init_state()
    ai_client, provider = _build_ai_client()
    profile = st.session_state.maths_profile_saved
    summary = basic_maths.build_learning_summary(profile)
    stats = basic_maths.build_dashboard_metrics(profile, practice_attempts=len(st.session_state.maths_chat))

    with st.sidebar:
        st.markdown("<div class='bm-eyebrow'>Basic Maths Prep</div>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0'>Personalised maths prep desk</h3>", unsafe_allow_html=True)
        st.caption("A calm, student-friendly workspace for diagnostics, revision planning, and coaching.")
        st.progress(min(max(stats["progress"], 0), 100) / 100)
        st.caption(f"Learning progress: {stats['progress']}%")

        nav = st.radio(
            "Go to",
            ["Dashboard", "Learning Path", "Academic Plan", "Practice Lab", "Appointments", "Analytics"],
            index=["Dashboard", "Learning Path", "Academic Plan", "Practice Lab", "Appointments", "Analytics"].index(st.session_state.maths_nav)
            if st.session_state.maths_nav in ["Dashboard", "Learning Path", "Academic Plan", "Practice Lab", "Appointments", "Analytics"]
            else 0,
        )
        st.session_state.maths_nav = nav

        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        st.markdown("<div class='bm-eyebrow'>Assistant mode</div>", unsafe_allow_html=True)
        st.caption(f"Using {provider}")
        _render_profile_form()

    st.markdown("<div class='bm-eyebrow'>Archive Tutor inspired · Basic Maths Prep</div>", unsafe_allow_html=True)

    # Variant preview modal: allow review before attempting
    if st.session_state.get("maths_show_preview") and st.session_state.get("maths_variant_preview"):
        with st.modal("Review variant questions"):
            pv = st.session_state.get("maths_variant_preview") or []
            st.markdown(f"<div class='bm-eyebrow'>Preview {len(pv)} variant questions</div>", unsafe_allow_html=True)
            for idx, q in enumerate(pv):
                st.markdown(f"**Q{idx+1}.** {q.get('question')}  ")
                for cidx, c in enumerate(q.get('choices', [])):
                    st.markdown(f"- {c}")
            approve = st.button("Approve & Attempt")
            discard = st.button("Discard variants")
            if approve:
                st.session_state.maths_modal_questions = pv
                st.session_state.maths_show_modal = True
                try:
                    del st.session_state["maths_variant_preview"]
                except Exception:
                    pass
                st.session_state.maths_show_preview = False
                st.experimental_rerun()
            if discard:
                try:
                    del st.session_state["maths_variant_preview"]
                except Exception:
                    pass
                st.session_state.maths_show_preview = False
                st.experimental_rerun()

    # If a quick-practice modal was requested, show it here (keeps user on same page)
    if st.session_state.get("maths_show_modal") and st.session_state.get("maths_modal_questions"):
        with st.modal("Quick practice"):
            mq = st.session_state.get("maths_modal_questions") or []
            with st.form("modal_practice_form"):
                st.markdown(f"<div class='bm-eyebrow'>Quick practice: {len(mq)} questions</div>", unsafe_allow_html=True)
                for q in mq:
                    _render_math_text(q.get("question", ""))
                    choices = q.get("choices", []) or []
                    labels = [chr(65 + i) for i in range(len(choices))]
                    for idx_c, choice in enumerate(choices):
                        st.markdown(f"**{labels[idx_c]}.** ")
                        _render_math_text(choice)
                    st.radio("Choose", labels, key=f"modal-prac-{q['id']}")
                submit_modal = st.form_submit_button("Submit practice")

            if submit_modal:
                responses = {}
                for q in mq:
                    sel = st.session_state.get(f"modal-prac-{q['id']}")
                    if isinstance(sel, str) and len(sel) == 1 and sel.isalpha():
                        idx = ord(sel.upper()) - 65
                    else:
                        idx = 0
                    responses[q["id"]] = max(0, min(idx, len(q.get("choices", [])) - 1))

                result = mcq_manager.evaluate_responses(responses)
                st.session_state.maths_practice_result = result
                # clear modal flags
                try:
                    del st.session_state["maths_modal_questions"]
                except Exception:
                    pass
                st.session_state.maths_show_modal = False
                analytics_module.log_interaction(profile.get("student_name") or "maths-student", "practice", str(result))

    if nav == "Dashboard":
        _render_hero(profile, summary, stats)
        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        action_cols = st.columns(3)
        with action_cols[0]:
            st.markdown(
                "<div class='bm-card'><h4>Recommendations</h4><p>Review the top topics the system suggests for your stage and goal.</p></div>",
                unsafe_allow_html=True,
            )
        with action_cols[1]:
            st.markdown(
                "<div class='bm-card'><h4>Academic planning</h4><p>Follow a weekly plan based on your current profile and progress.</p></div>",
                unsafe_allow_html=True,
            )
        with action_cols[2]:
            st.markdown(
                "<div class='bm-card'><h4>Schedule support</h4><p>Book a coaching slot automatically from available times.</p></div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        st.subheader("Ask the tutor")
        _render_topic_cards(profile)
        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        st.subheader("Plan the week")
        _render_week_plan(profile)

    elif nav == "Learning Path":
        st.markdown("<div class='bm-eyebrow'>Study folio</div>", unsafe_allow_html=True)
        st.subheader("Targeted recommendations")
        rec_cols = st.columns(2)
        for idx, item in enumerate(summary["recommendations"]):
            with rec_cols[idx % 2]:
                st.markdown(
                    f"""
                    <div class='bm-card'>
                      <h4>{item['title']}</h4>
                      <p>{item['why']}</p>
                      <div class='bm-divider'></div>
                      <p><strong>Practice:</strong> {item['practice']}</p>
                      <p><strong>Common mistake:</strong> {item['common_mistake']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        st.subheader("Academic planning suggestions")
        plan = basic_maths.build_week_plan(profile)
        cols = st.columns(5)
        for idx, item in enumerate(plan):
            with cols[idx % 5]:
                st.markdown(
                    f"""
                    <div class='bm-card'>
                      <h4>{item['day']}</h4>
                      <p><strong>{item['title']}</strong></p>
                      <p>{item['description']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        st.subheader("Study rhythm")
        _render_revision_timeline(profile)

    elif nav == "Academic Plan":
        st.markdown("<div class='bm-eyebrow'>Reading desk</div>", unsafe_allow_html=True)
        st.subheader("Academic planning suggestions")
        _render_week_plan(profile)
        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        _render_revision_timeline(profile)

    elif nav == "Practice Lab":
        _render_practice_lab(profile, ai_client, provider)

    elif nav == "Appointments":
        _render_appointments(profile)

    elif nav == "Analytics":
        _render_analytics(profile)


if __name__ == "__main__":
    main()
