/**
 * The icon set.
 *
 * Inline SVG rather than an icon package: there are eleven of them, they are
 * all 16px line icons on the same grid, and a dependency for that is a
 * dependency to keep current. `currentColor` throughout, so an icon takes the
 * colour of whatever it sits in and never needs a token of its own — which is
 * also the only way an icon follows a theme change for free.
 *
 * `aria-hidden` on every one. Each is beside a text label, and an icon that
 * announces itself makes a screen reader say everything twice.
 */

/* eslint-disable react-refresh/only-export-components --
   The file's single export is the `Icon` namespace object rather than a set of
   named components, which fast refresh cannot follow. Worth the cost: the
   alternative is thirteen exports and an import list that grows by a line per
   glyph, and editing an icon is not a hot-reload path anybody works in. */

interface IconProps {
  className?: string
}

function Svg({ children, className }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      className={className}
      // Intrinsic size, so an icon dropped anywhere is 16px rather than fluid.
      // Without it an SVG with only a viewBox stretches to fill its container,
      // and the failure is spectacular rather than subtle: a search glyph six
      // hundred pixels tall in the middle of the page. CSS still overrides it.
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

/**
 * Exported as one namespace object rather than thirteen named exports, so a
 * call site reads `<Icon.Lock />` — the set stays legible at the point of use
 * and an import list does not grow by one line per glyph. That is what the
 * file-level fast-refresh exemption above is for.
 */
export const Icon = {
  Grid: (p: IconProps) => (
    <Svg {...p}>
      <rect x="2" y="2.5" width="12" height="11" rx="1.5" />
      <path d="M2 6h12M6.5 6v7.5" />
    </Svg>
  ),
  Table: (p: IconProps) => (
    <Svg {...p}>
      <rect x="2" y="3" width="12" height="10" rx="1.5" />
      <path d="M2 6.5h12M2 9.75h12" />
    </Svg>
  ),
  Warehouse: (p: IconProps) => (
    <Svg {...p}>
      <path d="M2 6.2 8 2.5l6 3.7V13a.5.5 0 0 1-.5.5h-11A.5.5 0 0 1 2 13z" />
      <path d="M6 13.5V9h4v4.5" />
    </Svg>
  ),
  Fields: (p: IconProps) => (
    <Svg {...p}>
      <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h7" />
    </Svg>
  ),
  Filter: (p: IconProps) => (
    <Svg {...p}>
      <path d="M2.5 3.5h11l-4.2 5v4.2l-2.6 1V8.5z" />
    </Svg>
  ),
  Upload: (p: IconProps) => (
    <Svg {...p}>
      <path d="M8 10.5V2.5M5 5.5 8 2.5l3 3" />
      <path d="M2.5 10.5v2a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-2" />
    </Svg>
  ),
  Download: (p: IconProps) => (
    <Svg {...p}>
      <path d="M8 2.5v8M5 7.5l3 3 3-3" />
      <path d="M2.5 10.5v2a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-2" />
    </Svg>
  ),
  Search: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="7" cy="7" r="4.25" />
      <path d="m10.2 10.2 3.3 3.3" />
    </Svg>
  ),
  Close: (p: IconProps) => (
    <Svg {...p}>
      <path d="m4 4 8 8M12 4l-8 8" />
    </Svg>
  ),
  Lock: (p: IconProps) => (
    <Svg {...p}>
      <rect x="3.25" y="7" width="9.5" height="6.5" rx="1.5" />
      <path d="M5.5 7V5.25a2.5 2.5 0 0 1 5 0V7" />
    </Svg>
  ),
  Check: (p: IconProps) => (
    <Svg {...p}>
      <path d="m3 8.5 3.2 3.2L13 5" />
    </Svg>
  ),
  Plus: (p: IconProps) => (
    <Svg {...p}>
      <path d="M8 3.5v9M3.5 8h9" />
    </Svg>
  ),
  Chevron: (p: IconProps) => (
    <Svg {...p}>
      <path d="m6 4 4 4-4 4" />
    </Svg>
  ),
}
