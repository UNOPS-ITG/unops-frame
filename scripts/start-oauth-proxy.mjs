#!/usr/bin/env node
/**
 * Cross-platform launcher for oauth2-proxy.
 *
 * Picks `oauth2-proxy.exe` on Windows and `./oauth2-proxy` elsewhere, run
 * from the repo root so the relative config paths resolve correctly.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");

const isWindows = process.platform === "win32";
const binaryPath = join(repoRoot, isWindows ? "oauth2-proxy.exe" : "oauth2-proxy");

if (!existsSync(binaryPath)) {
  console.error(`[start-oauth-proxy] Binary not found at ${binaryPath}.`);
  process.exit(1);
}

const args = [
  "--alpha-config=oauth2-proxy.cfg.yaml",
  "--config=oauth2-proxy.cfg.template",
];

// Use the absolute binary path: on Windows `spawn` with shell:false resolves a
// relative executable name against PATH (not cwd), which would throw ENOENT.
const child = spawn(binaryPath, args, {
  cwd: repoRoot,
  stdio: "inherit",
  shell: false,
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
