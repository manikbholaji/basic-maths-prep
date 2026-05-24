Title: axe-core accessibility violations in Streamlit app shell (aria-expanded on sidebar, landmark/heading issues)

Summary

When running axe-core against a Streamlit app, axe reports a small number of accessibility violations that appear to originate from Streamlit's generated DOM (app shell and BaseWeb widgets). These include:

- `aria-allowed-attr` (critical): `aria-expanded="true"` on `.stSidebar` <section> nodes.
- `heading-order` (moderate): `#recommendations` rendered as an `h3` in a context that violates heading order checks.
- `region` (moderate): some content not contained by landmarks (no top-level `main` landmark wrapping app content).

These problems make axe fail even when the app's own content uses correct semantics. I have a minimal workaround (DOM sanitization JS) that makes the axe violations go away when applied in the page, but it is brittle and relies on reapplying fixes after Streamlit re-renders. A framework-level fix would be preferable.

Reproduction

1. Run this repository's demo app locally (example):

```bash
# from repo root
pip install -r requirements.txt
streamlit run app/basic_maths_app.py
```

2. Visit http://localhost:8505/ and wait for the app to stabilise.
3. Inject axe and run a scan (example Node/Playwright):

```js
await page.addScriptTag({ url: 'https://unpkg.com/axe-core@4.6.3/axe.min.js' });
const result = await page.evaluate(() => axe.run());
console.log('violations', result.violations.map(v => v.id));
```

Observed axe violations (excerpt from my run)

- aria-allowed-attr: critical — target: `.stSidebar` — html: `<section class="stSidebar" aria-expanded="true">` — message: "ARIA attribute is not allowed: aria-expanded=\"true\""
- heading-order: moderate — target: `#recommendations` — html: `<h3 id="recommendations">...` — message: heading order issues
- region: moderate — many `.stElementContainer` nodes reported as not contained by landmarks

Temporary, minimal in-page fix that clears the violations

The following snippet, when executed in the page context before running axe, removes the reported violations (proof of cause). This is brittle and needs to run early and after re-renders.

```js
// run in page context
[...document.querySelectorAll('.stSidebar')].forEach(s=>s.removeAttribute('aria-expanded'));
const rec = document.getElementById('recommendations');
if(rec && rec.tagName.toLowerCase()==='h3'){
  const h2 = document.createElement('h2'); h2.id = rec.id; h2.innerHTML = rec.innerHTML; rec.parentNode.replaceChild(h2, rec);
}
if(!document.querySelector('main[role="main"]')){
  const app = document.querySelector('.stApp') || document.querySelector('[data-testid="stAppViewContainer"]') || document.querySelector('#root');
  if(app){ const m=document.createElement('main'); m.setAttribute('role','main'); app.parentNode.replaceChild(m, app); m.appendChild(app); }
}
```

Suggested framework fixes (Streamlit)

1. Avoid adding `aria-expanded` on non-interactive section elements. If a sidebar needs to reflect expanded/collapsed state, ensure the element with `aria-expanded` is an interactive control (e.g. a button) or use an appropriate widget container with allowed ARIA attributes.
2. Ensure the app shell provides a landmark structure (`header`, `main`, `nav`, `footer`) so that app content is contained within `main` and user content is not flagged as outside landmarks.
3. Normalize heading semantics for the built-in components (or ensure they render headings with levels that maintain heading order). Use semantic heading levels or allow app authors to control heading levels.

Why this matters

- axe failures block CI and make it hard to assert accessibility in tests when the app's own content meets standards.
- In-app workarounds are brittle because Streamlit re-renders DOM and reintroduces attributes.

Attachments / logs

- I can attach the full axe JSON output and a small Playwright script that reproduces the scan. If helpful I can open a PR or issue with a minimal reproducible example that demonstrates the fix.

Contact

Maintainer: (I can open the issue from the project if desired) — I recommend adding a small Streamlit-side fix for the sidebar/landmark behavior, or guidance in the docs about accessible sidebar implementations.
