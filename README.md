# Frame

A governed work platform: a Smartsheet-grade grid over metadata-defined **Blueprints**.

Two people open the same saved view of the same register from the same URL and legitimately see
different rows and different columns — annotated, server-enforced, audited, and fast at scale, on a
grid we own, with zero per-Blueprint code.

That sentence is Milestone 1's exit criterion, and `npm run demo:m1` asserts it.

- **Why the product exists, and what it is not**: `specs/frame-prds/product-vision-frame.md`
- **The requirements**: `specs/frame-prds/00-prd-index.md` and the fourteen PRDs beside it
- **How to work in this repo, and where it deliberately differs from sibling repos**: `CLAUDE.md`

---

## Running it locally

Everything runs against emulators. Nothing touches GCP.

```bash
npm install
cd functions && ./setup_venv.sh   # setup_venv.ps1 on Windows
```

Then, in three terminals:

```bash
npx firebase emulators:start --only firestore   # Firestore on 6310
npm run seed                                    # a demo register, two personas, one saved view
npm run dev                                     # API on 6301, web on 6300
```

Open `http://localhost:6300/`:

| URL | What it is |
| --- | --- |
| `/` | the grid harness — synthetic rows, no backend needed, used by the perf suite |
| `/#tokens` | the design-token gallery |
| `/#register/ws-demo/risk` | the seeded register, live |
| `/#view/ws-demo/risk/open-risks` | the same register through a shared saved view |

The seed creates two identities — `risk@unops.org` (risk team) and `dev@unops.org` (staff) — so the
governed behaviour is visible locally. A seed with one identity makes a governed grid look exactly
like an ungoverned one, which is the thing nobody then tests.

**Ports.** `config/ports.json` is the single source of truth, shared by the Node tooling, the Python
backend and Docker. Frame uses a contiguous `63xx` block rather than the estate defaults (4200, 4180,
8000, 5432, 9099…) so it can run beside sibling projects. Any port can be overridden with
`FRAME_PORT_*`, or the whole block shifted with `FRAME_PORT_OFFSET`, for a second checkout.
`npm run check:ports` fails the build if a literal creeps back in.

---

## The checks, and what each is for

```bash
npm run verify   # ports, lint, typecheck, architectural fitness, frontend unit tests
npm run perf     # the canvas actually paints, and stays responsive at 50,000 rows
npm run e2e      # the real stack: emulator → permission library → API → grid
npm run demo:m1  # the milestone criterion, asserted and screenshotted
cd functions && ./venv/Scripts/python -m pytest    # the backend suite
```

They are not interchangeable, and the split is deliberate:

**`tools/fitness`** guards the invariants that decay silently. One write path, one permission
evaluator, no permission logic in the client, no per-Blueprint router. Each failure message states
the reason, because an engineer who understands why will comply and one who only sees a red test
will route around it.

**`npm run perf`** exists because a canvas grid can pass every jsdom test and render a blank
rectangle: an unparseable `fillStyle` is *silently ignored*. It reads real pixels out of a real
browser. It needs only Vite — the check that the grid renders at all must not be able to fail because
Firestore was not running.

**`npm run e2e`** needs the emulator, the seed and the API. It catches what the unit suites
structurally cannot: a wire contract that changed on one side, a route that moved, a permission rule
that is correct in isolation and wrong once a real principal is resolved. Several bugs have been
found only here.

---

## What exists

| | |
| --- | --- |
| **Blueprint engine** | metaschema, `compile_blueprint`, BP-26 coherence validation, the indexable projection |
| **Expression grammar** | one AST, three backends, a conformance suite asserting they agree |
| **Permission library** | the only place an allow/deny decision is made; four registered consumers |
| **Write path** | one function, field-scoped versions, audit and transactional outbox in one commit |
| **Read path** | over-fetch with a scan bound, honest counts, the cursor-of-last-fetched rule |
| **Generated API** | one router for every Blueprint; per-Blueprint-version OpenAPI |
| **Delta channel** | server-mediated, evaluated per delta; no client store listener, ever |
| **Saved views** | user-authored filters and sorts; a view grants nothing |
| **Master-detail** | PM-3 composition, parent ceiling applied last |
| **Import / export** | callers of the single write path; withheld counts travel with the file |
| **The grid** | `FrameGrid` over Glide Data Grid, brand-tokened, withheld cells legible |

Not yet built: forms, automations, document generation, the AI layer, corporate data (PRD 14),
reporting, notifications, search.
