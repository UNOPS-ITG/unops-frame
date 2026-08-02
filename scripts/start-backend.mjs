#!/usr/bin/env node
/**
 * Cross-platform launcher for the Python FastAPI backend.
 *
 * Picks the correct interpreter inside `functions/venv` for the host OS
 * and runs `python -m api.cloudrun` with `functions/` as the cwd, so the
 * uvicorn dev server (with reload) starts the same way on Windows and Linux.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { ports } from "../config/ports.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");
const functionsDir = join(repoRoot, "functions");

const isWindows = process.platform === "win32";
const pythonPath = isWindows
  ? join(functionsDir, "venv", "Scripts", "python.exe")
  : join(functionsDir, "venv", "bin", "python");

if (!existsSync(pythonPath)) {
  console.error(
    `[start-backend] Python interpreter not found at ${pythonPath}.\n` +
      `Run 'cd functions && ${isWindows ? "setup_venv.bat" : "./setup_venv.sh"}' first.`,
  );
  process.exit(1);
}

const child = spawn(pythonPath, ["-m", "api.cloudrun"], {
  cwd: functionsDir,
  stdio: "inherit",
  env: {
    ...process.env,
    // Passed explicitly rather than left to functions/config/.env, so that the
    // backend and every emulator client agree even when FRAME_PORT_OFFSET has
    // shifted the whole block for a second checkout. config/ports.json stays
    // the single source of truth in both languages.
    PORT: String(ports.backend),
    FIRESTORE_EMULATOR_HOST: `127.0.0.1:${ports.emulators.firestore}`,
    PUBSUB_EMULATOR_HOST: `127.0.0.1:${ports.emulators.pubsub}`,
    FIREBASE_AUTH_EMULATOR_HOST: `127.0.0.1:${ports.emulators.auth}`,
    FIREBASE_STORAGE_EMULATOR_HOST: `127.0.0.1:${ports.emulators.storage}`,
  },
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
