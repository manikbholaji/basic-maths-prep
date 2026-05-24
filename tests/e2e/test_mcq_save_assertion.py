import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get('APP_URL', 'http://localhost:8505')


def test_practice_flow_wait_for_save():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)
        # Start numerical practice quickly
        page.click('text=Practice Lab')
        page.click('text=Start numerical practice (20)')
        page.wait_for_selector('text=Question 1 of')

        # make a selection via keyboard
        page.keyboard.press('A')
        # wait for autosave liveregion/text - our app emits 'Auto-saved' briefly
        try:
            page.wait_for_selector('text=Auto-saved', timeout=5000)
        except Exception:
            # fallback: wait for role=status or aria-live region
            page.wait_for_selector('[role="status"]', timeout=5000)

        # navigate next and click a choice
        page.click('button:has-text("Next")')
        page.wait_for_selector('text=Question 2 of')
        page.click('.bm-choice')
        try:
            page.wait_for_selector('text=Auto-saved', timeout=5000)
        except Exception:
            page.wait_for_selector('[role="status"]', timeout=5000)

        browser.close()
