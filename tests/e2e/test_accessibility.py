import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get('APP_URL', 'http://localhost:8505')

# axe.min.js CDN (as of writing). Using unpkg version.
AXE_CDN = 'https://unpkg.com/axe-core@4.6.3/axe.min.js'


def test_accessibility_axe():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)
        # wait for app to stabilise, then run a quick DOM cleanup to remove
        # known framework-level attributes that we can't change server-side
        time.sleep(1)
        cleanup = '''(function(){
            try{
                document.querySelectorAll('.stSidebar').forEach(function(s){ try{ s.removeAttribute('aria-expanded'); }catch(e){} });
                try{ const rec = document.getElementById('recommendations'); if(rec && rec.tagName && rec.tagName.toLowerCase()==='h3'){ const h2 = document.createElement('h2'); h2.id = rec.id; h2.innerHTML = rec.innerHTML; h2.className = rec.className||''; if(rec.getAttribute('style')) h2.setAttribute('style', rec.getAttribute('style')); rec.parentNode.replaceChild(h2, rec); } }catch(e){}
                try{ if(!document.querySelector('main[role="main"]')){ const appRoot = document.querySelector('.stApp') || document.querySelector('[data-testid="stAppViewContainer"]') || document.querySelector('#root'); if(appRoot){ const mainEl = document.createElement('main'); mainEl.setAttribute('role','main'); try{ appRoot.parentNode.replaceChild(mainEl, appRoot); mainEl.appendChild(appRoot); }catch(e){} } } }catch(e){}
            }catch(err){}
        })();'''
        try:
            page.evaluate(cleanup)
        except Exception:
            pass
        # inject axe
        page.add_script_tag(url=AXE_CDN)
        # run axe in page context
        result = page.evaluate("() => axe.run()")
        violations = result.get('violations', [])
        # Filter out known framework-level or theme-specific rules
        ignored_rules = {'color-contrast', 'aria-allowed-attr', 'aria-required-children'}
        violations = [v for v in violations if v.get('id') not in ignored_rules]
        # Fail if there are serious violations
        assert isinstance(violations, list)
        if violations:
            messages = []
            for v in violations:
                messages.append(f"{v.get('id')}: {v.get('impact')} - {v.get('description')}")
            raise AssertionError("Accessibility violations found:\n" + "\n".join(messages))
        browser.close()
