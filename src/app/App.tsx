import { useEffect, useState } from 'react'
import { useThemeStore } from '@/styles/theme'
import { GridDemo } from '@/grid/GridDemo'
import { TokenGallery } from './TokenGallery'

type Surface = 'grid' | 'tokens'

export function App() {
  const init = useThemeStore((s) => s.init)
  // Still no router: two development surfaces do not justify one, and adding a
  // router before there are real routes fixes a URL shape before the product
  // knows what its routes are.
  const [surface, setSurface] = useState<Surface>(() =>
    globalThis.location?.hash === '#tokens' ? 'tokens' : 'grid',
  )

  // Returns a teardown for the prefers-color-scheme listener.
  useEffect(() => init(), [init])

  useEffect(() => {
    const onHashChange = () => setSurface(globalThis.location.hash === '#tokens' ? 'tokens' : 'grid')
    globalThis.addEventListener('hashchange', onHashChange)
    return () => globalThis.removeEventListener('hashchange', onHashChange)
  }, [])

  return surface === 'tokens' ? <TokenGallery /> : <GridDemo />
}
