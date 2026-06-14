import os
import time
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

# Skip E2E tests by default in CI unless RUN_E2E=true
if os.environ.get("RUN_E2E", "false").lower() != "true":
    pytest.skip("Skipping e2e tests by default (set RUN_E2E=true to enable)", allow_module_level=True)

BASE_URL = os.environ.get("APP_URL", "http://localhost:8505")

def test_practice_flow_keyboard_and_click():
    # Make sure we use a unique test user
    test_username = f"e2e_{int(time.time())}@example.com"
    test_password = "password123"
    test_fullname = "E2E Tester"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)

        # Register a new user dynamically
        page.wait_for_selector('text="Sign In"', timeout=60000)
        page.get_by_role("tab").nth(1).click() # Click Create Account tab
        time.sleep(1)

        fullname_input = page.locator('input[type="text"]').nth(1)
        fullname_input.fill(test_fullname)
        
        reg_username_input = page.locator('input[type="text"]').nth(2)
        reg_username_input.fill(test_username)
        
        reg_password_input = page.locator('input[type="password"]').nth(1)
        reg_password_input.fill(test_password)
        
        page.get_by_role("button", name="Create Account").click()
        time.sleep(2)

        # Switch to Sign In tab and log in
        page.get_by_role("tab").nth(0).click()
        time.sleep(1)

        username_input = page.locator('input[type="text"]').nth(0)
        username_input.fill(test_username)
        
        password_input = page.locator('input[type="password"]').nth(0)
        password_input.fill(test_password)
        
        page.get_by_role("button", name="Sign In").click()

        # Wait for dashboard to load
        page.wait_for_selector(f'text="Welcome, {test_fullname}!"', timeout=30000)

        # Configure parametric quiz
        page.get_by_text("Mode 2: Tailor from Parameters").click()
        time.sleep(1)

        page.get_by_label("Topic / Chapter", exact=False).fill("Coordinate Geometry")
        time.sleep(1)

        # Generate quiz
        page.get_by_role("button", name="Generate Parametric Quiz").click()

        # Wait for iframe to render
        page.wait_for_selector('iframe', timeout=60000)
        time.sleep(2)

        iframe_element = page.query_selector('iframe')
        frame = iframe_element.content_frame()

        # Start quiz inside iframe
        frame.wait_for_selector('#userNameInput', timeout=15000)
        frame.locator('#userNameInput').fill(test_fullname)
        time.sleep(0.5)
        frame.evaluate("document.querySelector('.start-button').click()")

        # Solve Q1
        frame.wait_for_selector('#question1', timeout=15000)
        frame.evaluate("document.querySelector('#options1 .option').click()")
        time.sleep(0.5)

        # Verify that we can click next
        frame.evaluate("document.querySelector('button[onclick=\"nextQuestion()\"]').click()")
        time.sleep(0.5)

        # Wait for Q2 to load
        frame.wait_for_selector('#question2', timeout=15000)
        
        browser.close()
