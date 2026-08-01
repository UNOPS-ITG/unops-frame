#!/usr/bin/env node
/**
 * Run the operations invariant checker (functions/scripts/check_ops_invariants.py).
 *
 * Usage: npm run ops:check                          → emulator, reference case
 *        npm run ops:check -- --env dev             → real dev Firestore
 *        npm run ops:check -- --case <id> --allow I4_PROGRESS_DRIFT …
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_CASE = "bj4bgBS0iahBkMuoRmvn";

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

// Translate `--case <id>` (npm-friendly) into the positional arg.
const argv = process.argv.slice(2);
let caseId = DEFAULT_CASE;
const rest = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === "--case") caseId = argv[++i];
  else rest.push(argv[i]);
}

const res = spawnSync(pythonPath, ["scripts/check_ops_invariants.py", caseId, ...rest], {
  cwd: functionsDir,
  stdio: "inherit",
  env: { PYTHONUNBUFFERED: "1", ...process.env },
});
process.exit(res.status ?? 2);
