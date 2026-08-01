---
name: browser-test
description: Drive the running UNOPS AI Playbook app in a real headless browser (Playwright) against the real dev Firestore, authenticated as the real user — no OAuth popups, no emulators. Use this whenever you need to look at, click through, or verify the actual running app rather than just reading code.
---

Use this skill to actually operate the app — navigate pages, click buttons,
fill forms, read rendered text, take screenshots, check browser console
errors — instead of only reasoning about source code.

## Prerequisites

The dev stack must be running: `npm run dev` (starts backend on :8000, vite
on :4200, oauth2-proxy on :4180 — oauth2-proxy itself isn't needed for this
skill but is harmless to leave running). If it's not running, start it in
the background yourself (`npm run dev`, `run_in_background: true`) — it's a
safe, reversible local action — and wait ~10s for `Application startup
complete` from the backend before driving the browser.

Also requires `scripts/agent-browser/.env.local` to exist (copy from
`.env.local.example` and fill in `DEV_AUTH_BYPASS_SECRET` from
`functions/config/.env` if it's missing). If neither file has the secret,
see "First-time setup" below.

## Running it

```bash
node scripts/agent-browser/browser.mjs '<JSON array of steps>'
```

Run it from the repo root (or pass the full path to `browser.mjs` — Node
resolves `playwright` relative to the script's own location, so this works
from any cwd).

The argument is either inline JSON or a path to a JSON file of steps —
prefer the file for long batches (write it with the Write tool first);
it avoids shell-quoting pain entirely. `npm run agent:browser -- '<json>'`
also works.

Each invocation launches a fresh (but persistent-profile) headless browser,
runs the steps in order, prints JSON results, and exits — it does not stay
running. Batch everything you need for one logical check into a single
call rather than invoking once per action, and run only ONE invocation at
a time (the profile is lock-protected; concurrent runs fail). A watchdog
kills a hung batch at 90s with partial results (`AGENT_BROWSER_TIMEOUT_MS`
to override).

Full step vocabulary and design rationale: `scripts/agent-browser/README.md`.
Quick reference: `goto`, `status`, `screenshot` (full-page by default;
`expand:true` to unclip inner-scroll panels), `screenshotScroll` (segmented
capture), `resize` (tall viewport for full editor/modal capture), `text`,
`html`, `click`, `clickText` (click visible element by text), `fill`, `press`,
`hover`, `check`, `selectOption`, `upload`, `eval` (a JS expression), `wait`,
`waitForSelector`, `scrollThrough`, `scrollElement`, `console`, `network`.

For a full-content shot of a tall editor/modal (design review), `resize` to
~1400×2800 first, then screenshot — one shot captures the whole form instead of
clipping it at the fold. Use the `click` action (real Playwright pointer event)
for elements `clickText` can't drive (side-rails, switches, native selects).

Example — load the dashboard and check for errors:
```bash
node scripts/agent-browser/browser.mjs '[
  {"action":"goto","params":{"url":"/"}},
  {"action":"wait","params":{"ms":2000}},
  {"action":"screenshot"},
  {"action":"console"},
  {"action":"network"}
]'
```
Screenshots land in `scripts/agent-browser/.output/` — Read the PNG after
the call to actually look at it.

Two operational lessons baked in from real use:
- **Slow dev endpoints are normal.** Some backend endpoints take 7–9s
  locally (e.g. case-types), so pages show loading skeletons long after
  `goto` returns. Use `waitForSelector` on real content (or a generous
  `wait`), and before concluding a data fetch is broken, run `network` —
  it lists every `/api` call with status `"pending"` / `"failed: …"` /
  HTTP code, so a slow request is distinguishable from a missing one.
- A first-run onboarding dialog ("Welcome to UNOPS AI Playbook!") may
  cover the app; dismiss with `{"action":"click","params":{"selector":"text=Skip for now"}}`.
  The persistent profile remembers the dismissal.

## Why this works without interactive login

Normal local dev requires clicking through a real Google OAuth screen via
oauth2-proxy (:4180) — impossible for a headless script. This harness
instead intercepts `/api/**` calls in the browser and re-issues them
directly to the backend (:8000) with an `x-dev-auth-bypass` header that the
backend's `DevAuthBypassMiddleware` accepts *only* in local dev, treating
the request as the real configured user. Firestore access is real — same
dev database, same service-account credentials the backend always uses.
Full details: `scripts/agent-browser/README.md`.

Headless is required, not optional, in this environment: a headed browser
never paints (no interactive desktop session) and hangs on anything needing
a rendered frame. Don't try `headless: false`.

## First-time setup (only if `.env.local`/secret is missing)

1. Generate a secret and add to `functions/config/.env`:
   ```
   DEV_AUTH_BYPASS_SECRET=<openssl rand -hex 24, or similar>
   DEV_AUTH_BYPASS_EMAIL=<the real UNOPS email to authenticate as>
   ```
2. Restart the backend (or let uvicorn's `--reload` picked it up — it
   watches `functions/config/`) and confirm the startup log shows
   `DevAuthBypassMiddleware ACTIVE`.
3. Copy `scripts/agent-browser/.env.local.example` to
   `scripts/agent-browser/.env.local` with the same secret + email.

Never put `DEV_AUTH_BYPASS_SECRET` in any deployed environment's config —
see the warnings in `dev_auth_bypass_middleware.py` and
`LOCAL-RUN-GUIDANCE.md`.
