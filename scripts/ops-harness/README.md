# ops-harness — local operations test harness

Runs the **entire artifact-operations stack locally**: Firestore emulator +
the Firebase functions emulator (real `on_operation_updated` trigger + real
`worker*` task functions) + the FastAPI backend, with `FAKE_AI=1` replacing
LLM calls by canned deterministic output. A full 6-stage × 14-dossier
generate-all completes locally in ~60 s at zero cost — including every
barrier unlock, FEEL gate, summary aggregation, and progress write.

Built in Phase 0 of `specs/operations/03-fix-plan.md`. The
`.claude/skills/ops-test/SKILL.md` skill documents the full workflow,
diagnosis guide, and fake-AI failure-injection knobs.

| Command | What it does |
|---|---|
| `npm run dev:emulated` | emulators + emulated backend + vite, one command |
| `npm run ops:emulators` | firebase emulators (firestore :8181, functions :5001) |
| `npm run ops:backend` | FastAPI :8000 → emulator Firestore, `FAKE_AI=1` (`start-backend-emulated.mjs`) |
| `npm run ops:seed` | copy a real case from dev into the emulator (`seed.mjs` → `functions/scripts/seed_local_case.py`) |
| `npm run ops:test` | E2E scenario suite (`run-scenarios.mjs` → `functions/scripts/run_ops_scenarios.py`) |
| `npm run ops:check` | invariant checker; `-- --env dev` for real dev (`check.mjs` → `functions/scripts/check_ops_invariants.py`) |
| `npm run ops:stop` | kill every harness process by port (`stop.mjs`) — emulators orphan JVMs/runtimes on Windows |

Related repair/diagnosis tools (in `functions/scripts/`):
`repair_stuck_operations.py`, `backfill_artifact_archive.py` (one-time
hidden-tombstone → artifactArchive migration).

Key facts:
- Emulator Firestore is **in-memory** — reseed after every emulator restart.
- `functions/.env.local` (emulator-only per firebase-tools) carries the
  `FAKE_AI*` flags; it is committed intentionally (no secrets).
- The emulator does NOT emulate Cloud Tasks retries; a raising worker stays
  PROCESSING locally.
- GCS artifact-content writes go to the real dev bucket (ADC) — harmless.
