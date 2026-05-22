# Architecture

Basic Maths Prep is organized around a small, testable core and a Streamlit UI shell.

## Main parts

- `app/streamlit_app.py` - entrypoint wrapper used by Streamlit.
- `app/basic_maths_app.py` - renders the dashboard, learning path, practice lab, appointment flow, and analytics views.
- `app/basic_maths.py` - contains recommendations, study planning, topic summaries, and AI fallback replies.
- `app/appointments.py` - JSON-backed appointment storage plus automatic slot suggestion.
- `app/analytics_module.py` - logs practice interactions and prepares trend tables for charts.
- `app/sentiment.py` - optional sentiment scoring for logged practice text.
- `app/api_client.py` - provider wrapper for OpenAI, Google, or mock responses.

## Data flow

1. The user saves a study profile in the sidebar.
2. The dashboard uses that profile to generate topic recommendations and the weekly plan.
3. The practice lab logs user prompts and coach replies.
4. The analytics view reads the log file and plots daily activity.
5. Appointment booking picks the next available slot and stores it in `data/appointments.json`.

## Design notes

- The UI uses a warm, editorial palette inspired by the reference images.
- The content is original and maths-focused.
- The app stays functional even without external AI keys because of the deterministic fallback.
