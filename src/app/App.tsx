/* The shell. Deliberately almost empty: Stage 0 exists to prove the toolchain,
 * the tokens and the fitness suite work end to end, not to start the product. */

export function App() {
  return (
    <main className="container-md" style={{ paddingBlock: 'var(--spacing-16)' }}>
      <h1
        style={{
          fontFamily: 'var(--font-family-display)',
          fontSize: 'var(--font-size-3xl)',
          fontWeight: 'var(--font-weight-semibold)',
          letterSpacing: 'var(--letter-spacing-tight)',
          margin: 0,
        }}
      >
        Frame
      </h1>
      <p
        style={{
          color: 'var(--color-text-secondary)',
          fontSize: 'var(--font-size-base)',
          lineHeight: 'var(--line-height-relaxed)',
          maxWidth: 'var(--layout-md)',
        }}
      >
        A governed work platform: a grid you can type into, over a data model that knows what
        the rows mean.
      </p>
    </main>
  )
}
