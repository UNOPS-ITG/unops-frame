#!/usr/bin/env node
/**
 * Headless Playwright runner for driving the app locally without the
 * interactive oauth2-proxy / Google OAuth flow.
 *
 * Runs one batch of steps against a persistent browser profile (so
 * non-auth state — theme, localStorage, etc. — survives between calls),
 * then exits. See README.md in this directory for the auth story and the
 * full step vocabulary.
 *
 * Usage:
 *   node scripts/agent-browser/browser.mjs '[{"action":"goto","params":{"url":"/"}},{"action":"screenshot"}]'
 *   node scripts/agent-browser/browser.mjs path/to/steps.json
 */
import { chromium } from 'playwright';
import { readFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
// Frame runs on its own port block so it never collides with the sibling
// projects that own the estate defaults. See config/ports.json.
import { urls as framePorts } from '../../config/ports.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROFILE_DIR = join(__dirname, '.browser-profile');
const OUTPUT_DIR = join(__dirname, '.output');
const DEFAULT_SCREENSHOT_PATH = join(OUTPUT_DIR, 'screenshot.png');

// Hard ceiling for the whole batch so a hung step (dead dev server, selector
// that never appears) can't stall the process past the caller's patience.
// Partial results are printed before exiting.
const WATCHDOG_MS = Number(process.env.AGENT_BROWSER_TIMEOUT_MS || 90_000);

function loadLocalEnv() {
  const path = join(__dirname, '.env.local');
  const env = {};
  if (existsSync(path)) {
    for (const line of readFileSync(path, 'utf8').split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const eq = trimmed.indexOf('=');
      if (eq === -1) continue;
      env[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1).trim();
    }
  }
  return env;
}

const localEnv = loadLocalEnv();
const config = {
  frontendUrl: process.env.AGENT_BROWSER_FRONTEND_URL || localEnv.FRONTEND_URL || framePorts.frontend,
  backendUrl: process.env.AGENT_BROWSER_BACKEND_URL || localEnv.BACKEND_URL || framePorts.backend,
  devBypassSecret: process.env.AGENT_BROWSER_DEV_AUTH_BYPASS_SECRET || localEnv.DEV_AUTH_BYPASS_SECRET || null,
  devBypassEmail: process.env.AGENT_BROWSER_DEV_AUTH_BYPASS_EMAIL || localEnv.DEV_AUTH_BYPASS_EMAIL || null,
};

function resolveUrl(url) {
  if (/^https?:\/\//.test(url)) return url;
  return config.frontendUrl.replace(/\/$/, '') + '/' + url.replace(/^\//, '');
}

/** Re-target same-origin /api/** requests at the FastAPI backend, attaching
 * the local dev auth-bypass headers. Uses route.continue() (not fetch +
 * fulfill) so the request stays on the normal network stack — response
 * STREAMING (the app's SSE endpoints via fetch-event-source) is preserved,
 * which fulfill() would break by buffering the whole body. Scoped to the
 * frontend origin so third-party URLs that happen to contain /api/ are
 * never rerouted or handed the secret. */
async function installApiBypass(context) {
  if (!config.devBypassSecret) {
    console.error('[agent-browser] WARNING: no DEV_AUTH_BYPASS_SECRET configured — /api calls will be unauthenticated. See README.md.');
    return;
  }
  const frontendOrigin = new URL(config.frontendUrl).origin;
  const backendBase = config.backendUrl.replace(/\/$/, '');
  await context.route(
    (url) => url.origin === frontendOrigin && url.pathname.startsWith('/api/'),
    async (route) => {
      const req = route.request();
      const reqUrl = new URL(req.url());
      await route.continue({
        url: backendBase + reqUrl.pathname + reqUrl.search,
        headers: {
          ...req.headers(),
          host: new URL(config.backendUrl).host,
          'x-dev-auth-bypass': config.devBypassSecret,
          ...(config.devBypassEmail ? { 'x-dev-auth-email': config.devBypassEmail } : {}),
        },
      });
    }
  );
}

/** Local browsers can't PUT to GCS signed URLs — the dev bucket has no CORS
 * config for the Frame dev origin, so the browser's preflight fails and
 * upload flows die at the direct-to-GCS step. Proxy those requests through
 * Node (no CORS there): answer the preflight ourselves, re-issue the PUT
 * verbatim with fetch, and hand the real GCS response back to the page. */
async function installGcsUploadProxy(context) {
  await context.route(
    (url) => url.hostname === 'storage.googleapis.com',
    async (route) => {
      const req = route.request();
      if (req.method() === 'OPTIONS') {
        await route.fulfill({
          status: 204,
          headers: {
            'access-control-allow-origin': '*',
            'access-control-allow-methods': 'PUT,GET,POST,OPTIONS',
            'access-control-allow-headers': '*',
          },
        });
        return;
      }
      try {
        const resp = await fetch(req.url(), {
          method: req.method(),
          headers: { 'content-type': req.headers()['content-type'] || 'application/octet-stream' },
          body: req.postDataBuffer() ?? undefined,
        });
        await route.fulfill({
          status: resp.status,
          headers: { 'access-control-allow-origin': '*' },
          body: Buffer.from(await resp.arrayBuffer()),
        });
      } catch (e) {
        await route.abort('failed');
      }
    }
  );
}

/** Scroll the page (or the nearest scroll container of `selector`) from top to
 * bottom in viewport-sized steps, pausing briefly at each so lazy/virtualized
 * content and intersection-observer reveals render, then return to the top.
 * This is what makes full-page screenshots actually complete. */
async function scrollThroughPage(page, settleMs, selector) {
  await page.evaluate(async ({ settle, selector }) => {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    let scroller = document.scrollingElement || document.documentElement;
    if (selector) {
      const el = document.querySelector(selector);
      if (el) {
        // Walk up to the nearest actually-scrollable ancestor.
        let n = el;
        while (n && n !== document.body) {
          const s = getComputedStyle(n);
          if (/(auto|scroll)/.test(s.overflowY) && n.scrollHeight > n.clientHeight) { scroller = n; break; }
          n = n.parentElement;
        }
      }
    }
    const step = Math.max(200, scroller.clientHeight - 100);
    const max = scroller.scrollHeight;
    for (let y = 0; y < max; y += step) {
      scroller.scrollTo(0, y);
      await sleep(settle || 250);
    }
    scroller.scrollTo(0, max);
    await sleep(settle || 250);
    scroller.scrollTo(0, 0);
    await sleep(150);
  }, { settle: settleMs, selector });
}

async function runAction(page, step, collected) {
  const { action, params = {} } = step;
  switch (action) {
    case 'console':
      return { logs: collected.consoleLogs.slice(-(params.limit || 200)) };
    case 'network':
      // /api requests observed during this run: method, path, and status —
      // including still-pending and failed ones, so slow endpoints (some dev
      // endpoints take ~8s) and connection errors are visible, not silently
      // absent.
      return { requests: [...collected.apiRequests.values()].slice(-(params.limit || 100)) };
    case 'goto': {
      await page.goto(resolveUrl(params.url), { waitUntil: params.waitUntil || 'domcontentloaded', timeout: params.timeout || 30000 });
      return { url: page.url(), title: await page.title() };
    }
    case 'status':
      return { url: page.url(), title: await page.title() };
    case 'screenshot': {
      // Relative paths land in .output/; absolute paths are honored as-is
      // (e.g. for route-organized captures under the repo's screenshots/).
      const path = params.path
        ? (isAbsolute(params.path) ? params.path : join(OUTPUT_DIR, params.path))
        : DEFAULT_SCREENSHOT_PATH;
      mkdirSync(dirname(path), { recursive: true });
      // Default to full-page: for a design/UX review we almost always want the
      // whole scrollable document, not just the viewport. Pass full:false to
      // force a viewport-only shot. When full-page, first scroll the document
      // top→bottom→top so lazy/virtualized/intersection-observer content
      // actually renders before the capture.
      const full = params.full !== false;
      // expand: neutralize inner-scroll containers so content that normally
      // scrolls inside a fixed-height panel (editor bodies, modal bodies,
      // between a sticky header/footer) flows into the document and is fully
      // captured by fullPage. Essential for design review of long editors.
      let restore = null;
      if (params.expand) {
        restore = await page.evaluate(() => {
          const changed = [];
          for (const el of document.querySelectorAll('*')) {
            const s = getComputedStyle(el);
            const scrolls = /(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 4;
            const capped = s.maxHeight !== 'none' && el.scrollHeight > el.clientHeight + 4;
            if (scrolls || capped) {
              changed.push({ el, o: el.style.overflow, oy: el.style.overflowY, mh: el.style.maxHeight, h: el.style.height });
              el.style.overflow = 'visible';
              el.style.overflowY = 'visible';
              el.style.maxHeight = 'none';
              el.style.height = 'auto';
            }
          }
          // Stash on window so a follow-up call can restore (keeps DOM refs alive).
          window.__agentExpandRestore = changed;
          return changed.length;
        });
      }
      if (full && params.noScroll !== true) await scrollThroughPage(page, params.settle);
      await page.screenshot({ path, fullPage: full });
      if (params.expand) {
        await page.evaluate(() => {
          for (const c of (window.__agentExpandRestore || [])) {
            c.el.style.overflow = c.o; c.el.style.overflowY = c.oy;
            c.el.style.maxHeight = c.mh; c.el.style.height = c.h;
          }
          window.__agentExpandRestore = null;
        });
      }
      return { path, expanded: restore };
    }
    case 'screenshotScroll': {
      // Segmented capture of an inner-scroll container (editor bodies, modal
      // bodies) that fixed-height layouts prevent fullPage from capturing.
      // Scrolls the container top→bottom in ~viewport steps, saving one
      // viewport screenshot per step as <base>-01.png, <base>-02.png, …
      const base = params.path
        ? (isAbsolute(params.path) ? params.path : join(OUTPUT_DIR, params.path))
        : DEFAULT_SCREENSHOT_PATH;
      mkdirSync(dirname(base), { recursive: true });
      const info = await page.evaluate((selector) => {
        let el = selector ? document.querySelector(selector) : null;
        if (!el) {
          // Auto-pick the tallest scrollable container.
          let best = null, bestH = 0;
          for (const n of document.querySelectorAll('*')) {
            const s = getComputedStyle(n);
            if (/(auto|scroll)/.test(s.overflowY) && n.scrollHeight > n.clientHeight + 8 && n.scrollHeight > bestH) { best = n; bestH = n.scrollHeight; }
          }
          el = best;
        }
        if (!el) return null;
        el.scrollTop = 0;
        window.__agentScrollEl = el;
        return { sh: el.scrollHeight, ch: el.clientHeight };
      }, params.selector);
      if (!info) throw new Error('screenshotScroll: no scroll container found');
      const step = Math.max(200, info.ch - 80);
      const n = Math.max(1, Math.ceil(info.sh / step));
      const paths = [];
      const dot = base.lastIndexOf('.');
      const stem = dot === -1 ? base : base.slice(0, dot);
      const ext = dot === -1 ? '.png' : base.slice(dot);
      for (let i = 0; i < n; i++) {
        await page.evaluate(({ selector, y }) => {
          let el = selector ? document.querySelector(selector) : window.__agentScrollEl;
          if (el) el.scrollTop = y;
        }, { selector: params.selector, y: i * step });
        await page.waitForTimeout(params.settle || 350);
        const p = `${stem}-${String(i + 1).padStart(2, '0')}${ext}`;
        await page.screenshot({ path: p, fullPage: false });
        paths.push(p);
      }
      return { paths, segments: n };
    }
    case 'resize':
      // Change the viewport. A tall viewport (e.g. 1400x2800) makes fixed-height
      // (100vh) editor/modal layouts expand their flex-scrollable body to fit
      // content, so a single fullPage shot captures the whole thing without
      // inner-scroll segmenting. Remember to resize back to 1400x900 after.
      await page.setViewportSize({ width: params.width || 1400, height: params.height || 900 });
      return { ok: true };
    case 'scrollThrough':
      // Scroll the page (or a selector's nearest scroll container) top→bottom
      // in viewport steps to trigger lazy rendering, then back to top.
      await scrollThroughPage(page, params.settle, params.selector);
      return { ok: true };
    case 'scrollElement': {
      // Scroll a specific inner-scroll container to its end (e.g. a modal body,
      // a Terms-of-Use box that gates a checkbox until fully read). Dispatches a
      // scroll event so "scrolled to end" listeners fire.
      const done = await page.evaluate((selector) => {
        const el = document.querySelector(selector);
        if (!el) return false;
        el.scrollTop = el.scrollHeight;
        el.dispatchEvent(new Event('scroll', { bubbles: true }));
        return true;
      }, params.selector);
      if (!done) throw new Error(`scrollElement: no element matching "${params.selector}"`);
      return { ok: true };
    }
    case 'text':
      return { text: await page.innerText(params.selector || 'body') };
    case 'html':
      return { html: await page.content() };
    case 'click':
      await page.click(params.selector, { timeout: params.timeout || 10000 });
      return { ok: true };
    case 'clickText': {
      // Robust click-by-text: finds the first VISIBLE element whose trimmed
      // text matches (exact by default; params.contains for substring) and
      // clicks it via DOM. Sidesteps CSS-selector ambiguity and responsive
      // duplicate elements that make page.click strict-mode-fail.
      const clicked = await page.evaluate(({ text, contains, tag }) => {
        const sel = tag || 'button,a,[role=button],[role=tab],[role=menuitem]';
        const onScreen = (el) => {
          if (el.offsetParent === null) return false;
          const r = el.getBoundingClientRect();
          // Reject zero-size and off-screen-positioned elements (e.g. closed
          // dropdown items parked at top:-9999 that are technically "visible").
          if (r.width < 1 || r.height < 1) return false;
          return r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth;
        };
        const els = Array.from(document.querySelectorAll(sel));
        const match = els.find((el) => {
          if (!onScreen(el)) return false;
          const t = (el.innerText || el.textContent || '').trim();
          return contains ? t.includes(text) : t === text;
        });
        if (match) { match.click(); return true; }
        return false;
      }, { text: params.text, contains: !!params.contains, tag: params.tag });
      if (!clicked) throw new Error(`clickText: no visible element matching "${params.text}"`);
      return { ok: true };
    }
    case 'fill':
      await page.fill(params.selector, params.text, { timeout: params.timeout || 10000 });
      return { ok: true };
    case 'press':
      await page.keyboard.press(params.key);
      return { ok: true };
    case 'hover':
      await page.hover(params.selector, { timeout: params.timeout || 10000 });
      return { ok: true };
    case 'drag': {
      // Native mouse drag between two elements (e.g. React Flow connections).
      // params: { fromSelector, toSelector, steps? } — hovers the source first
      // so hover-revealed drag handles become visible/interactive.
      const from = page.locator(params.fromSelector).first();
      const to = page.locator(params.toSelector).first();
      await from.hover({ timeout: params.timeout || 10000 });
      const fb = await from.boundingBox();
      const tb = await to.boundingBox();
      if (!fb || !tb) throw new Error('drag: element not visible');
      const sx = fb.x + fb.width / 2;
      const sy = fb.y + fb.height / 2;
      const tx = tb.x + tb.width / 2;
      const ty = tb.y + tb.height / 2;
      await page.mouse.move(sx, sy);
      await page.mouse.down();
      const steps = params.steps || 12;
      for (let i = 1; i <= steps; i += 1) {
        await page.mouse.move(sx + ((tx - sx) * i) / steps, sy + ((ty - sy) * i) / steps);
      }
      await page.mouse.up();
      return { ok: true, from: { x: sx, y: sy }, to: { x: tx, y: ty } };
    }
    case 'check':
      await page.setChecked(params.selector, params.checked !== false, { timeout: params.timeout || 10000 });
      return { ok: true };
    case 'selectOption':
      return { selected: await page.selectOption(params.selector, params.value, { timeout: params.timeout || 10000 }) };
    case 'upload':
      // params.files: path(s) relative to repo root or absolute.
      await page.setInputFiles(
        params.selector,
        (Array.isArray(params.files) ? params.files : [params.files]).map((f) => resolve(__dirname, '..', '..', f)),
        { timeout: params.timeout || 10000 }
      );
      return { ok: true };
    case 'eval':
      // params.code must be a single JS EXPRESSION (it is wrapped in `return (...)`).
      return { result: await page.evaluate(new Function('return (' + params.code + ')')) };
    case 'wait':
      await page.waitForTimeout(params.ms || 1000);
      return { ok: true };
    case 'waitForSelector':
      await page.waitForSelector(params.selector, { timeout: params.timeout || 10000, state: params.state });
      return { ok: true };
    default:
      throw new Error('unknown action: ' + action);
  }
}

function parseSteps(arg) {
  const trimmed = arg.trim();
  if (trimmed.startsWith('[')) return JSON.parse(trimmed);
  // Otherwise treat as a path to a JSON file of steps — avoids shell-quoting
  // pain (especially under PowerShell) for long batches.
  return JSON.parse(readFileSync(resolve(process.cwd(), trimmed), 'utf8'));
}

async function main() {
  const stepsArg = process.argv[2];
  if (!stepsArg) {
    console.error('Usage: node browser.mjs \'[{"action":"goto","params":{"url":"/"}}]\'  (or a path to a steps .json file)');
    process.exit(1);
  }
  const steps = parseSteps(stepsArg);
  const results = [];

  const watchdog = setTimeout(() => {
    console.log(JSON.stringify(results, null, 2));
    console.error(`[agent-browser] WATCHDOG: batch exceeded ${WATCHDOG_MS}ms — printed partial results and exiting. Is the dev server up?`);
    process.exit(2);
  }, WATCHDOG_MS);

  // Headless is required, not a preference: this runs in a sandboxed/headless
  // CI-like environment with no interactive desktop session, so a headed
  // Chromium window never paints and any call needing a real compositor
  // frame (screenshots) hangs indefinitely. DOM-level calls (title, eval)
  // work either way, but headless is the only mode that's reliable here.
  let context;
  try {
    context = await chromium.launchPersistentContext(PROFILE_DIR, {
      headless: true,
      viewport: { width: 1400, height: 900 },
    });
  } catch (e) {
    if (/ProcessSingleton|profile is already in use|Target page, context or browser has been closed/i.test(String(e))) {
      console.error('[agent-browser] The persistent profile is locked — another browser.mjs invocation is still running. Run one batch at a time.');
      process.exit(1);
    }
    throw e;
  }
  const page = context.pages()[0] || (await context.newPage());
  await installApiBypass(context);
  await installGcsUploadProxy(context);

  const collected = { consoleLogs: [], apiRequests: new Map() };
  page.on('console', (msg) => collected.consoleLogs.push({ type: msg.type(), text: msg.text() }));
  page.on('pageerror', (err) => collected.consoleLogs.push({ type: 'pageerror', text: String(err) }));
  const isApi = (req) => new URL(req.url()).pathname.startsWith('/api/');
  context.on('request', (req) => {
    if (!isApi(req)) return;
    const u = new URL(req.url());
    collected.apiRequests.set(req, { method: req.method(), path: u.pathname + u.search, status: 'pending' });
  });
  context.on('response', (resp) => {
    const entry = collected.apiRequests.get(resp.request());
    if (entry) entry.status = resp.status();
  });
  context.on('requestfailed', (req) => {
    const entry = collected.apiRequests.get(req);
    if (entry) entry.status = 'failed: ' + (req.failure()?.errorText || 'unknown');
  });

  for (const step of steps) {
    try {
      const result = await runAction(page, step, collected);
      results.push({ action: step.action, ok: true, result });
    } catch (e) {
      results.push({ action: step.action, ok: false, error: String((e && e.message) || e) });
    }
  }

  console.log(JSON.stringify(results, null, 2));
  clearTimeout(watchdog);
  await context.close();
}

main().catch((e) => {
  console.error('ERROR', e);
  process.exit(1);
});
