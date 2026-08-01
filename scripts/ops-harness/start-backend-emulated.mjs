#!/usr/bin/env node
/**
 * Launch the FastAPI backend pointed at the LOCAL Firebase emulators, with
 * fake-AI mode on. The emulated twin of scripts/start-backend.mjs — used by
 * `npm run dev:emulated` (see scripts/ops-harness/README.md).
 *
 * Env it injects (overridable by pre-setting them):
 * - FIRESTORE_EMULATOR_HOST=localhost:8181 → Firestore reads/writes hit the
 *   emulator AND lib/queue.py routes worker dispatch to the local functions
 *   emulator instead of Cloud Tasks (see _is_emulator()).
 * - GCLOUD_PROJECT=unops-ai-playbook-dev → emulator namespace/project id.
 * - FAKE_AI=1 → generate_gemini_response returns canned output (lib/fake_ai.py).
 */
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..", "..");
const functionsDir = join(repoRoot, "functions");

// Keep host/port in one place: read the firestore emulator port from firebase.json.
const firebaseJson = JSON.parse(readFileSync(join(repoRoot, "firebase.json"), "utf8"));
const fsPort = firebaseJson?.emulators?.firestore?.port ?? 8181;
const fsHost = firebaseJson?.emulators?.firestore?.host ?? "localhost";

const isWindows = process.platform === "win32";
const pythonPath = isWindows
  ? join(functionsDir, "venv", "Scripts", "python.exe")
  : join(functionsDir, "venv", "bin", "python");

if (!existsSync(pythonPath)) {
  console.error(`[ops-harness] Python interpreter not found at ${pythonPath}. Run functions/setup_venv first.`);
  process.exit(1);
}

const env = {
  FIRESTORE_EMULATOR_HOST: `${fsHost}:${fsPort}`,
  GCLOUD_PROJECT: "unops-ai-playbook-dev",
  FAKE_AI: "1",
  ...process.env,
};
console.log(`[ops-harness] backend → emulator firestore at ${env.FIRESTORE_EMULATOR_HOST}, FAKE_AI=${env.FAKE_AI}`);

const child = spawn(pythonPath, ["-m", "api.cloudrun"], {
  cwd: functionsDir,
  stdio: "inherit",
  env,
});

const forward = (signal) => {
  if (!child.killed) child.kill(signal);
};
process.on("SIGINT", () => forward("SIGINT"));
process.on("SIGTERM", () => forward("SIGTERM"));

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 0);
});
