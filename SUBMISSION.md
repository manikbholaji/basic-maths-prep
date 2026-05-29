# Submission Notes - Basic Maths Prep

This document summarizes the project artifacts and how to run the rebuilt maths-prep experience.

## Project summary

- A Streamlit-based Basic Maths Prep site for school learners.
- Editorial landing page inspired by the sample references, but rebuilt with original content and layout.
- Profile-led recommendations, weekly academic planning, and revision timelines.
- AI-backed maths coach with a deterministic fallback.
- Automated appointment scheduling for coaching sessions.
- Analytics for practice interactions.

## Evaluation checklist

- Run the unit tests.
  - `python -m pytest -q`
- Open the app locally.
  - `streamlit run app/streamlit_app.py`
- Verify the following flows in the UI.
  - Save a student profile and confirm the dashboard updates.
  - Ask a maths question in the practice lab.
  - Auto-schedule a coaching appointment.
  - Check the analytics page for logged interactions.

## Local setup

```powershell
cd "f:\My Project\basic-maths-prep"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Test and demo commands

```powershell
python -m pytest -q
streamlit run app/streamlit_app.py
```

## Files included for submission

- `app/basic_maths_app.py`
- `app/basic_maths.py`
- `app/appointments.py`
- `app/analytics_module.py`
- `app/streamlit_app.py`
- `tests/`
- `scripts/`

## Notes for evaluators

- The app uses saved profile data to shape recommendations and planning suggestions.
- Appointment booking is automated and stores entries in `data/appointments.json`.
- If API secrets are not configured, the app falls back to a deterministic mock coach.
