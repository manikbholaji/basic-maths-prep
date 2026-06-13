import os
import sys
import time
import subprocess
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR_LOCAL = os.path.join(str(PROJECT_ROOT), "data", "screenshots")
SCREENSHOT_DIR_ARTIFACT = r"C:\Users\PB915\.gemini\antigravity-cli\brain\eb574654-2ee3-41e3-a35d-87d598307480"

os.makedirs(SCREENSHOT_DIR_LOCAL, exist_ok=True)
os.makedirs(SCREENSHOT_DIR_ARTIFACT, exist_ok=True)

PORT = "8509"
URL = f"http://localhost:{PORT}"

def save_screenshot(page, filename):
    """Saves a screenshot to both the local project folder and the conversation artifact directory."""
    local_path = os.path.join(SCREENSHOT_DIR_LOCAL, filename)
    artifact_path = os.path.join(SCREENSHOT_DIR_ARTIFACT, filename)
    
    # Take screenshot
    page.screenshot(path=local_path)
    
    # Copy to artifact path
    try:
        import shutil
        shutil.copy2(local_path, artifact_path)
    except Exception as e:
        print(f"Error copying to artifact directory: {e}")
        
    print(f"Captured screenshot: {filename}")

def run_automation():
    # Start Streamlit server in a subprocess with MOCK_AI=true to avoid actual LLM latencies/costs
    env = os.environ.copy()
    env["MOCK_AI"] = "true"
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    
    # Ensure local SQLite DB exists
    sys.path.insert(0, str(PROJECT_ROOT))
    from app import db_manager
    db_manager.init_db()
    
    print("Starting Streamlit app locally in the background...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py", 
         "--server.port", PORT, "--server.headless", "true"],
        env=env,
        cwd=str(PROJECT_ROOT)
    )
    
    # Wait for Streamlit server to start up
    server_started = False
    for i in range(30):
        try:
            resp = requests.get(URL, timeout=2)
            if resp.status_code == 200:
                server_started = True
                print("Streamlit app is up and running!")
                break
        except Exception:
            pass
        print("Waiting for server to start...")
        time.sleep(1)
        
    if not server_started:
        print("Error: Streamlit server failed to start.")
        proc.terminate()
        return
        
    # Start Playwright browser interaction
    try:
        with sync_playwright() as p:
            print("Launching headless Chromium browser...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            
            # Capture browser console logs and page errors to debug JS runtime issues
            page.on("console", lambda msg: print(f"[Browser Console] {msg.type}: {msg.text}"))
            page.on("pageerror", lambda err: print(f"[Browser PageError] {err}"))
            
            try:
                # 1. Login Page
                print("Navigating to login page...")
                page.goto(URL, timeout=60000)
                page.wait_for_selector('text="Sign In"', timeout=20000)
                time.sleep(2)
                save_screenshot(page, "1_login_page.png")
                
                # Register a new user dynamically to ensure credentials exist
                print("Registering a new user...")
                page.get_by_role("tab").nth(1).click()
                time.sleep(1)
                
                fullname_input = page.locator('input[type="text"]').nth(1)
                fullname_input.fill("Test Student")
                fullname_input.press("Tab")
                time.sleep(0.5)
                
                reg_username_input = page.locator('input[type="text"]').nth(2)
                reg_username_input.fill("test_automation@example.com")
                reg_username_input.press("Tab")
                time.sleep(0.5)
                
                reg_password_input = page.locator('input[type="password"]').nth(1)
                reg_password_input.fill("password")
                reg_password_input.press("Tab")
                time.sleep(0.5)
                
                page.get_by_role("button", name="Create Account").click()
                time.sleep(2)  # Wait for creation notification
                
                # Switch back to Sign In
                print("Switching back to Sign In tab...")
                page.get_by_role("tab").nth(0).click()
                time.sleep(1)
                
                # Enter credentials and login
                print("Logging in...")
                username_input = page.locator('input[type="text"]').nth(0)
                username_input.fill("test_automation@example.com")
                username_input.press("Tab")
                time.sleep(0.5)
                
                password_input = page.locator('input[type="password"]').nth(0)
                password_input.fill("password")
                password_input.press("Tab")
                time.sleep(0.5)
                
                page.get_by_role("button", name="Sign In").click()
                
                # 2. Main Dashboard
                print("Waiting for dashboard to load...")
                try:
                    page.wait_for_selector('text="Welcome, Test Student!"', timeout=20000)
                except Exception as ex:
                    save_screenshot(page, "login_failure.png")
                    raise ex
                time.sleep(2)
                save_screenshot(page, "2_dashboard_page.png")
                
                # 3. Parametric Quiz Configuration
                print("Configuring parametric quiz...")
                # Click Tab 2
                page.get_by_text("Mode 2: Tailor from Parameters").click()
                time.sleep(1)
                
                # Fill out parameters
                page.get_by_label("Topic / Chapter", exact=False).fill("Coordinate Geometry")
                time.sleep(1)
                save_screenshot(page, "3_quiz_parameters.png")
                
                # 4. Generated Quiz Loading / Start Page
                print("Generating quiz...")
                page.get_by_role("button", name="Generate Parametric Quiz").click()
                
                # Wait for iframe to load (the quiz component)
                print("Waiting for quiz iframe to render...")
                page.wait_for_selector('iframe', timeout=90000)
                time.sleep(3)
                save_screenshot(page, "4_quiz_loaded.png")
                
                # Get iframe context
                iframe_element = page.query_selector('iframe')
                frame = iframe_element.content_frame()
                
                # Enter name and start quiz inside iframe
                print("Starting quiz inside iframe...")
                frame.wait_for_selector('#userNameInput', timeout=10000)
                # Input name
                frame.locator('#userNameInput').fill("Test Student")
                time.sleep(0.5)
                # Click Start Quiz
                frame.evaluate("document.querySelector('.start-button').click()")
                
                # 5. Solving Quiz Questions
                print("Solving Q1-Q10 inside iframe...")
                frame.wait_for_selector('#question1', timeout=10000)
                time.sleep(1)
                print("Total questions in frame:", frame.locator('.question-container').count())
                print("JS questions length:", frame.evaluate("questions.length"))
                save_screenshot(page, "5_quiz_q1.png")
                
                # Solve questions dynamically by checking the question index
                for q in range(1, 11):
                    print(f"Solving Question {q}/10...")
                    # Wait for active question container to be visible
                    active_q_selector = f'#question{q}'
                    frame.wait_for_selector(active_q_selector, timeout=10000)
                    
                    # Log JS state
                    js_current = frame.evaluate("currentQuestion")
                    next_display = frame.evaluate("document.querySelector('.button:nth-of-type(2)').style.display")
                    submit_display = frame.evaluate("document.querySelector('.button:last-of-type').style.display")
                    print(f"[{q}/10] JS currentQuestion={js_current}, Next button display='{next_display}', Submit button display='{submit_display}'")
                    
                    # Select first option in the active question
                    frame.evaluate(f"document.querySelector('#options{q} .option').click()")
                    time.sleep(0.5)
                    
                    if q == 10:
                        print("Question 10 reached. Submitting quiz...")
                        frame.evaluate("document.querySelector('button[onclick=\"submitQuiz()\"]').click()")
                        time.sleep(1)
                    else:
                        print("Advancing to next question...")
                        frame.evaluate("document.querySelector('button[onclick=\"nextQuestion()\"]').click()")
                        time.sleep(0.5)
                        
                # 6. Results Chart Page
                print("Viewing quiz results...")
                frame.wait_for_selector('#resultPage', timeout=10000)
                time.sleep(2)
                save_screenshot(page, "6_quiz_result.png")
                
                # 7. Check Mistakes / Explanations
                print("Reviewing mistakes...")
                frame.evaluate("document.querySelector('button[onclick=\"showPreviousResult()\"]').click()")
                time.sleep(1)
                save_screenshot(page, "7_quiz_mistakes_review.png")
                
                # 8. Dashboard History
                print("Returning to dashboard...")
                # Click button outside the iframe
                page.locator('button:has-text("Back to Dashboard")').click()
                page.wait_for_selector('h2:has-text("Your Quiz History")', timeout=20000)
                time.sleep(2)
                save_screenshot(page, "8_dashboard_history.png")
                
                print("All screenshots successfully captured!")
            except Exception as e:
                try:
                    save_screenshot(page, "error_failure.png")
                except Exception as se:
                    print(f"Failed to capture error screenshot: {se}")
                raise e
            finally:
                browser.close()
                
    except Exception as e:
        safe_msg = str(e).encode('ascii', 'ignore').decode('ascii')
        print(f"Automation execution error: {safe_msg}")
        import traceback
        traceback.print_exc()
    finally:
        # Shutdown Streamlit server
        print("Shutting down local Streamlit app server...")
        proc.terminate()
        proc.wait()
        print("Server shutdown complete.")

if __name__ == '__main__':
    run_automation()
