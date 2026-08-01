#!/usr/bin/env node
/**
 * Run the operations E2E scenario suite (functions/scripts/run_ops_scenarios.py)
 * against the local harness. Requires `npm run dev:emulated` (or ops:emulators
 * + ops:backend) to be running.
 *
 * Usage: npm run ops:test
 *        npm run ops:test -- --only generate-all,cancel
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..", "..");
const functionsDir = join(repoRoot, "functions");
const isWindows = process.platform === "win32";
const pythonPath = isWindows
  ? join(functionsDir, "venv", "Scripts", "python.exe")
  : join(functionsDir, "venv", "bin", "python");

if (!existsSync(pythonPath)) {
  console.error(`[ops-harness] Python interpreter not found at ${pythonPath}.`);
  process.exit(2);
}

const res = spawnSync(pythonPath, ["scripts/run_ops_scenarios.py", ...process.argv.slice(2)], {
  cwd: functionsDir,
  stdio: "inherit",
  env: { PYTHONUNBUFFERED: "1", ...process.env },
});
process.exit(res.status ?? 2);
