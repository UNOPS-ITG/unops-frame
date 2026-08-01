#!/usr/bin/env node
/**
 * Seed the local Firestore emulator with a real case copied from dev.
 * Thin cross-platform wrapper around functions/scripts/seed_local_case.py.
 *
 * Usage: npm run ops:seed                      → seeds the reference test case
 *        npm run ops:seed -- --case <id> …     → any seed_local_case.py args
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_CASE = "bj4bgBS0iahBkMuoRmvn"; // RFQ/ITB Evaluation reference case (14 quotations, 6 stages)

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..", "..");
const functionsDir = join(repoRoot, "functions");
const isWindows = process.platform === "win32";
const pythonPath = isWindows
  ? join(functionsDir, "venv", "Scripts", "python.exe")
  : join(functionsDir, "venv", "bin", "python");

if (!existsSync(pythonPath)) {
  console.error(`[ops-harness] Python interpreter not found at ${pythonPath}.`);
  process.exit(1);
}

const extra = process.argv.slice(2);
const args = ["scripts/seed_local_case.py", ...(extra.includes("--case") ? [] : ["--case", DEFAULT_CASE]), ...extra];

const res = spawnSync(pythonPath, args, { cwd: functionsDir, stdio: "inherit", env: process.env });
process.exit(res.status ?? 1);
