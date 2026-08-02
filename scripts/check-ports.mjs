#!/usr/bin/env node
/* Guards Frame's local port allocation.
 *
 * Two failure modes, both of which have already happened once on this machine:
 *
 *   1. Two config files disagree, so the seeder writes into one emulator while
 *      the backend reads from another and the symptom is "my data vanished".
 *   2. A port literal creeps back into source, Frame binds an estate-shared
 *      port, and it silently steals traffic from a sibling project — or slides
 *      to a free port and a tool then talks to whatever else was listening.
 *
 * Run by `npm run verify` and the pre-commit hook.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { ports } from '../config/ports.mjs'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const problems = []

/* --- 1. emulator-config.json agrees with config/ports.json ---------------- */
const emu = JSON.parse(readFileSync(join(root, 'scripts/emulator-config.json'), 'utf8'))
const expected = {
  auth: ports.emulators.auth,
  firestore: ports.emulators.firestore,
  functions: ports.emulators.functions,
  storage: ports.emulators.storage,
}
for (const [name, want] of Object.entries(expected)) {
  const got = emu.emulators?.[name]?.port
  if (got !== want) {
    problems.push(
      `scripts/emulator-config.json: ${name} emulator is on ${got}, config/ports.json says ${want}`,
    )
  }
}

/* --- 2. No estate-shared port literals in our own source ------------------ */
// Ports owned by sibling projects on this machine. Frame must not bind them.
const FORBIDDEN = new Map([
  [4200, 'Vite/Angular default, used by ai-playbook'],
  [4180, 'oauth2-proxy default'],
  [8000, 'generic backend default'],
  [8080, 'generic'],
  [5432, 'Postgres default'],
  [5173, 'Vite default'],
  [3000, 'Node default'],
  [9099, 'Firebase auth emulator default'],
  [8181, 'Firestore emulator, used by ai-playbook'],
  [5001, 'Firebase functions emulator default'],
  [9199, 'Firebase storage emulator default'],
  [4000, 'Firebase emulator UI default'],
])

const SCANNED = [
  'vite.config.ts',
  'config/ports.json',
  'config/ports.mjs',
  'scripts/emulator-config.json',
  'scripts/start-backend.mjs',
  'tools/shoot-gallery.mjs',
  'scripts/agent-browser/browser.mjs',
  'functions/api/cloudrun.py',
  'functions/api/core/config.py',
]

for (const rel of SCANNED) {
  let text
  try {
    text = readFileSync(join(root, rel), 'utf8')
  } catch {
    continue // not created yet
  }
  // Strip comments so the explanatory prose in ports.json — which names the
  // forbidden ports on purpose — does not trip its own rule.
  const code = text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*(\/\/|#).*$/gm, '')
    .replace(/"\$comment"\s*:\s*(\[[\s\S]*?\]|"[^"]*")/g, '')

  for (const [port, why] of FORBIDDEN) {
    if (new RegExp(`\\b${port}\\b`).test(code)) {
      problems.push(`${rel}: hard-codes ${port} (${why}). Use config/ports.json.`)
    }
  }
}

/* --- 3. firebase.docker.json agrees with firebase.json, on 0.0.0.0 -------- */
// Inside a container 127.0.0.1 means "reachable only from this container", so the
// published ports would answer nothing while the stack looked started.
try {
  const fb = JSON.parse(readFileSync(join(root, 'firebase.json'), 'utf8'))
  const fbDocker = JSON.parse(readFileSync(join(root, 'firebase.docker.json'), 'utf8'))

  if (fbDocker.firestore?.database !== fb.firestore?.database) {
    problems.push(
      `firebase.docker.json: database "${fbDocker.firestore?.database}" != "${fb.firestore?.database}"`,
    )
  }
  for (const [name, cfg] of Object.entries(fb.emulators ?? {})) {
    if (typeof cfg !== 'object' || cfg === null || cfg.port === undefined) continue
    const docker = fbDocker.emulators?.[name]
    if (docker?.port !== cfg.port) {
      problems.push(`firebase.docker.json: ${name} port ${docker?.port} != ${cfg.port}`)
    }
    if (docker?.host !== '0.0.0.0') {
      problems.push(
        `firebase.docker.json: ${name} host is "${docker?.host}", must be 0.0.0.0 — ` +
          '127.0.0.1 inside a container is unreachable from the published port',
      )
    }
    if (cfg.host && cfg.host !== '127.0.0.1') {
      problems.push(`firebase.json: ${name} host should be 127.0.0.1, found "${cfg.host}"`)
    }
  }
} catch (err) {
  problems.push(`could not compare firebase.json / firebase.docker.json: ${err.message}`)
}

/* --- 4. docker-compose publishes the same ports --------------------------- */
try {
  const compose = readFileSync(join(root, 'docker-compose.yml'), 'utf8')
  const expected = [
    ['FRAME_PORT_POSTGRES', ports.postgres],
    ['FRAME_PORT_FIRESTORE', ports.emulators.firestore],
    ['FRAME_PORT_AUTH', ports.emulators.auth],
    ['FRAME_PORT_FUNCTIONS', ports.emulators.functions],
    ['FRAME_PORT_STORAGE', ports.emulators.storage],
    ['FRAME_PORT_PUBSUB', ports.emulators.pubsub],
    ['FRAME_PORT_EMULATOR_UI', ports.emulators.ui],
    ['FRAME_PORT_EMULATOR_HUB', ports.emulators.hub],
    ['FRAME_PORT_BACKEND', ports.backend],
  ]
  for (const [envName, port] of expected) {
    // Compose cannot import config/ports.mjs, so the default is written inline and
    // checked here instead.
    if (!new RegExp(`\\$\\{${envName}:-${port}\\}`).test(compose)) {
      problems.push(
        `docker-compose.yml: expected \${${envName}:-${port}} — the inline default has ` +
          'drifted from config/ports.json',
      )
    }
  }
  // Publishing to 0.0.0.0 would put a dev/dev Postgres on the office network.
  const unbound = [...compose.matchAll(/^\s*-\s*"(?!127\.0\.0\.1:)([^"]*:\d+)"/gm)]
  for (const m of unbound) {
    if (/\d+:\d+/.test(m[1])) {
      problems.push(`docker-compose.yml: port mapping "${m[1]}" is not bound to 127.0.0.1`)
    }
  }
} catch (err) {
  problems.push(`could not check docker-compose.yml: ${err.message}`)
}

/* --- 5. The allocation is internally consistent -------------------------- */
const all = [
  ['frontend', ports.frontend],
  ['backend', ports.backend],
  ['oauthProxy', ports.oauthProxy],
  ...Object.entries(ports.emulators),
  ['postgres', ports.postgres],
]
const seen = new Map()
for (const [name, port] of all) {
  if (seen.has(port)) problems.push(`${name} and ${seen.get(port)} both want port ${port}`)
  seen.set(port, name)
  // Windows allocates ephemeral outbound ports from 49152 up; binding a
  // listener there occasionally loses a race with an outgoing connection.
  if (port >= 49152) {
    problems.push(`${name}=${port} is in the ephemeral range (49152+); pick something lower`)
  }
}

if (problems.length) {
  console.error('Port configuration problems:\n')
  for (const p of problems) console.error('  • ' + p)
  console.error('')
  process.exit(1)
}

console.log(
  `ports ok — frontend ${ports.frontend}, backend ${ports.backend}, ` +
    `proxy ${ports.oauthProxy}, emulators ${ports.emulators.firestore}-${ports.emulators.hub}, ` +
    `postgres ${ports.postgres}`,
)
