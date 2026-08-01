# Run Microworld

A throwaway viewer for one artifact-generation run: what every operation did,
when, what the engine decided, and where an invariant first broke.

Two files, both deliberately outside the app:

| | |
|---|---|
| `functions/scripts/export_run_trace.py` | reads Firestore/GCS → one `trace.json` (+ a text digest) |
| `scripts/run-microworld/viewer.html` | one self-contained page that renders a `trace.json` |

## Why it lives here and not in `src/`

Anything under `src/` pays `tsc -b` with `noUncheckedIndexedAccess`, eslint, i18n
keys across five locale catalogs (enforced by `scripts/check-locales.mjs` inside
`npm run build`), RTL logical properties, theme tokens, vitest, **and prod bundle
weight**. A diagnostic nobody ships should pay none of that. `scripts/` is
eslint-ignored and never bundled, so this viewer is English-only with hard-coded
colours on purpose — the `ui-panel-conventions` and `display-conventions` rules
apply to the product, not to this.

It also adds no API route (so no `callable-to-rest.mapping.ts` entry, no
`check-callable-mappings.mjs` change, no contract test), no Firestore index, and
nothing to the deploy path.

## Use it

```bash
cd functions

# newest run on a case, against the local emulator harness
venv/Scripts/python.exe scripts/export_run_trace.py <caseId> --digest

# real dev, every root tree in the case
venv/Scripts/python.exe scripts/export_run_trace.py <caseId> --env dev --roots 0 --digest
```

Every export writes **one timestamped folder** here, holding both files:

```
scripts/run-microworld/runtraces/
  2026-07-26T134743Z-generate-all/
    trace.json     the data
    run.html       the viewer with that trace inlined — just open it
```

The location is anchored to the repo root, so it does not depend on which
directory you ran from. The folder suffix is the case id by default, or the
scenario name when the ops suite writes it; override with `--label`. Open
`run.html` directly (no file picker, no network), or open `viewer.html` and drop
a `trace.json` onto it.

`runtraces/` is gitignored — these are regenerable post-mortem dumps. The viewer
itself is tracked. Prune the folder whenever you like.

Path overrides, if you need them: `--out-dir DIR`, `--out FILE`, `--html FILE`,
`--no-html` (skip the rendered page).

`--digest` prints a terse summary: roots and whether they are stuck, anomalies
with exact instants, invariant findings placed in time, engine event counts,
slowest nodes, and total cost. That digest is the fastest way to read a run, and
it is what an agent should look at instead of twenty Firestore probes.

Useful flags: `--roots N` (default **1** — `operations` has no TTL so a whole-case
export is unbounded), `--root <opId>`, `--since <ISO>`, `--allow <CODE>`,
`--no-invariants`, `--with-context skip` (never touch GCS).

The ops scenario suite writes traces automatically on failure into the same
`runtraces/` folder, one per scenario — see `--no-trace` / `--trace-always` /
`--trace-dir` on `npm run ops:test`. The stall dump deliberately fires **before**
the recovery sweep, because the sweep repairs the very state worth looking at.

## Read the output correctly

**This is a reconstruction, not a replay.** Firestore keeps no write log, and
`transition_operation` overwrites `status`, `startedAt` and `completedAt` on every
transition — so per operation only the *last* value of each survives.

Consequences you must keep in mind:

- **Hatched bars are inferred, not observed.** Every interval carries a
  `confidence` (`exact` / `bounded` / `unknown`) and a `why` string explaining what
  is and isn't known. Read the `why` before drawing a conclusion from a boundary.
- **Retries collapse.** `retryCount` survives but attempt windows do not (and the
  `generationCosts` doc is keyed by operation id, so retries overwrite the cost
  record too). A retried node renders as one bar with a `↻N` badge — never N bars.
- **The status held before a demotion is unrecoverable.** For the B1 stuck-barrier
  shape the viewer shows `TERMINAL_UNKNOWN` (narrowed to `COMPLETED` only when the
  `allChildrenTerminalAt` latch implies the auto-complete path). What *is* fully
  detectable is the contradiction, reported as `TERMINAL_REGRESSION` and
  `COMPLETED_BEFORE_STARTED` with exact instants.
- **Equal `createdAt` implies nothing.** Ops created in one batch share a single
  `SERVER_TIMESTAMP`, so sibling creation order is not recoverable.
- **A missing engine event is not evidence.** `runEvents` writes are best-effort
  and swallowed on failure, and `unlock_pass` is only recorded when a pass actually
  dispatched or terminalized something.

What the reconstruction really rests on is the write-once `metadata.*At` latches
(`allChildrenTerminalAt`, `sweepRepairedAt`, `contentCompleteAt`, `resetAt`,
`progressRepairedAt`, the `*ErrorAt` stamps). Unlike `status`/`startedAt`, those
survive overwrites.

## Invariants over time

The exporter reuses the checker's own predicates (`check_ops_invariants.py`, split
into `load_snapshot` + `check_snapshot`) and evaluates them at every **breakpoint**
— interval boundaries and event instants — so a finding gets a `firstTrueMs`
instead of a bare pass/fail. Clicking a finding seeks the playhead and selects the
implicated operation.

The split is not arbitrary:

| Codes | How they are evaluated |
|---|---|
| I1, I2 | **derived-exact** — read straight off the anomaly, no sampling |
| I3, I6 | **in time**, but must persist across ≥2 consecutive breakpoints (mid-flight handoffs legitimately flicker) |
| I4 | at each parent's own subtree-rest instant (mid-run drift is meaningless) |
| I5 | **tail-only** — `updatedAt` holds one value, and `progress.py` writes a flag without touching it, so a stall that later resolved is invisible |
| I7–I11 | **at rest only** — statements about the final artifact-document set |

That maps exactly onto what the data can support: the time-evaluable set is the
operation-graph invariants; the at-rest set is the artifact-document ones. The
trace has operation stamps but no artifact-doc write history.

## Keyboard

`←` / `→` step to the previous/next breakpoint (not by fixed time), `Home` / `End`
jump to the ends, and `play` animates the playhead.

## Notes

- `?trace=foo.json` works only over `http(s)`; `file://` blocks `fetch`. Use the
  file picker or `--html`.
- `--html` refuses to inline a trace over ~8 MB; open the JSON in the viewer
  instead.
- The viewer checks `traceVersion` and warns on a mismatch rather than rendering
  something misleading.
