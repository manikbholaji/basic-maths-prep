# Contributing

Thanks for considering contributing to the SHAPERS Academic Advisor project.

- Use the `main` branch for releases; create feature branches for changes.
- Write clear commit messages and open pull requests for review.
- Keep API keys out of commits — use `.streamlit/secrets.toml` locally or Streamlit secrets.

Suggested workflow:

```bash
git checkout -b feat/describe-change
# make changes
git add .
git commit -m "feat: add explanation"
git push origin feat/describe-change
# open PR on GitHub
```

Testing:
- Unit/Smoke tests are under `tests/` and can be run with `python -m tests.conversational_tests`.

Code style and linting are optional for this starter project.
