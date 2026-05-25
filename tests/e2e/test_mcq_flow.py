import os
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import pytest

# Skip E2E tests by default in CI unless RUN_E2E=true
if os.environ.get("RUN_E2E", "false").lower() != "true":
    pytest.skip("Skipping e2e tests by default (set RUN_E2E=true to enable)", allow_module_level=True)

BASE_URL = os.environ.get("APP_URL", "http://localhost:8505")
PROGRESS_FILE = Path(__file__).resolve().parents[2] / "data" / "user_progress.json"


def _resolve_test_email():
    # Allow CI or local runs to specify an email via env var.
    env = os.environ.get("E2E_TEST_EMAIL")
    if env:
        return env
    # If a progress file exists, prefer an existing user to avoid collisions.
    try:
        if PROGRESS_FILE.exists():
            data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data:
                # return the first existing email
                return next(iter(data.keys()))
    except Exception:
        pass
    # default fallback
    return "e2e@example.com"


def test_practice_flow_keyboard_and_click():
    TEST_EMAIL = _resolve_test_email()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)

        # Sign up / sign in flow (create a test user)
        # Wait for sign-in expander to appear and open it
        try:
            page.wait_for_selector("text=Sign in / Sign up", timeout=60000)
            page.click("text=Sign in / Sign up")
        except Exception:
            # fallback: continue if not present
            pass

        # If the test email is not an existing user, attempt sign up first.
        existing_users = {}
        try:
            if PROGRESS_FILE.exists():
                existing_users = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            existing_users = {}

        if TEST_EMAIL not in existing_users:
            page.fill('input[aria-label="Full name"]', "E2E Tester")
            page.fill('input[aria-label="Sign up email"]', TEST_EMAIL)
            page.fill('input[aria-label="Create password"]', "e2e-pass-123")
            page.click('button:has-text("Sign up")')

        # sign in
        page.fill('input[aria-label="Sign in email"]', TEST_EMAIL)
        page.fill('input[aria-label="Password"]', "e2e-pass-123")
        page.click('button:has-text("Sign in")')

        # Start numerical practice
        page.click('text=Practice Lab')
        page.click('text=Start numerical practice (20)')
        page.wait_for_selector('text=Question 1 of')

        # Select first choice via keyboard (A)
        page.keyboard.press('A')
        time.sleep(0.5)

        # Select second question via Next and click choice block
        page.click('button:has-text("Next")')
        page.wait_for_selector('text=Question 2 of')
        # click the first .bm-choice element on the page
        page.click('.bm-choice')
        time.sleep(0.5)

        # Validate progress file updated for user
        assert PROGRESS_FILE.exists(), "progress file not found"
        data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        assert TEST_EMAIL in data, f"user progress not saved for {TEST_EMAIL}"
        entry = data[TEST_EMAIL]
        assert "practice_session" in entry
        ps = entry["practice_session"]
        assert isinstance(ps.get("questions"), list)
        assert isinstance(ps.get("answers"), dict)

        browser.close()
