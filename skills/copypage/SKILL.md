---
name: copypage
description: "Faithfully recreate any web page from screenshots, live browser access, or user-provided page source code, to produce an HTML prototype for continuous optimization, A/B testing, or user research."
---

# Copypage

Recreate an existing web page as a single self-contained HTML prototype, based on screenshots, source code, and/or live browser access via Claude in Chrome.

## Process

### Step 1 — Get input

Ask the user which input(s) they can provide, since combining sources gives the best result:

- **Screenshots** of the page (default option, always works).
- **Source code**: the user can give the page's HTML/CSS/JS directly — e.g. via "View Page Source" (Ctrl+U / Cmd+Option+U), "Save Page As" in the browser, browser DevTools ("Elements" panel copy-as-HTML), or by pasting a code snippet/file. This is the most reliable input when available, since it removes guesswork on markup, exact class names, and styling values.
- **Live browser access** via Claude in Chrome, if connected (see Step 2bis).

If the user only has screenshots, proceed with those. If they can also paste or upload source code, ask for it — it substantially improves fidelity. If no input is available yet, ask the user to provide at least one of the above (screenshots being the easiest to get).

### Step 2 — Analyze the input

If working from screenshots, study them to extract:

- **Layout & grid**: structure, breakpoints, spacing system
- **Typography**: fonts, sizes, weights, line-heights
- **Colors**: palette, gradients, states (hover/active/disabled)
- **Components**: buttons, cards, forms, navigation bars, etc.
- **Visible states**: default, hover, focus, error, loading
- **Responsiveness**: how the layout adapts across viewport sizes
- **Navigation behaviors**: identify all navigation elements and interactions visible on the page — links, menus, tabs, modals, accordions, scroll/hover/click-triggered interactions, page or view transitions.

If the user has provided source code (HTML/CSS/JS, a saved page, or a pasted snippet), read it directly instead of guessing from pixels:

- Extract the actual DOM structure, class names, CSS rules, and JS behavior where present.
- Note any assets referenced (images, fonts, icons) that aren't included — treat these as placeholders unless the user supplies them too.
- Watch for minified/bundled code, framework-generated markup (React/Vue hydration artifacts), or code that only represents part of the page (e.g. a single component) — flag these limitations to the user.
- Cross-check the source against any screenshots provided, since rendered output (via CSS frameworks, JS-driven state, or server-side templating) can differ from the raw markup.

### Step 2bis — (Optional) Inspect the live page with Claude in Chrome

If Claude in Chrome is connected, go beyond screenshots and gather structural/behavioral data directly from the browser. Use whichever of these fits the need:

- **`javascript_tool`**: execute JS in the page context to read `document.documentElement.outerHTML`, inspect computed styles (`getComputedStyle`), or read exposed JS state (e.g. a framework's global state object).
- **`read_page`**: pull the accessibility tree to get a structured list of interactive elements (buttons, links, inputs, ARIA roles) — useful for confirming navigation behaviors identified in Step 2.
- **`read_network_requests`**: inspect XHR/Fetch calls triggered by the page to understand any dynamic data loading behind navigation or interactions.

Note: this does not give access to the original server-side source code or unminified JS bundles — only what's observable in the live, rendered page. This is why user-provided source code (Step 1) is worth asking for even when Claude in Chrome is available.

### Step 3 — Generate the HTML prototype

Produce a single self-contained HTML file (HTML, CSS, and JavaScript inline) that matches the original design as closely as possible.

- Prefer fidelity to the actual source code over visual guesswork wherever source code is available; fall back to screenshot-based inference for anything the source doesn't cover.
- Use placeholders when content is hidden or cannot be inferred.
- Do not invent features that are not visible or evidenced by inspection.
- Briefly list any assumptions made, and note which parts came from source code vs. visual inference.
