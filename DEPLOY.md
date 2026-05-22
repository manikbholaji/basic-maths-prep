# Deployment Guide — Streamlit Community Cloud & GitHub

This document walks you through pushing the project to GitHub and deploying on Streamlit Community Cloud.

## 1) Create a GitHub repository

- Create a new repository on GitHub (e.g., `shapers_academic_advisor`).
- Locally, in PowerShell or terminal, run:

```powershell
cd "f:\My Project\shapers_academic_advisor"
git init
git add .
git commit -m "Initial project scaffold for SHAPERS Academic Advisor"
# Replace the remote URL with your repo
git remote add origin https://github.com/<your-username>/shapers_academic_advisor.git
git branch -M main
git push -u origin main
```

## 2) Add Streamlit secrets

- On Streamlit Community Cloud (https://streamlit.io/cloud), create a new app and link your GitHub repo.
- In the app settings → Secrets, add the secret for the provider you want to use. Do NOT commit API keys in the repo.

Use one of these blocks:

OpenAI:

```toml
OPENAI_API_KEY = "sk-your-real-openai-key-here"
```

Google Gemini:

```toml
GOOGLE_API_KEY = "your-real-google-api-key-here"
```

Dialogflow:

```toml
DIALOGFLOW_PROJECT_ID = "your-dialogflow-project-id"
DIALOGFLOW_ACCESS_TOKEN = "your-dialogflow-access-token"
```

## 3) Configure the app entrypoint

Streamlit will run `app/streamlit_app.py` by default. If needed, set the `Main file` in Streamlit settings to `app/streamlit_app.py`.

The deployed app now has a Gemini-style composer flow:

- Students choose **Text**, **PNG**, or **PDF** before generating a response.
- Students can edit and resubmit earlier prompts from prompt history.
- The sidebar profile editor requires **Save profile** before the chatbot uses updated student details.
- The admin panel includes stream guidance for Class 11/12.
- The admin panel also includes India-wide diploma, undergraduate, and postgraduate program recommendations with example institutions.
- Appointment booking uses a date picker and peak-hour time slots.
- PNG and PDF responses are formatted for readable A4-style output.

## 4) Runtime & dependencies

Streamlit installs packages from `requirements.txt`. Ensure it contains `streamlit`, `openai`, `google-auth`, `requests`, `Pillow`, `reportlab`, `vaderSentiment`, `pandas`, and `plotly`.

## 5) Optional: GitHub Actions for CI

A basic `python-app.yml` is included under `.github/workflows/` to install dependencies and run optional checks on push.

## 6) Debugging deployment issues

- If the sidebar says **Mock mode**, the app is working but no provider secret is configured yet.
- If app fails to start, check the `Logs` panel in Streamlit Cloud for errors.
- Common issues: missing secrets, package install errors, or an incorrect main file path.

## 7) Local testing before push

```powershell
cd "f:\My Project\shapers_academic_advisor"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m tests.conversational_tests
streamlit run app/streamlit_app.py
```

## 8) Verify the prompt composer flow

- Open the Chat page.
- Enter a prompt, pick **Text**, **PNG**, or **PDF**, and submit.
- Use the prompt history section to edit an earlier prompt and resubmit it in place.
- Save the student profile before testing board/class-aware responses.

## 9) Verify stream guidance and booking

- Open the Admin page and test the stream recommender with Class 11/12 inputs.
- Open Book Appointment and confirm only working-hour time slots are available.
- Generate a PNG or PDF response and check that the exported layout is clean and readable.

If you want I can prepare the `git` commands and create the GitHub repo skeleton for you; you'll need to push the code from your computer or provide a GitHub token to create the repo from here.
