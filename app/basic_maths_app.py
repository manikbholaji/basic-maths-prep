from __future__ import annotations

import os
import sys
import hashlib
import json
from copy import deepcopy
from datetime import date, timedelta, datetime
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

USERS_FILE = PROJECT_ROOT / "data" / "users.json"
PROGRESS_FILE = PROJECT_ROOT / "data" / "user_progress.json"


def _ensure_data_files():
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text("{}", encoding="utf-8")
    if not PROGRESS_FILE.exists():
        PROGRESS_FILE.write_text("{}", encoding="utf-8")


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, payload: dict):
    # Write atomically: write to a temp file then replace the target
    try:
        tmp = path.parent / (path.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        # fallback to direct write
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _account_sign_up(name: str, email: str, password: str) -> tuple[bool, str]:
    _ensure_data_files()
    email_norm = (email or "").strip().lower()
    if not name.strip() or not email_norm or "@" not in email_norm or len(password or "") < 6:
        return False, "Enter a valid name, email, and password (min 6 characters)."
    users = _load_json(USERS_FILE)
    if email_norm in users:
        return False, "Account already exists. Please sign in."
    users[email_norm] = {
        "name": name.strip(),
        "email": email_norm,
        "password_hash": _hash_password(password),
    }
    _save_json(USERS_FILE, users)
    return True, "Account created successfully."


def _account_sign_in(email: str, password: str) -> tuple[bool, dict | None, str]:
    _ensure_data_files()
    email_norm = (email or "").strip().lower()
    users = _load_json(USERS_FILE)
    user = users.get(email_norm)
    if not user:
        return False, None, "No account found for this email."
    if user.get("password_hash") != _hash_password(password or ""):
        return False, None, "Incorrect password."
    return True, user, "Signed in successfully."


def _save_user_progress(email: str, patch: dict):
    _ensure_data_files()
    email_norm = (email or "").strip().lower()
    if not email_norm:
        return
    progress = _load_json(PROGRESS_FILE)
    current = progress.get(email_norm, {})
    current.update(patch)
    progress[email_norm] = current
    _save_json(PROGRESS_FILE, progress)


def _load_user_progress(email: str) -> dict:
    _ensure_data_files()
    email_norm = (email or "").strip().lower()
    progress = _load_json(PROGRESS_FILE)
    return progress.get(email_norm, {})


def _choice_to_index(sel: str, n_choices: int) -> int:
    if isinstance(sel, str) and len(sel) == 1 and sel.isalpha():
        idx = ord(sel.upper()) - 65
    else:
        idx = 0
    return max(0, min(idx, max(n_choices - 1, 0)))


def _recommend_next_index(questions: list[dict], answers: dict, current_idx: int) -> int | None:
    if not questions:
        return None

    def status_for(i: int) -> str:
        q = questions[i]
        sel = answers.get(q.get("id"))
        if not sel:
            return "unseen"
        selected_idx = _choice_to_index(sel, len(q.get("choices", []) or []))
        correct_idx = int(q.get("answer", 0))
        return "correct" if selected_idx == correct_idx else "incorrect"

    current_status = status_for(current_idx)

    order = list(range(current_idx + 1, len(questions))) + list(range(0, current_idx))
    if current_status == "incorrect":
        priorities = ["unseen", "incorrect"]
    else:
        priorities = ["unseen", "incorrect"]

    for p in priorities:
        for i in order:
            if status_for(i) == p:
                return i
    return None


def _render_question_player(questions: list[dict], prefix: str, title: str, submit_label: str) -> tuple[bool, dict]:
    if not questions:
        return False, {}

    idx_key = f"{prefix}_index"
    ans_key = f"{prefix}_answers"
    flag_key = f"{prefix}_flags"
    if idx_key not in st.session_state:
        st.session_state[idx_key] = 0
    if ans_key not in st.session_state:
        st.session_state[ans_key] = {}
    if flag_key not in st.session_state:
        st.session_state[flag_key] = {}

    total = len(questions)
    current_idx = max(0, min(int(st.session_state[idx_key]), total - 1))
    st.session_state[idx_key] = current_idx

    # Commit any pending autosave if debounce passed
    pending = st.session_state.get("bm_pending_save") or {}
    try:
        if pending:
            when = pending.get("when")
            if when and (datetime.now() - when).total_seconds() >= 2:
                # perform save
                user_p = pending.get("user")
                data_p = pending.get("checkpoint")
                if user_p and user_p.get("email") and data_p:
                    _save_user_progress(user_p.get("email"), {"practice_session": data_p})
                    st.session_state["bm_last_auto_save"] = datetime.now().strftime("%H:%M:%S")
                    msg = f"Auto-saved (Q{int(data_p.get('index',0))+1}) at {st.session_state.get('bm_last_auto_save')}"
                    st.session_state["bm_auto_save_msg"] = msg
                    try:
                        st.markdown(f"<div id='bm-live' aria-live='polite' aria-atomic='true' style='position:absolute;left:-10000px'>{msg}</div>", unsafe_allow_html=True)
                    except Exception:
                        pass
                    # focus hint for client helper
                    try:
                        st.markdown(f"<div id='bm-focus-label' style='position:absolute;left:-10000px'>{'Q'+str(int(data_p.get('index',0))+1)}</div>", unsafe_allow_html=True)
                    except Exception:
                        pass
                st.session_state["bm_pending_save"] = {}
    except Exception:
        st.session_state["bm_pending_save"] = {}

    st.markdown(f"<div class='bm-eyebrow'>{title}: {total} questions</div>", unsafe_allow_html=True)
    nav_cols = st.columns([1.6, 1, 1])
    with nav_cols[0]:
        jump = st.selectbox("Jump to question", list(range(1, total + 1)), index=current_idx, key=f"{prefix}_jump")
        if jump - 1 != current_idx:
            current_idx = jump - 1
            st.session_state[idx_key] = current_idx
    with nav_cols[1]:
        if st.button("Previous", key=f"{prefix}_prev"):
            current_idx = max(0, current_idx - 1)
            st.session_state[idx_key] = current_idx
            _safe_rerun()
    with nav_cols[2]:
        if st.button("Next", key=f"{prefix}_next"):
            current_idx = min(total - 1, current_idx + 1)
            st.session_state[idx_key] = current_idx
            _safe_rerun()

    pct = int(round(((current_idx + 1) / total) * 100))
    st.markdown(f"<div class='bm-mini-progress-rail'><div class='bm-mini-progress-fill' style='width:{pct}%;'></div></div>", unsafe_allow_html=True)
    st.caption(f"Question {current_idx + 1} of {total}")

    q = questions[current_idx]
    flags = st.session_state.get(flag_key) or {}
    # Accessibility: hidden label for the question and ARIA group wrapper
    qid = q.get('id')
    try:
        st.markdown(f"<div id='qlabel-{qid}' style='position:absolute;left:-10000px;top:auto;width:1px;height:1px;overflow:hidden;'>{q.get('question','')[:160]}</div>", unsafe_allow_html=True)
    except Exception:
        pass
    top_actions = st.columns([1.2, 1, 1])
    with top_actions[0]:
        user = st.session_state.get("maths_auth_user")
        if user and user.get("email"):
            if st.button("Save progress", key=f"{prefix}_save_progress"):
                checkpoint = {"questions": questions, "answers": st.session_state.get(ans_key) or {}, "index": int(st.session_state.get(idx_key, 0))}
                _save_user_progress(user.get("email"), {"practice_session": checkpoint})
                st.markdown(f"<span class='bm-progress-saved'>Progress saved (Q{checkpoint['index']+1})</span>", unsafe_allow_html=True)
    with top_actions[1]:
        st.caption("Status legend: ○ unseen · ● answered · ⚑ flagged")
    with top_actions[2]:
        current_flag = bool(flags.get(q.get("id"), False))
        flag_label = "Unflag question" if current_flag else "Flag question"
        if st.button(flag_label, key=f"{prefix}_flag_btn"):
            flags[q.get("id")] = not current_flag
            st.session_state[flag_key] = flags
            _safe_rerun()

    _render_math_text(q.get("question", ""))
    choices = q.get("choices", []) or []
    labels = [chr(65 + i) for i in range(len(choices))]

    # Render the radio selector above the choices so selection maps clearly to each item
    saved = (st.session_state.get(ans_key) or {}).get(q.get("id"))
    default_idx = labels.index(saved) if saved in labels else 0
    selected = st.radio("Choose", labels, index=default_idx, key=f"{prefix}_choice_{q.get('id')}") if labels else None

    # Render choices inside a semantic radio group for accessibility
    st.markdown(f"<div role='radiogroup' aria-label='Question choices' class='bm-choices-group'>", unsafe_allow_html=True)
    # Render each choice in its own container so Streamlit preserves structure.
    for idx_c, choice in enumerate(choices):
        is_sel = (selected == labels[idx_c])
        qid = q.get('id')
        with st.container():
            cls = "bm-choice bm-selected" if is_sel else "bm-choice"
            # compute an accessible name for the radio from the label and plain text of the choice
            try:
                import re as _re
                _plain = _re.sub(r'<[^>]*>', '', str(choice)).strip()
                _plain = _plain.replace('"', '&quot;')
            except Exception:
                _plain = str(choice)
            aria_checked = 'true' if is_sel else 'false'
            aria_label = f"Choice {labels[idx_c]}: {_plain[:140]}"
            st.markdown(f"<div class=\"{cls}\" role='radio' aria-checked='{aria_checked}' aria-label=\"{aria_label}\" tabindex='0'>", unsafe_allow_html=True)
            # Show label and content side-by-side using a simple table for alignment
            try:
                cols = st.columns([0.12, 1, 0.26])
                with cols[0]:
                    st.markdown(f"<div style='font-weight:700;color:var(--accent);'>{labels[idx_c]}</div>", unsafe_allow_html=True)
                with cols[1]:
                    _render_math_text(choice)
                with cols[2]:
                    pick_key = f"{prefix}_pick_{qid}_{idx_c}"
                    if st.button("Select", key=pick_key):
                        # set the radio selection and mirror into answers map
                        st.session_state[f"{prefix}_choice_{qid}"] = labels[idx_c]
                        ans_map = st.session_state.get(ans_key) or {}
                        ans_map[qid] = labels[idx_c]
                        st.session_state[ans_key] = ans_map
                        user = st.session_state.get("maths_auth_user")
                        try:
                            if user and user.get("email"):
                                checkpoint = {"questions": questions, "answers": st.session_state.get(ans_key) or {}, "index": int(st.session_state.get(idx_key, 0))}
                                _save_user_progress(user.get("email"), {"practice_session": checkpoint})
                                ts = datetime.now().strftime("%H:%M:%S")
                                st.session_state["bm_last_auto_save"] = ts
                                msg = f"Auto-saved (Q{int(st.session_state.get(idx_key,0))+1}) at {ts}"
                                st.session_state["bm_auto_save_msg"] = msg
                                st.session_state["bm_auto_save_msg_ts"] = datetime.now()
                                try:
                                    st.markdown(f"<div id='bm-live' aria-live='polite' aria-atomic='true' style='position:absolute;left:-10000px'>{msg}</div>", unsafe_allow_html=True)
                                except Exception:
                                    pass
                                try:
                                    # set a focus hint
                                    st.markdown(f"<div id='bm-focus-label' style='position:absolute;left:-10000px'>{labels[idx_c]}</div>", unsafe_allow_html=True)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        _safe_rerun()
            except Exception:
                # fallback: simple rendering
                _render_math_text(choice)
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    # (Removed keyboard text-input fallback; global key capture is provided by the injected JS helper)

    # Insert a small client-side helper component that listens for global keypresses
    # and forwards clicks on `.bm-choice` to the corresponding Select button.
    try:
        import streamlit.components.v1 as components

        helper_js = r"""
        <script>
        (function(){
            try{
                const parentDoc = window.parent.document;

                function clickSelectByChoiceIndex(idx){
                    // find all Select buttons currently visible (they correspond to choices)
                    const btns = Array.from(parentDoc.querySelectorAll('button')).filter(b => b.textContent && b.textContent.trim()==='Select');
                    if(btns && btns[idx]){
                        btns[idx].click();
                    }
                }

                // global key handler (A-D)
                parentDoc.addEventListener('keydown', function(e){
                    const tag = (e.target && e.target.tagName) || '';
                    if(tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
                    const k = (e.key || '').toUpperCase();
                    if(k >= 'A' && k <= 'D'){
                        const idx = k.charCodeAt(0) - 65;
                        clickSelectByChoiceIndex(idx);
                        // update aria labels/checked after keyboard selection
                        setTimeout(updateAria, 40);
                    }
                }, true);

                // make entire .bm-choice clickable: forward click to matching Select button
                parentDoc.addEventListener('click', function(e){
                    const el = e.target.closest && e.target.closest('.bm-choice');
                    if(!el) return;
                    // determine index of this .bm-choice among all choices in the current question
                    const all = Array.from(parentDoc.querySelectorAll('.bm-choice'));
                    const idx = all.indexOf(el);
                    if(idx >= 0){
                        // click the corresponding Select button
                        clickSelectByChoiceIndex(idx);
                        setTimeout(updateAria, 40);
                    }
                }, true);
                // map Select buttons to accessible labels and reflect checked state
                function updateAria(){
                    try{
                        const all = Array.from(parentDoc.querySelectorAll('.bm-choice'));
                        const btns = Array.from(parentDoc.querySelectorAll('button')).filter(b => b.textContent && b.textContent.trim()==='Select');
                        all.forEach((el, i) => {
                            el.setAttribute('role','radio');
                            if(el.classList.contains('bm-selected')) el.setAttribute('aria-checked','true'); else el.setAttribute('aria-checked','false');
                            const lbl = (el.querySelector('div') && el.querySelector('div').textContent) ? el.querySelector('div').textContent.trim() : String.fromCharCode(65+i);
                            if(btns[i]) btns[i].setAttribute('aria-label', `Select choice ${lbl}`);
                        });
                    }catch(e){/*ignore*/}
                }
                // initial call
                setTimeout(updateAria, 100);
                // accessibility fixes: remove invalid aria attributes, set role=main, and normalize heading levels
                try{
                    // remove aria-expanded on elements that shouldn't have it (e.g., Streamlit sidebar)
                    Array.from(parentDoc.querySelectorAll('[aria-expanded]')).forEach(el=>{
                        el.removeAttribute('aria-expanded');
                    });
                    // watch for nodes that add aria-expanded later and remove it
                    const obs = new MutationObserver(function(muts){
                        muts.forEach(m=>{
                            if(m.type === 'attributes' && m.attributeName === 'aria-expanded'){
                                try{ m.target.removeAttribute('aria-expanded'); }catch(e){}
                            }
                            if(m.addedNodes && m.addedNodes.length){
                                m.addedNodes.forEach(node=>{
                                    try{ if(node.querySelectorAll){ Array.from(node.querySelectorAll('[aria-expanded]')).forEach(el=>el.removeAttribute('aria-expanded')); } }catch(e){}
                                });
                            }
                        });
                    });
                    try{ obs.observe(parentDoc.body, { attributes:true, subtree:true, childList:true }); }catch(e){}
                    // also periodically remove aria-expanded for a short window (workaround for re-renders)
                    try{
                        let rid = setInterval(()=>{
                            Array.from(parentDoc.querySelectorAll('[aria-expanded]')).forEach(el=>el.removeAttribute('aria-expanded'));
                        }, 200);
                        setTimeout(()=>{ clearInterval(rid); }, 5000);
                    }catch(e){}
                }catch(e){}
                try{
                    const app = parentDoc.querySelector('.stApp');
                    if(app) app.setAttribute('role','main');
                }catch(e){}
                try{
                    // replace existing and newly added h4 tags with h3 to improve heading order
                    function replaceH4(node){
                        const h4s = Array.from((node||parentDoc).getElementsByTagName('h4'));
                        h4s.forEach(h4=>{
                            const h3 = parentDoc.createElement('h3');
                            h3.innerHTML = h4.innerHTML;
                            for(const attr of h4.attributes) h3.setAttribute(attr.name, attr.value);
                            h4.parentNode.replaceChild(h3, h4);
                        });
                    }
                    replaceH4();
                    const hObs = new MutationObserver((muts)=>{ muts.forEach(m=>{ if(m.addedNodes) replaceH4(m.addedNodes[0]); }); });
                    try{ hObs.observe(parentDoc.body, { childList:true, subtree:true }); }catch(e){}
                }catch(e){}
                // focus helper: if server emitted a bm-focus-label element, focus matching Select button
                function focusFromLabel(){
                    try{
                        const hint = parentDoc.getElementById('bm-focus-label');
                        if(!hint) return;
                        const label = hint.textContent && hint.textContent.trim();
                        if(!label) return;
                        const btns = Array.from(parentDoc.querySelectorAll('button')).filter(b => b.textContent && b.textContent.trim()==='Select');
                        // find button whose aria-label contains the label text or whose previous sibling label matches
                        for(const b of btns){
                            const al = (b.getAttribute('aria-label')||'').toString();
                            if(al.includes(label) || b.closest('.bm-choice') && b.closest('.bm-choice').textContent.includes(label)){
                                b.focus();
                                break;
                            }
                        }
                        // remove hint to avoid repeat
                        hint.remove();
                        // remove tabindex from KaTeX display blocks to avoid scrollable-region-focusable issues
                        try{ Array.from(parentDoc.querySelectorAll('.katex-display')).forEach(el=>{ try{ el.removeAttribute('tabindex'); }catch(e){} }); }catch(e){}
                        // ensure combobox inputs have aria-expanded to satisfy required ARIA attributes
                        try{ Array.from(parentDoc.querySelectorAll('input[role="combobox"]')).forEach(inp=>{ try{ if(!inp.hasAttribute('aria-expanded')) inp.setAttribute('aria-expanded','false'); }catch(e){} }); }catch(e){}
                    }catch(e){/*ignore*/}
                }
                setTimeout(focusFromLabel, 120);
            }catch(err){
                // silently fail
                console.error('bm-helper error', err);
            }
        })();
        </script>
        """

        components.html(helper_js, height=0)
    except Exception:
        pass
    answers = st.session_state.get(ans_key) or {}
    # Detect change and persist automatically for signed-in users
    prev_sel = saved
    answers[q.get("id")] = selected
    st.session_state[ans_key] = answers
    user = st.session_state.get("maths_auth_user")
    try:
        if user and user.get("email") and selected is not None and selected != prev_sel:
            # save a lightweight checkpoint for resume immediately
            checkpoint = {"questions": questions, "answers": st.session_state.get(ans_key) or {}, "index": int(st.session_state.get(idx_key, 0))}
            _save_user_progress(user.get("email"), {"practice_session": checkpoint})
            ts = datetime.now().strftime("%H:%M:%S")
            st.session_state["bm_last_auto_save"] = ts
            msg = f"Auto-saved (Q{int(st.session_state.get(idx_key,0))+1}) at {ts}"
            st.session_state["bm_auto_save_msg"] = msg
            st.session_state["bm_auto_save_msg_ts"] = datetime.now()
            try:
                st.markdown(f"<div id='bm-live' aria-live='polite' aria-atomic='true' style='position:absolute;left:-10000px'>{msg}</div>", unsafe_allow_html=True)
            except Exception:
                pass
            try:
                st.markdown(f"<div id='bm-focus-label' style='position:absolute;left:-10000px'>{selected}</div>", unsafe_allow_html=True)
            except Exception:
                pass
    except Exception:
        pass

    if total <= 30:
        palette_cols = st.columns(min(total, 10))
        for i in range(total):
            col = palette_cols[i % len(palette_cols)]
            qid = questions[i].get("id")
            ans = (st.session_state.get(ans_key) or {}).get(qid)
            flagged = bool((st.session_state.get(flag_key) or {}).get(qid))
            if flagged:
                marker = "⚑"
            elif ans:
                marker = "●"
            else:
                marker = "○"
            current = "▸" if i == current_idx else ""
            if col.button(f"{current}Q{i+1}{marker}", key=f"{prefix}_qbtn_{i}"):
                st.session_state[idx_key] = i
                _safe_rerun()

    next_idx = _recommend_next_index(questions, st.session_state.get(ans_key) or {}, current_idx)
    if next_idx is not None and next_idx != current_idx:
        st.info(f"Recommended next question: Q{next_idx + 1}")
        if st.button("Go to recommended next", key=f"{prefix}_recommended_next"):
            st.session_state[idx_key] = next_idx
            _safe_rerun()

    submit_clicked = st.button(submit_label, key=f"{prefix}_submit")
    # Show a compact inline auto-save indicator when available (only while recent)
    last = st.session_state.get("bm_last_auto_save")
    toast = st.session_state.get("bm_auto_save_msg")
    toast_ts = st.session_state.get("bm_auto_save_msg_ts")
    now = datetime.now()
    if toast and toast_ts and (now - toast_ts).total_seconds() <= 3:
        st.markdown(f"<div class='bm-toast'>{toast}</div>", unsafe_allow_html=True)
    elif toast and not toast_ts:
        st.session_state["bm_auto_save_msg_ts"] = now
        st.markdown(f"<div class='bm-toast'>{toast}</div>", unsafe_allow_html=True)
    # Inline timestamp (permanent)
    if last:
        st.markdown(f"<div class='bm-autosave-inline'>Auto-saved: {last}</div>", unsafe_allow_html=True)
    return submit_clicked, (st.session_state.get(ans_key) or {})


def _render_math_text(txt: str):
    """Render text preferring LaTeX/math formatting when appropriate."""
    if not txt:
        return
    s = str(txt)
    # If the string already contains explicit LaTeX markers, render as-is
    if '$' in s or '\\(' in s or '\\)' in s or '\\frac' in s or '\\sqrt' in s:
        # Prefer display math for longer LaTeX content
        if '\n' in s or len(s) > 120 or re.search(r"\\frac|\\sqrt|\\begin|\\frac", s):
            st.markdown(f"$$\n{s}\n$$")
        else:
            st.markdown(s)
        return

    # Heuristic: if it looks like an equation or contains x, =, ^, /, or digits with variables, render as LaTeX
    if re.search(r"=|\^|\\frac|\\sqrt|\bx\b|\d+[a-zA-Z]|[a-zA-Z]\^\d|/", s):
        # use display math for longer formulas, inline for short expressions
        try:
            if len(s) > 80 or '\n' in s or re.search(r"\\frac|\\sqrt", s):
                st.markdown(f"$$\n{s}\n$$")
            else:
                st.markdown(f"${s}$")
            return
        except Exception:
            wrapped = re.sub(r"(?<!\$)(\b\d+\s*[+\-*/=^]\s*\d+(?:\s*[+\-*/=^]\s*\d+)*)", r"$\1$", s)
            st.markdown(wrapped)
            return

    # default: markdown paragraph
    st.markdown(s)
def _safe_rerun():
    """Call Streamlit's experimental rerun if available, otherwise no-op."""
    try:
        func = getattr(st, "experimental_rerun", None)
        if callable(func):
            func()
    except Exception:
        # swallow errors to avoid aborting the app
        pass


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
        --paper: #f4f8fc;
        --ink: #0b1f35;
        --muted: #213543;
        --accent: #005a8d;
        --accent-soft: #e0eef9;
        --line: #c6d8e8;
        --shadow: rgba(11, 31, 53, 0.10);
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
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 0.85rem 1rem;
        color: var(--muted);
    }

    .stButton > button { border-radius:8px; border: none; background: var(--accent); color: white; font-weight:600; padding:0.6rem 0.85rem }
    .stButton > button p, .stButton > button span, .stButton > button div { color: white !important; }
    .stButton > button:hover { filter:brightness(0.95); }

    .stButton > button[kind="secondary"] {
        background: #eef4fb !important;
        color: var(--ink) !important;
        border: 1px solid var(--line) !important;
    }
    .stButton > button[kind="secondary"] p,
    .stButton > button[kind="secondary"] span,
    .stButton > button[kind="secondary"] div {
        color: var(--ink) !important;
    }

    .stButton > button:disabled {
        background: #b8c9d8 !important;
        color: #20364d !important;
        border: 1px solid #95adc2 !important;
        opacity: 1 !important;
        filter: none !important;
    }
    .stButton > button:disabled p,
    .stButton > button:disabled span,
    .stButton > button:disabled div {
        color: #20364d !important;
        opacity: 1 !important;
    }

    .stTextInput input,
    .stTextArea textarea,
    .stDateInput input,
    div[data-baseweb="select"] > div {
        background: #ffffff !important;
        color: var(--ink) !important;
        border: 1px solid var(--line) !important;
    }

    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder,
    .stDateInput input::placeholder {
        color: #4a6476 !important;
        opacity: 1 !important;
    }

    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stDateInput input:focus,
    div[data-baseweb="select"] > div:focus-within {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px rgba(0, 90, 141, 0.18) !important;
    }

    .bm-choice { border-radius: 6px; padding: 0.5rem; margin-bottom: 0.25rem; }
    .bm-choice p { margin: 0; color: var(--ink); }
    .bm-choice.bm-selected { background: rgba(0,90,141,0.04); border: 1px solid rgba(0,90,141,0.12); }
    .bm-choice.bm-selected { background: rgba(0,90,141,0.10); border: 1px solid rgba(0,90,141,0.22); box-shadow: 0 4px 12px rgba(0,90,141,0.06); transition: background 150ms ease, transform 120ms ease; transform-origin: left; }
    .bm-choice.bm-selected::after { content: "✓"; float: right; background: var(--accent); color: white; border-radius: 999px; width: 1.4rem; height: 1.4rem; display: inline-flex; align-items: center; justify-content: center; font-weight:700; margin-left: 0.6rem; }
    .bm-choice { transition: background 120ms ease, border-color 120ms ease; }
    .bm-progress-saved { font-size:0.85rem; color: var(--accent); margin-left: 0.5rem; }
    /* compact floating toast for small status messages */
    .bm-toast {
        position: fixed;
        right: 1rem;
        bottom: 1.2rem;
        background: rgba(0,90,141,0.95);
        color: white;
        padding: 0.5rem 0.85rem;
        border-radius: 10px;
        box-shadow: 0 6px 18px rgba(11,31,53,0.12);
        font-size: 0.9rem;
        z-index: 9999;
    }
    .bm-autosave-inline { font-size:0.9rem; color:var(--ink); margin-left:0.6rem }
    /* Typography and spacing refinements */
    .bm-hero-title { font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.4rem; }
    .bm-hero-copy { font-size: 1.05rem; color: var(--muted); }
    .stCaptionContainer p { color: var(--ink) !important; }
    .bm-card { padding: 1.25rem; border-radius: 12px; min-height: 110px; }
    .bm-panel { padding: 1.25rem; border-radius: 12px; }
    .bm-index-item { padding: 0.6rem 0; }

    /* Buttons and layout */
    .stButton > button { padding: 0.66rem 0.95rem; border-radius: 10px; box-shadow: none; }
    .stButton + .stButton { margin-left: 0.6rem; }
    .stButton[kind="secondary"] > button { padding: 0.6rem 0.85rem; }

    /* Small select button inside choice blocks */
    .bm-choice .stButton > button { padding: 0.35rem 0.6rem; font-size:0.9rem; }
    .bm-choice { display:block; }

    /* Thicker, rounded progress bars */
    .stProgress > div > div {
        height: 12px !important;
        border-radius: 10px !important;
        background: linear-gradient(90deg, var(--accent) 0%, var(--accent) 100%) !important;
    }
    div[role="progressbar"] { height: 12px !important; }

    /* Choices: increase spacing and readability */
    .bm-choice { padding: 0.75rem; margin-bottom: 0.5rem; font-size: 1rem; }
    .bm-choice p { font-size: 0.98rem; color: var(--ink); }
    .bm-choice { cursor: pointer; }
    .bm-choice:not(.bm-selected):hover { background: rgba(0,90,141,0.02); transform: translateY(-2px); box-shadow: 0 6px 18px rgba(11,31,53,0.04); }

    /* Nav buttons (prev/next) larger and spaced */
    .stButton > button[aria-label] { padding: 0.6rem 0.9rem; }


    section[data-testid="stSidebar"] { background: linear-gradient(180deg,#ffffff 0%, #edf4fb 100%); border-right: 1px solid var(--line); }

    /* Custom progress rail for dashboard */
    .bm-progress-rail { background: #eef6fb; border-radius: 10px; height: 12px; width: 100%; overflow: hidden; border: 1px solid rgba(0,0,0,0.04); }
    .bm-progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent) 0%, #0079b6 100%); border-radius: 10px; transition: width 350ms ease; }
    /* Mini progress for question player */
    .bm-mini-progress-rail { background: #f3f7fb; height: 10px; border-radius: 10px; overflow:hidden; border:1px solid rgba(0,0,0,0.03); }
    .bm-mini-progress-fill { height:100%; background: linear-gradient(90deg, var(--accent) 0%, #33a0dd 100%); transition: width 250ms ease; }
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
    if "maths_auth_user" not in st.session_state:
        st.session_state.maths_auth_user = None
    if "maths_saved_practice_session" not in st.session_state:
        st.session_state.maths_saved_practice_session = None
    if "maths_saved_diagnostic_session" not in st.session_state:
        st.session_state.maths_saved_diagnostic_session = None


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
        user = st.session_state.get("maths_auth_user")
        if user and user.get("email"):
            _save_user_progress(user.get("email"), {"profile": st.session_state.maths_profile_saved})
        st.success("Study folio saved. The tutor will now use this profile.")
        st.rerun()

    st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='bm-eyebrow'>Saved profile</div>", unsafe_allow_html=True)
    st.caption(basic_maths.profile_summary(st.session_state.maths_profile_saved))
    if st.session_state.maths_profile_saved.get("weak_topics"):
        st.caption("Weak spots: " + ", ".join(st.session_state.maths_profile_saved.get("weak_topics", [])))


def _render_account_panel():
    st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='bm-eyebrow'>Student account</div>", unsafe_allow_html=True)

    user = st.session_state.get("maths_auth_user")
    if user:
        st.success(f"Signed in as {user.get('name', 'Student')}")
        st.caption(user.get("email", ""))
        if st.button("Sign out", key="maths_sign_out"):
            st.session_state.maths_auth_user = None
            _safe_rerun()
        return

    with st.expander("Sign in / Sign up", expanded=False):
        with st.form("maths_sign_in_form"):
            st.caption("Sign in to save progress and continue practice later.")
            login_email = st.text_input("Sign in email", key="maths_login_email")
            login_password = st.text_input("Password", type="password", key="maths_login_password")
            sign_in = st.form_submit_button("Sign in")
        if sign_in:
            ok, account, msg = _account_sign_in(login_email, login_password)
            if ok:
                st.session_state.maths_auth_user = account
                saved = _load_user_progress(account.get("email"))
                if saved.get("profile"):
                    st.session_state.maths_profile_saved = saved.get("profile")
                    _sync_draft_widgets(st.session_state.maths_profile_saved)
                if saved.get("practice_result"):
                    st.session_state.maths_practice_result = saved.get("practice_result")
                if saved.get("quiz_result"):
                    st.session_state.maths_quiz_result = saved.get("quiz_result")
                st.session_state.maths_saved_practice_session = saved.get("practice_session")
                st.session_state.maths_saved_diagnostic_session = saved.get("diagnostic_session")
                st.success(msg)
                _safe_rerun()
            else:
                st.error(msg)

        with st.form("maths_sign_up_form"):
            st.caption("New student? Create an account.")
            su_name = st.text_input("Full name", key="maths_signup_name")
            su_email = st.text_input("Sign up email", key="maths_signup_email")
            su_password = st.text_input("Create password", type="password", key="maths_signup_password")
            sign_up = st.form_submit_button("Sign up")
        if sign_up:
            ok, msg = _account_sign_up(su_name, su_email, su_password)
            if ok:
                st.success(msg + " Please sign in.")
            else:
                st.error(msg)


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
            "<div class='bm-index-item'><strong>Diagnostic clarity</strong><br/><span style='color:var(--muted)'>30 questions curated by grade and topic readiness.</span></div>"
            "<div class='bm-index-item'><strong>Targeted recommendations</strong><br/><span style='color:var(--muted)'>Review incorrect answers and focus on the exact skills that need attention.</span></div>"
            "<div class='bm-index-item'><strong>Academic planning</strong><br/><span style='color:var(--muted)'>Week-by-week practice tailored to the student stage and goals.</span></div>"
            "<div class='bm-index-item'><strong>Appointment scheduling</strong><br/><span style='color:var(--muted)'>Auto-book coaching slots based on availability.</span></div>"
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
            f"<div class='bm-index-item'><strong>Profile</strong><br/><span style='color:var(--muted)'>{basic_maths.profile_summary(profile)}</span></div>"
            f"<div class='bm-index-item'><strong>Recommended focus</strong><br/><span style='color:var(--muted)'>{summary['recommendations'][0]['title'] if summary['recommendations'] else 'Balanced review'}</span></div>"
            f"<div class='bm-index-item'><strong>Next practice</strong><br/><span style='color:var(--muted)'>{next_practice}</span></div>"
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
                                <section class='bm-card' aria-label='{card['title']}'>
                                    <h3 style='margin-top:0;margin-bottom:0.35rem;font-size:1.05rem'>{card['title']}</h3>
                  <p><strong>Why now:</strong> {card['subtitle']}</p>
                  <div class='bm-divider'></div>
                  <p><strong>Practice:</strong> {card['practice']}</p>
                  <p style='margin-top:0.45rem'><strong>Common mistake:</strong> {card['mistake']}</p>
                                </section>
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
                                <section class='bm-card' aria-label='{item['day']} plan'>
                                    <h3 style='margin-top:0;margin-bottom:0.35rem;font-size:1.05rem'>{item['day']}</h3>
                  <p><strong>{item['title']}</strong></p>
                  <p>{item['description']}</p>
                                </section>
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
                                <section class='bm-card' aria-label='{item['label']} milestone'>
                                    <h3 style='margin-top:0;margin-bottom:0.35rem;font-size:1.05rem'>{item['label']}</h3>
                  <p>{item['note']}</p>
                                </section>
                """,
                unsafe_allow_html=True,
            )


def _render_practice_lab(profile, ai_client, provider):
    st.markdown("<div class='bm-eyebrow'>Practice lab</div>", unsafe_allow_html=True)
    st.subheader("Ask the tutor")

    user = st.session_state.get("maths_auth_user")
    if user and user.get("email"):
        resume_cols = st.columns(2)
        saved_practice = st.session_state.get("maths_saved_practice_session")
        saved_diag = st.session_state.get("maths_saved_diagnostic_session")
        with resume_cols[0]:
            if saved_practice and saved_practice.get("questions") and not st.session_state.get("maths_practice_questions"):
                if st.button("Resume unfinished practice", key="resume_saved_practice"):
                    st.session_state.maths_practice_questions = saved_practice.get("questions", [])
                    st.session_state["practice_answers"] = saved_practice.get("answers", {})
                    st.session_state["practice_index"] = int(saved_practice.get("index", 0))
                    _safe_rerun()
        with resume_cols[1]:
            if saved_diag and saved_diag.get("questions") and not st.session_state.get("maths_diagnostic_questions"):
                if st.button("Resume unfinished diagnostic", key="resume_saved_diag"):
                    st.session_state.maths_diagnostic_questions = saved_diag.get("questions", [])
                    st.session_state["diagnostic_answers"] = saved_diag.get("answers", {})
                    st.session_state["diagnostic_index"] = int(saved_diag.get("index", 0))
                    _safe_rerun()

    # Debug: load a preview of numerical practice questions for QA
    try:
        if _debug_mode_enabled(_load_secrets()):
            with st.sidebar.expander("Admin: QA / Previews", expanded=False):
                if st.button("Load numerical practice preview (20)", key="load_num_preview"):
                    kb = mcq_manager.load_kb()
                    if kb is None:
                        st.warning("No knowledge base found.")
                        return
                    dom = kb.get("mcq_bank", {}).get("middle", {}).get("domains", {}).get("numerical-practice", {})
                    questions = dom.get("questions", [])[:20]
                    if questions:
                        st.session_state.maths_practice_questions = questions
                        st.session_state.practice_answers = {}
                        st.session_state.practice_index = 0
                        _safe_rerun()
                    else:
                        st.warning("No numerical practice questions found in KB.")
    except Exception:
        pass

    # Allow users to start a numerical practice set directly
    if st.button("Start numerical practice (20)", key="start_num_practice"):
        questions = mcq_manager.sample_numerical_practice(level="middle", num_questions=20)
        if questions:
            st.session_state.maths_practice_questions = questions
            st.session_state.practice_answers = {}
            st.session_state.practice_index = 0
            _safe_rerun()
        else:
            st.warning("No numerical practice questions available right now.")

    # If a practice set was requested from a recommendation card, render it first
    if st.session_state.get("maths_practice_questions"):
        questions = st.session_state.get("maths_practice_questions") or []
        submit_practice, practice_answers = _render_question_player(
            questions,
            prefix="practice",
            title="Practice",
            submit_label="Submit practice",
        )

        if user and user.get("email"):
            checkpoint = {
                "questions": questions,
                "answers": practice_answers,
                "index": int(st.session_state.get("practice_index", 0)),
            }
            _save_user_progress(user.get("email"), {"practice_session": checkpoint})
            st.session_state.maths_saved_practice_session = checkpoint

        if submit_practice:
            responses = {}
            for q in questions:
                sel = practice_answers.get(q.get("id"))
                responses[q["id"]] = _choice_to_index(sel, len(q.get("choices", []) or []))

            result = mcq_manager.evaluate_responses(responses)
            st.session_state.maths_practice_result = result
            if user and user.get("email"):
                _save_user_progress(user.get("email"), {"practice_result": result, "practice_session": None})
                st.session_state.maths_saved_practice_session = None
            try:
                del st.session_state["maths_practice_questions"]
                del st.session_state["practice_answers"]
                del st.session_state["practice_index"]
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
                    _safe_rerun()
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
            st.markdown(f"<section class='bm-card' aria-label='Coach reply'><h3 style='margin-top:0;margin-bottom:0.35rem;font-size:1.05rem'>Coach reply</h3><p>{reply}</p></section>", unsafe_allow_html=True)
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
            st.session_state["diagnostic_answers"] = {}
            st.session_state["diagnostic_index"] = 0
            if user and user.get("email"):
                checkpoint = {"questions": questions, "answers": {}, "index": 0}
                _save_user_progress(user.get("email"), {"diagnostic_session": checkpoint})
                st.session_state.maths_saved_diagnostic_session = checkpoint

    if st.session_state.get("maths_diagnostic_questions"):
        questions = st.session_state.maths_diagnostic_questions
        submit_diag, diagnostic_answers = _render_question_player(
            questions,
            prefix="diagnostic",
            title="Diagnostic",
            submit_label="Submit diagnostic",
        )

        if user and user.get("email"):
            checkpoint = {
                "questions": questions,
                "answers": diagnostic_answers,
                "index": int(st.session_state.get("diagnostic_index", 0)),
            }
            _save_user_progress(user.get("email"), {"diagnostic_session": checkpoint})
            st.session_state.maths_saved_diagnostic_session = checkpoint

        if submit_diag:
            responses = {}
            for q in questions:
                sel = diagnostic_answers.get(q.get("id"))
                responses[q["id"]] = _choice_to_index(sel, len(q.get("choices", []) or []))

            result = mcq_manager.evaluate_responses(responses)
            st.session_state.maths_quiz_result = result
            if user and user.get("email"):
                _save_user_progress(user.get("email"), {"quiz_result": result, "diagnostic_session": None})
                st.session_state.maths_saved_diagnostic_session = None
            # clear questions after submission
            del st.session_state.maths_diagnostic_questions
            try:
                del st.session_state["diagnostic_answers"]
                del st.session_state["diagnostic_index"]
            except Exception:
                pass
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
                        f"<section class='bm-card' aria-label='{domain_label}'>"
                        f"<h3 style='margin-top:0;margin-bottom:0.35rem;font-size:1.05rem'>{domain_label}</h3>"
                        f"<p><strong>Incorrect:</strong> {rec.get('wrong',0)}/{rec.get('total',0)}</p>"
                        f"<p><strong>Suggested practice:</strong> {rec.get('suggested_practice',0)} Qs · ~{rec.get('suggested_minutes',0)} mins</p>"
                        f"<div class='bm-divider'></div>"
                        f"<p><strong>Actions:</strong></p><ul>{actions_html}</ul>"
                        f"</section>",
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
                        _safe_rerun()

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
                            _safe_rerun()


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
    # If signed-in user has a saved practice session, blend that into the visible dashboard progress
    user = st.session_state.get("maths_auth_user")
    try:
        if user and user.get("email"):
            saved = _load_user_progress(user.get("email")) or {}
            ps = saved.get("practice_session") or {}
            if ps and isinstance(ps.get("questions"), list) and ps.get("index") is not None:
                idx = int(ps.get("index", 0))
                total = len(ps.get("questions", [])) or 1
                practice_pct = int(round((idx / total) * 100))
                # blend base dashboard stat with practice completion: 60% base, 40% practice
                stats["progress"] = int(round(stats.get("progress", 0) * 0.6 + practice_pct * 0.4))
    except Exception:
        pass

    with st.sidebar:
        st.markdown("<div class='bm-eyebrow'>Basic Maths Prep</div>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0'>Personalised maths prep desk</h3>", unsafe_allow_html=True)
        st.caption("A calm, student-friendly workspace for diagnostics, revision planning, and coaching.")
        pval = int(min(max(stats.get("progress", 0), 0), 100))
        st.markdown(f"<div class='bm-progress-rail'><div class='bm-progress-fill' style='width:{pval}%;'></div></div>", unsafe_allow_html=True)
        st.caption(f"Learning progress: {pval}%")

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
        _render_account_panel()

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
                _safe_rerun()
            if discard:
                try:
                    del st.session_state["maths_variant_preview"]
                except Exception:
                    pass
                st.session_state.maths_show_preview = False
                _safe_rerun()

    # If a quick-practice modal was requested, show it here (keeps user on same page)
    if st.session_state.get("maths_show_modal") and st.session_state.get("maths_modal_questions"):
        with st.modal("Quick practice"):
            mq = st.session_state.get("maths_modal_questions") or []
            submit_modal, modal_answers = _render_question_player(mq, prefix="modal", title="Quick practice", submit_label="Submit practice")

            if submit_modal:
                responses = {}
                for q in mq:
                    sel = modal_answers.get(q.get("id"))
                    responses[q["id"]] = _choice_to_index(sel, len(q.get("choices", []) or []))

                result = mcq_manager.evaluate_responses(responses)
                st.session_state.maths_practice_result = result
                # clear modal flags
                try:
                    del st.session_state["maths_modal_questions"]
                except Exception:
                    pass
                st.session_state.maths_show_modal = False
                try:
                    del st.session_state["modal_answers"]
                    del st.session_state["modal_index"]
                except Exception:
                    pass
                analytics_module.log_interaction(profile.get("student_name") or "maths-student", "practice", str(result))

    if nav == "Dashboard":
        _render_hero(profile, summary, stats)
        st.markdown("<div class='bm-divider'></div>", unsafe_allow_html=True)
        action_cols = st.columns(3)
        with action_cols[0]:
            st.markdown(
                "<section class='bm-card' aria-label='Recommendations'><h3 style='margin-top:0;margin-bottom:0.35rem;font-size:1.05rem'>Recommendations</h3><p>Review the top topics the system suggests for your stage and goal.</p></section>",
                unsafe_allow_html=True,
            )
        with action_cols[1]:
            st.markdown(
                "<section class='bm-card' aria-label='Academic planning'><h3 style='margin-top:0;margin-bottom:0.35rem;font-size:1.05rem'>Academic planning</h3><p>Follow a weekly plan based on your current profile and progress.</p></section>",
                unsafe_allow_html=True,
            )
        with action_cols[2]:
            st.markdown(
                "<section class='bm-card' aria-label='Schedule support'><h3 style='margin-top:0;margin-bottom:0.35rem;font-size:1.05rem'>Schedule support</h3><p>Book a coaching slot automatically from available times.</p></section>",
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
