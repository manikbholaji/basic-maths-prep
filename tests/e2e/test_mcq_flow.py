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
    env = os.environ.get("E2E_TEST_EMAIL")
    if env:
        return env
    try:
        if PROGRESS_FILE.exists():
            data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data:
                return next(iter(data.keys()))
    except Exception:
        pass
    return "e2e@example.com"


def _open_sign_in_panel(page):
    try:
        page.click("text=Sign in / Sign up")
    except Exception:
        pass


def _fill_sign_in(page, email: str, password: str):
    email_locators = [
        'input[aria-label="Sign in email"]',
        'xpath=//label[contains(normalize-space(.), "Sign in email")]/following::input[1]',
        'input[type="email"]',
        'input[type="text"]',
    ]
    password_locators = [
        'input[aria-label="Password"]',
        'xpath=//label[contains(normalize-space(.), "Password")]/following::input[1]',
        'input[type="password"]',
    ]
    for selector in email_locators:
        try:
            locator = page.locator(selector)
            if locator.count() and locator.first.is_visible():
                locator.first.fill(email)
                break
        except Exception:
            continue
    for selector in password_locators:
        try:
            locator = page.locator(selector)
            if locator.count() and locator.first.is_visible():
                locator.first.fill(password)
                break
        except Exception:
            continue


def test_practice_flow_keyboard_and_click():
    TEST_EMAIL = _resolve_test_email()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)

        existing_users = {}
        try:
            if PROGRESS_FILE.exists():
                existing_users = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            existing_users = {}

        _open_sign_in_panel(page)
        if TEST_EMAIL not in existing_users:
            page.fill('input[aria-label="Full name"]', "E2E Tester")
            page.fill('input[aria-label="Sign up email"]', TEST_EMAIL)
            page.fill('input[aria-label="Create password"]', "e2e-pass-123")
            page.click('button:has-text("Sign up")')
            page.wait_for_selector('text=Signed in as', timeout=60000)
        else:
            _fill_sign_in(page, TEST_EMAIL, "e2e-pass-123")
            page.click('button:has-text("Sign in")')

        page.click('text=Practice Lab')
        page.click('text=Start numerical practice (20)')
        page.wait_for_selector('text=Question 1 of', timeout=30000)

        # Select choice A via keyboard
        page.keyboard.press('A')
        time.sleep(1.0) # wait for auto-save

        page.click('button:has-text("Next")')
        page.wait_for_selector('text=Question 2 of', timeout=30000)

        # Click the first 'Select' button
        first_select_btn = page.locator('button:has-text("Select")').first
        first_select_btn.wait_for(state="visible", timeout=30000)
        first_select_btn.click()
        time.sleep(1.0) # wait for auto-save

        assert PROGRESS_FILE.exists(), "progress file not found"
        data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        assert TEST_EMAIL in data, f"user progress not saved for {TEST_EMAIL}"
        entry = data[TEST_EMAIL]
        assert "practice_session" in entry
        ps = entry["practice_session"]
        assert isinstance(ps.get("questions"), list)
        assert isinstance(ps.get("answers"), dict)

        browser.close()
