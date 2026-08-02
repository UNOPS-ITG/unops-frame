import { useEffect } from 'react'
import { useThemeStore } from '@/styles/theme'
import { TokenGallery } from './TokenGallery'

export function App() {
  const init = useThemeStore((s) => s.init)

  // Returns a teardown for the prefers-color-scheme listener.
  useEffect(() => init(), [init])

  // Stage 1 has no router yet; the gallery is the only surface, and it exists
  // to make theme regressions visible rather than to be part of the product.
  return <TokenGallery />
}
