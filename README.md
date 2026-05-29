# Basic Maths Prep

Basic Maths Prep is a Streamlit study site for school maths revision. It uses an editorial, split-layout design inspired by the provided sample pages, but all copy and logic are original. The app focuses on topic recommendations, academic planning, practice coaching, and automated appointment scheduling.

## What it includes

- A landing-style dashboard with a profile-led study summary.
- Personalised topic recommendations for numbers, fractions, algebra, geometry, mensuration, and exam strategy.
- Academic planning suggestions, including a weekly study plan and revision timeline.
- A practice lab that can answer maths questions with an AI client or a deterministic fallback.
- Automated appointment scheduling that picks the next available coaching slot.
- Analytics for logged practice interactions.

## Local setup

```powershell
cd "f:\My Project\basic-maths-prep"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Testing

```powershell
cd "f:\My Project\basic-maths-prep"
python -m pytest -q
```

## Project structure

- `app/streamlit_app.py` - Streamlit entrypoint
- `app/basic_maths_app.py` - Main Basic Maths Prep UI
- `app/basic_maths.py` - recommendations, planning, and reply helpers
- `app/appointments.py` - appointment storage and auto-scheduling
- `app/analytics_module.py` - practice log tracking and summaries
- `tests/` - unit and UI coverage

## Notes

- The app works offline with the mock AI fallback.
- If you add OpenAI or Google secrets, the coach replies become AI-backed.
- The saved profile button must be used before the dashboard recommendations update.
