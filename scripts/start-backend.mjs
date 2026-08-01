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
  env: process.env,
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
