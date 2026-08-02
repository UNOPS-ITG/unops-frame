/* Types for ports.mjs.
 *
 * The implementation stays plain ESM rather than TypeScript because it is
 * imported by vite.config.ts, by Node scripts under scripts/, and by tooling
 * that runs before any build step exists — a .ts module would need a compile
 * pass in each of those contexts. A hand-written declaration is the cheaper
 * side of that trade.
 */

export interface EmulatorPorts {
  firestore: number
  auth: number
  functions: number
  storage: number
  pubsub: number
  ui: number
  hub: number
}

export interface Ports {
  frontend: number
  backend: number
  oauthProxy: number
  emulators: EmulatorPorts
  postgres: number
}

export interface Urls {
  frontend: string
  backend: string
  oauthProxy: string
  emulatorUi: string
}

export declare const ports: Ports
export declare const urls: Urls
export default ports
