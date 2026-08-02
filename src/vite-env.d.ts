/// <reference types="vite/client" />

/**
 * Build-time environment, declared rather than inherited.
 *
 * Vite's own `ImportMetaEnv` is an open interface, so an undeclared key reads as
 * `any` and a typo in a variable name silently becomes `undefined` at runtime.
 * Naming each one here makes the set of things the client may read explicit —
 * which matters more than usual, because anything named `VITE_*` is inlined
 * into the bundle and therefore public.
 */
interface ImportMetaEnv {
  /** Local development only. The server independently requires ENVIRONMENT=local,
   * a matching secret and an allow-listed identity before honouring it, and the
   * whole branch is eliminated from a production build by `import.meta.env.DEV`. */
  readonly VITE_DEV_AUTH_BYPASS_SECRET?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv & { readonly DEV: boolean; readonly PROD: boolean }
}
