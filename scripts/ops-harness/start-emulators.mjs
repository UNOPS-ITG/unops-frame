#!/usr/bin/env node
/**
 * Start the Firebase emulators for the operations test harness.
 *
 * Ensures functions/.env.local exists first (firebase-tools loads it ONLY in
 * the emulator; it carries the FAKE_AI flags and is gitignored, so a fresh
 * checkout wouldn't have it), then execs `firebase emulators:start`.
 */
import { spawn } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..", "..");
const envLocal = join(repoRoot, "functions", ".env.local");

if (!existsSync(envLocal)) {
  writeFileSync(envLocal, [
    "# Emulator-only overrides (firebase-tools loads .env.local ONLY in the emulator).",
    "# Auto-created by scripts/ops-harness/start-emulators.mjs — see lib/fake_ai.py",
    "# for the FAKE_AI_FAIL / FAKE_AI_FAIL_400 / FAKE_AI_BOOL_DEFAULT knobs.",
    "FAKE_AI=1",
    "FAKE_AI_DELAY_MS=300",
    "",
  ].join("\n"));
  console.log(`[ops-harness] created ${envLocal} (FAKE_AI=1)`);
}

const child = spawn(
  "firebase",
  ["emulators:start", "--only", "firestore,functions", "--project", "unops-ai-playbook-dev"],
  { cwd: repoRoot, stdio: "inherit", shell: true },
);
child.on("exit", (code) => process.exit(code ?? 0));
