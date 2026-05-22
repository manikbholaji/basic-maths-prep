from playwright.sync_api import sync_playwright
import os
import time

VIDEO_DIR = 'demos/videos'
URL = 'https://academicadvisor.streamlit.app/'


def record_demo(output_name='admin_chat_demo'):
    os.makedirs(VIDEO_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(record_video_dir=VIDEO_DIR, record_video_size={"width": 1280, "height": 720})
        page = context.new_page()
        page.goto(URL, timeout=60000)

        # Wait for embedded Streamlit app iframe and get its frame
        page.wait_for_selector('iframe[title="streamlitApp"]', timeout=60000)
        iframe_elem = page.query_selector('iframe[title="streamlitApp"]')
        app_frame = iframe_elem.content_frame()

        # Admin flow: open Admin tab, choose a field, and build pathway
        app_frame.wait_for_selector('text="Admin"', timeout=60000)
        app_frame.click('text="Admin"')
        app_frame.wait_for_selector('text="🎯 Pathway Advisor Configuration"', timeout=60000)

        # Attempt to select a field option; try a few known options (safe clicks)
        try:
            app_frame.click('text="Humanities / Psychology / Public Policy"')
        except Exception:
            try:
                app_frame.click('text="Engineering / Computer Science"')
            except Exception:
                pass

        # Click Build Complete Pathway
        app_frame.wait_for_selector('button:has-text("Build Complete Pathway")', timeout=60000)
        app_frame.click('button:has-text("Build Complete Pathway")')

        # Wait for results to appear
        app_frame.wait_for_selector('text=/Recommended Pathways/', timeout=60000)

        # Brief pause to capture the expanded results in the video
        time.sleep(3)

        # Optionally go to Chat tab (visual coverage)
        try:
            app_frame.click('text="Chat"')
        except Exception:
            # If navigation can't be clicked inside iframe, click the top-level navigation
            try:
                page.click('text="Chat"')
            except Exception:
                pass

        # Let the video record a couple more seconds
        time.sleep(2)

        # Close context to finalize video file
        context.close()
        browser.close()

    # Find the produced video file (Playwright writes to record_video_dir with random name)
    files = os.listdir(VIDEO_DIR)
    webm_files = [f for f in files if f.endswith('.webm')]
    if not webm_files:
        print('No video file found in', VIDEO_DIR)
        return None

    # Pick the most recent file
    webm_files = sorted(webm_files, key=lambda fn: os.path.getmtime(os.path.join(VIDEO_DIR, fn)))
    src = os.path.join(VIDEO_DIR, webm_files[-1])
    dst = os.path.join(VIDEO_DIR, f"{output_name}.webm")
    try:
        os.replace(src, dst)
    except Exception:
        dst = src

    print('Video recorded to:', dst)
    print('\nTo convert to GIF (optional):')
    print('ffmpeg -i', dst, '-vf "fps=10,scale=640:-1:flags=lanczos" demos/admin_demo.gif')
    return dst


if __name__ == '__main__':
    record_demo()
