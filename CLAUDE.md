# Frame — working notes for agents and engineers

Frame is a governed work platform: a Smartsheet-grade grid over Frappe-style,
metadata-defined **Blueprints**. Read `specs/frame-prds/product-vision-frame.md`
first, then `specs/frame-prds/00-prd-index.md`. The PRDs are normative; this
file only records how to work in the repo and, more importantly, **why several
things here deliberately differ from the sibling repos**.

## The deliberate breaks from estate convention

This matters more than anything else in this file. `ai-playbook` is the stack
reference and most of its patterns are worth copying — but four are wrong for
Frame, and an agent pattern-matching it will helpfully reintroduce all four.
Each is enforced by a test in `tools/fitness`, and each test failure explains
its own reason.

**1. There is no router file per feature.** Playbook has ~31 routers named after
business nouns. Frame generates its REST surface from compiled Blueprint
metadata: a small fixed set of generic routers, and zero per-Blueprint Python.
This is not a style preference, it *is* the Frappe claim the product rests on —
"nobody builds a CRUD screen in Frame, ever". The moment one hand-written
per-Blueprint router exists, "zero per-Blueprint code" stops being
demonstrable.

**2. There is no `callable-to-rest` mapping and no hand-maintained type
mirror.** Playbook keeps a 340-line map plus a duplicated `src/types/` tree.
Frame generates its typed client from the published OpenAPI. Row *payloads*
stay dynamically typed, because Blueprints are user-authored and there is no
static type to generate; the *envelope* — Blueprint metadata, the trimmed row
page, annotations — is generated and static.

**3. Nothing in the client decides access, and there are no client-side store
listeners on row data.** Playbook's rules are deny-all with all access through
the API, which Frame keeps. Frame goes further: real-time is server-mediated
through rooms whose subscription is itself an evaluated permission decision.
A direct Firestore listener would force row-level ABAC into security rules — a
second implementation, in a second language, that cannot express parent-child
composition or typed restricted stubs at all.

**4. Row field values are never case-transformed on the wire.** The pydantic
base class camelCases the *envelope*; the value map passes through untouched.
An auto-camelizer turning a user's `vendor_name` field id into `vendorName`
inside their own data is a spectacular retrofit across every row in the estate.

## Invariants the fitness suite enforces

`npm run fitness`. These are specification promises made checkable:

- One permission evaluator, and none of it in the client (PM-4).
- One row writer; every channel is a caller, never a peer (BP-4).
- No per-Blueprint router file.
- Event consumers cannot reach row storage — they refetch through the API under
  their own identity, so the event stream never becomes a permission bypass.
- No raw colours, shadows or layout widths outside the token files.

A check whose subject does not exist yet logs that it is not yet enforced
rather than passing silently. A green suite that protects nothing is worse than
no suite.

## Design tokens

Non-negotiable, and `tools/fitness/design-tokens.test.ts` enforces it: colours,
shadows and container widths come from `src/styles/brand-tokens.css`, never
from literals. Three rules the tokens encode — never a pure neutral, shadows
carry brand temperature rather than black, and interactive states are
brand-tinted overlays rather than grey washes.

**The theme trap.** Themes are `light`, `grey`, `dark`. "Auto" is the *absence*
of `data-theme`, not a value: `brand-tokens.css` selects the auto branch with
`:root:not([data-theme])`, so writing `data-theme="auto"` matches no block,
silently pins light, and disables system following. The pre-paint script in
`index.html` removes the attribute instead.

**For the canvas grid**, every interactive colour is a `color-mix()`, which a
canvas renderer cannot consume. Resolve tokens to literal RGB through
`getComputedStyle` and re-resolve on theme change — do not hard-code the
resolved values.

## Toolchain notes

- **TypeScript is pinned to 5.x, not 7.** `typescript-eslint` caps at `<6.1`;
  TS 7 breaks linting today. Revisit when it does not.
- **`react-router` is pinned to 7.x.** v8 declares Node `>=22.22`; bump the
  local Node and this can move.
- `noUncheckedIndexedAccess` is on deliberately: row values are keyed by
  user-defined field ids, so indexing into them genuinely is unsafe.

## Commands

```
npm run dev         # Vite on :4200, /api proxied to :8000
npm run verify      # lint + typecheck + fitness + unit tests
npm run fitness     # the architectural gate on its own
npm run build       # tsc -b, locale check, then vite build
```

## Environment

Development is local: emulators, and Docker for the full stack. **Nothing
happens on GCP without asking the repo owner first.** BigQuery access is a
user-consented connector following the `ai-bob` pattern, not a service account
and not domain-wide delegation.
