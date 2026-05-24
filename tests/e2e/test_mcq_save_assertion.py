import os
import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get('APP_URL', 'http://localhost:8505')
PROGRESS_FILE = Path(__file__).resolve().parents[2] / "data" / "user_progress.json"


def _resolve_test_email():
    env = os.environ.get('E2E_TEST_EMAIL')
    if env:
        return env
    try:
        if PROGRESS_FILE.exists():
            data = json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))
            if isinstance(data, dict) and data:
                return next(iter(data.keys()))
    except Exception:
        pass
    return 'e2e@example.com'


def test_practice_flow_wait_for_save():
    TEST_EMAIL = _resolve_test_email()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)

        # Sign in (or sign up) so autosave is persisted to user progress
        page.click('text=Sign in / Sign up')
        existing = {}
        try:
            if PROGRESS_FILE.exists():
                existing = json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))
        except Exception:
            existing = {}

        if TEST_EMAIL not in existing:
            page.fill('input[aria-label="Full name"]', 'E2E Tester')
            page.fill('input[aria-label="Sign up email"]', TEST_EMAIL)
            page.fill('input[aria-label="Create password"]', 'e2e-pass-123')
            page.click('button:has-text("Sign up")')

        page.fill('input[aria-label="Sign in email"]', TEST_EMAIL)
        page.fill('input[aria-label="Password"]', 'e2e-pass-123')
        page.click('button:has-text("Sign in")')

        # Start numerical practice quickly
        page.click('text=Practice Lab')
        page.click('text=Start numerical practice (20)')
        page.wait_for_selector('text=Question 1 of')

        # make a selection via keyboard
        page.keyboard.press('A')
        # wait for autosave liveregion/text - our app emits 'Auto-saved' briefly
        try:
            page.wait_for_selector('text=Auto-saved', timeout=7000)
        except Exception:
            # fallback: wait for role=status or aria-live region
            try:
                page.wait_for_selector('[role="status"]', timeout=5000)
            except Exception:
                pass

        # navigate next and click a choice
        page.click('button:has-text("Next")')
        page.wait_for_selector('text=Question 2 of')
        page.click('.bm-choice')

        # wait briefly for server-side save to flush and assert persisted progress
        time.sleep(1.2)
        import json
        assert PROGRESS_FILE.exists(), 'progress file not found'
        data = json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))
        assert TEST_EMAIL in data, f'user progress not saved for {TEST_EMAIL}'

        browser.close()
