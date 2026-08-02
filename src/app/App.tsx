import { useEffect, useState } from 'react'
import { useThemeStore } from '@/styles/theme'
import { GridDemo } from '@/grid/GridDemo'
import { RegisterView } from '@/grid/RegisterView'
import { TokenGallery } from './TokenGallery'

/**
 * Three development surfaces, selected by hash.
 *
 * Still no router. Two of these are harnesses that will not survive to
 * production, and adding a router now would fix a URL shape before the product
 * knows what its routes are — `#register/ws1/risk` is obviously temporary in a
 * way that a `<Route path="/w/:ws/b/:bp">` is not.
 */
function readSurface(hash: string) {
  if (hash === '#tokens') return { kind: 'tokens' as const }
  const register = /^#register\/([^/]+)\/([^/]+)$/.exec(hash)
  const [, workspaceId, blueprintId] = register ?? []
  if (workspaceId !== undefined && blueprintId !== undefined) {
    return { kind: 'register' as const, workspaceId, blueprintId }
  }
  return { kind: 'demo' as const }
}

export function App() {
  const init = useThemeStore((s) => s.init)
  const [surface, setSurface] = useState(() => readSurface(globalThis.location?.hash ?? ''))

  // Returns a teardown for the prefers-color-scheme listener.
  useEffect(() => init(), [init])

  useEffect(() => {
    const onHashChange = () => setSurface(readSurface(globalThis.location.hash))
    globalThis.addEventListener('hashchange', onHashChange)
    return () => globalThis.removeEventListener('hashchange', onHashChange)
  }, [])

  switch (surface.kind) {
    case 'tokens':
      return <TokenGallery />
    case 'register':
      return <RegisterView workspaceId={surface.workspaceId} blueprintId={surface.blueprintId} />
    default:
      return <GridDemo />
  }
}
