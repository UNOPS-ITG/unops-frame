# Agent browser

A headless Playwright harness for driving the app locally without going
through the interactive oauth2-proxy / Google OAuth flow — built so an AI
agent (or any headless script) can exercise the real app against the real
dev Firestore, authenticated as a real UNOPS user, with no browser popups
or human-in-the-loop login.

## Why this exists

Normal local dev (`npm run dev`) authenticates through `oauth2-proxy` at
`localhost:4180`, which drives an interactive Google OAuth consent screen
(see `../../LOCAL-RUN-GUIDANCE.md`). A headless browser can't click through
that. Hitting `localhost:4200` directly instead just bounces between `/` and
`/login` forever, because `checkIAPAuth()` fails without the headers
oauth2-proxy would have injected.

This harness sidesteps both problems by intercepting same-origin `/api/**`
requests at the browser-network layer (`route.continue()` with a rewritten
URL — the request stays on the normal network stack, so SSE/streaming
responses still stream; only same-origin requests are touched, so no
third-party URL ever sees the secret) and re-targeting them directly at the
FastAPI backend (`localhost:8000`), attaching an `x-dev-auth-bypass` header. The
backend's `DevAuthBypassMiddleware`
(`functions/api/middleware/dev_auth_bypass_middleware.py`) accepts that
header **only** when `DEV_AUTH_BYPASS_SECRET` is set in the (gitignored)
`functions/config/.env` — never in any deployed environment — and treats the
request as authenticated as a real user (`DEV_AUTH_BYPASS_EMAIL`, or
whichever email is sent via `x-dev-auth-email`). Firestore/business logic
then runs exactly as it would for that user's real IAP session, using the
backend's already-configured real service-account credentials — this is not
a mock backend or the Firebase emulator, it's the real dev environment.

This also means oauth2-proxy doesn't even need to be running for headless
testing — only `dev:be` (backend, port 8000) and `dev:fe` (vite, port 4200).

**This bypass cannot activate outside a bare local `uvicorn` process** —
`DevAuthBypassMiddleware` is only registered when `DEV_AUTH_BYPASS_SECRET` is
set *and* the process is not Cloud Run/Firebase Functions. Never commit a
real secret value or set this in any `functions/.env.<project>` deployment
config.

## Setup (one-time)

