Deployment Guide — New GitHub Repository

Treat this project as a fresh codebase for deployment. Do not reuse or push to an existing repository with prior history.

1) Initialize a new repository locally

   git init
   git add .
   git commit -m "Initial import: Shapers Academic Advisor - Basic Maths Prep"

2) Create a new empty repository on GitHub (choose organization or personal account).
   - Do not import or fork the previous project; choose "Create new repository".

3) Add remote and push

   git remote add origin git@github.com:<your_org_or_user>/<new_repo>.git
   git branch -M main
   git push -u origin main

4) Secrets & environment
   - Do NOT commit secrets. Use GitHub Actions encrypted secrets or your hosting provider's secret store.
   - For local Streamlit testing, use `.streamlit/secrets.toml` (ignored by .gitignore).
   - Environment variables expected by the app: `OPENAI_API_KEY`, `GOOGLE_API_KEY` (optional for AI features).

5) CI/CD & hosting
   - Recommended: deploy with GitHub Actions + Streamlit Cloud / Vercel / Render.
   - Add a workflow file to run tests and deploy on push to `main`.

6) Notes
   - This repository is organized to be self-contained; when creating the new GitHub repo, mark it as private until you have reviewed content for sensitive data.
   - If you want, I can create a ready-to-use `.github/workflows/ci.yml` that runs tests and deploys to Streamlit Cloud or another target.

Contact me if you want me to create the repo, CI workflow, or deploy settings programmatically.
