/* Resolves Frame's local ports.
 *
 * config/ports.json holds the defaults; any of them can be overridden by an
 * environment variable so a second checkout, or a machine where 63xx is
 * already busy, can shift without editing a tracked file.
 *
 *   FRAME_PORT_FRONTEND, FRAME_PORT_BACKEND, FRAME_PORT_OAUTH_PROXY,
 *   FRAME_PORT_FIRESTORE, FRAME_PORT_AUTH, FRAME_PORT_FUNCTIONS,
 *   FRAME_PORT_STORAGE, FRAME_PORT_PUBSUB, FRAME_PORT_EMULATOR_UI,
 *   FRAME_PORT_EMULATOR_HUB, FRAME_PORT_POSTGRES
 *
 * FRAME_PORT_OFFSET shifts the whole block at once, which is the quickest way
 * to run two Frame checkouts side by side.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const defaults = JSON.parse(readFileSync(join(here, 'ports.json'), 'utf8'))

const offset = Number.parseInt(process.env.FRAME_PORT_OFFSET ?? '0', 10) || 0

const pick = (envName, fallback) => {
  const raw = process.env[envName]
  if (raw !== undefined && raw !== '') {
    const parsed = Number.parseInt(raw, 10)
    if (Number.isInteger(parsed) && parsed > 0 && parsed < 65536) return parsed
    throw new Error(`${envName}="${raw}" is not a usable port number`)
  }
  return fallback + offset
}

export const ports = {
  frontend: pick('FRAME_PORT_FRONTEND', defaults.frontend),
  backend: pick('FRAME_PORT_BACKEND', defaults.backend),
  oauthProxy: pick('FRAME_PORT_OAUTH_PROXY', defaults.oauthProxy),
  emulators: {
    firestore: pick('FRAME_PORT_FIRESTORE', defaults.emulators.firestore),
    auth: pick('FRAME_PORT_AUTH', defaults.emulators.auth),
    functions: pick('FRAME_PORT_FUNCTIONS', defaults.emulators.functions),
    storage: pick('FRAME_PORT_STORAGE', defaults.emulators.storage),
    pubsub: pick('FRAME_PORT_PUBSUB', defaults.emulators.pubsub),
    ui: pick('FRAME_PORT_EMULATOR_UI', defaults.emulators.ui),
    hub: pick('FRAME_PORT_EMULATOR_HUB', defaults.emulators.hub),
  },
  postgres: pick('FRAME_PORT_POSTGRES', defaults.postgres),
}

export const urls = {
  frontend: `http://localhost:${ports.frontend}`,
  backend: `http://localhost:${ports.backend}`,
  oauthProxy: `http://localhost:${ports.oauthProxy}`,
  emulatorUi: `http://localhost:${ports.emulators.ui}`,
}

export default ports