1. Generate a secret and add it to `functions/config/.env` (already done if
   you're reading this after the initial setup):
   ```
   DEV_AUTH_BYPASS_SECRET=<random string>
   DEV_AUTH_BYPASS_EMAIL=<your real UNOPS email>
   ```
   Restart/reload the backend (`npm run dev:be`, or it'll pick it up via the
   uvicorn `--reload` watch on `config/`) so the middleware registers.
2. Copy `.env.local.example` to `.env.local` in this directory and paste in
   the same secret + email.

## Usage

```bash
node scripts/agent-browser/browser.mjs '[
  {"action":"goto","params":{"url":"/"}},
  {"action":"wait","params":{"ms":1500}},
  {"action":"screenshot"},
  {"action":"console"}
]'
# or, to dodge shell-quoting (recommended for long batches / PowerShell):
node scripts/agent-browser/browser.mjs path/to/steps.json
```

Pass a JSON array of steps (inline, or as a path to a JSON file); each runs
against a single persistent browser context (profile stored in the gitignored
`.browser-profile/`, so non-auth state survives between invocations) and
results print as JSON. The process exits after the batch — this is a
run-a-batch-then-exit tool, not a long-lived server (see "Why one-shot, not
a persistent server" below). Run **one batch at a time**: the persistent
profile takes an exclusive lock, so a second concurrent invocation fails.
A watchdog force-exits (with partial results) if a batch exceeds 90s —
override with the `AGENT_BROWSER_TIMEOUT_MS` env var.

### Steps

| action | params | returns |
|---|---|---|
| `goto` | `url` (relative or absolute), `waitUntil`, `timeout` | `{url, title}` |
| `status` | — | `{url, title}` |
| `screenshot` | `path` (relative to `.output/`, or absolute), `full` (default **true** — whole document; pass `false` for viewport only), `expand` (bool — neutralize inner-scroll containers so clipped panels flow into the page), `noScroll` (bool — skip the pre-shot scroll-through) | `{path}` |
| `screenshotScroll` | `path`, `selector` (scroll container; auto-picks tallest if omitted), `settle` | `{paths, segments}` — one viewport shot per scroll step, saved `<base>-01.png`, `-02.png`, … for inner-scroll panels a single shot can't cover |
| `scrollThrough` | `selector` (optional), `settle` | `{ok}` — scroll top→bottom→top to trigger lazy/virtualized content |
| `scrollElement` | `selector`, | `{ok}` — scroll a specific inner container to its end (e.g. a Terms box that gates a checkbox) |
| `resize` | `width`, `height` | `{ok}` — change viewport. A tall viewport (e.g. 1400×2800) makes fixed-height (100vh) editor/modal layouts expand their scrollable body so one full-page shot captures everything. Resize back to 1400×900 after. |
| `text` | `selector` (default `body`) | `{text}` |
| `html` | — | `{html}` |
| `click` | `selector`, `timeout` | `{ok}` |
| `clickText` | `text`, `contains` (bool, substring match), `tag` (CSS to scope) | `{ok}` — clicks first VISIBLE element matching the text; use this when duplicate/responsive elements make `click` strict-mode-fail |
| `fill` | `selector`, `text`, `timeout` | `{ok}` |
| `press` | `key` | `{ok}` |
| `hover` | `selector`, `timeout` | `{ok}` |
| `check` | `selector`, `checked` (default true), `timeout` | `{ok}` |
| `selectOption` | `selector`, `value`, `timeout` | `{selected}` |
| `upload` | `selector`, `files` (path(s) relative to repo root), `timeout` | `{ok}` |
| `eval` | `code` (JS **expression** string — it's wrapped in `return (...)`) | `{result}` |
| `wait` | `ms` | `{ok}` |
| `waitForSelector` | `selector`, `timeout`, `state` | `{ok}` |
| `console` | `limit` (default 200) | `{logs}` — everything logged during this run |
| `network` | `limit` (default 100) | `{requests}` — every `/api` request this run: method, path, and status (a number, `"pending"`, or `"failed: <reason>"`) |

`url` for `goto` may be relative (`"/cases"`) — it's resolved against
`FRONTEND_URL` (default `http://localhost:4200`).

**Expect slow first loads.** Some dev-backend endpoints (e.g.
`/api/v1/case-types`) take 7–9 seconds locally, so pages sit on loading
skeletons well past `domcontentloaded`. Prefer `waitForSelector` on real
content over fixed `wait`s, and when data looks missing check `network`
for `"pending"` entries before concluding something is broken.

**Capturing full content of tall editors/modals.** Many editor and modal
bodies scroll *inside* a fixed-height (100vh) shell, so a plain full-page shot
clips them at the fold. Best fix: `resize` to a tall viewport (e.g. 1400×2800)
before the shot — the flex-scrollable body grows to fit and one full-page
capture gets everything. Fallbacks: `screenshot` with `expand:true`, or
`screenshotScroll` for segmented capture.

**Clicking: DOM vs real events.** `clickText` clicks via DOM `.click()`, which
works for most buttons and correctly ignores off-screen/duplicate copies. But
some elements only respond to a *real* pointer event (React handlers on
non-button elements, e.g. a collapsed side-rail) — for those use the `click`
action (real Playwright click) with a `text=…` or CSS selector. Native
`<select>`s and toggle-switches can't be driven by text; target the element.

## Why one-shot, not a persistent server

An earlier version tried to keep one browser process running in the
background and control it via a second process (WebSocket/CDP, then a plain
HTTP control server). Both failed in this sandboxed environment: raw
WebSocket connections to `localhost` hang indefinitely (even to Chrome's own
CDP port) and arbitrary listening TCP ports are unreachable from other
processes — only a few known ports (e.g. the dev server, Chrome's `9222`)
get through. A single process launching Playwright, running its steps
in-process, and exiting sidesteps both issues entirely — no IPC needed.

Headless mode isn't a preference either — it's required. This runs without
an interactive desktop session, so a `headless: false` Chromium window never
actually paints; DOM-level calls (`title`, `eval`) still resolve, but
anything needing a real compositor frame (`screenshot`) hangs until timeout.

## Relationship to `e2e/` and `npm run e2e*`

That is a separate, CI-oriented Playwright suite that runs against the
**Firebase Auth/Firestore emulators** (fake users, fake data — see
`e2e/README.md`). This harness is for interactive, exploratory testing
against the **real dev environment** as a real user. Don't seed test data
here or point CI at this — use `npm run e2e` for regression coverage.
