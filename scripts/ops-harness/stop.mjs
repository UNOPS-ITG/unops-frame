#!/usr/bin/env node
/**
 * Stop the local operations test harness: Firebase emulators (hub, UI,
 * Firestore JVM, functions runtime) and the emulated API.
 *
 * Kills by listening port because on Windows the emulator/npm wrappers
 * routinely orphan their children (JVM on 8181, python runtimes, uvicorn
 * reload workers), which then hold ports and — worse — keep serving stale
 * code. Ports: 8181 (Firestore), 5001 (functions), 4400 (hub), 4000 (UI),
 * 8000 (API) unless --keep-api.
 */
import { execSync } from "node:child_process";

const keepApi = process.argv.includes("--keep-api");
const ports = [8181, 5001, 4400, 4000, ...(keepApi ? [] : [8000])];
const isWindows = process.platform === "win32";

function pidsOnPort(port) {
  try {
    if (isWindows) {
      const out = execSync(`netstat -ano -p tcp`, { encoding: "utf8" });
      return [...new Set(
        out.split(/\r?\n/)
          .filter((l) => l.includes("LISTENING") && l.match(new RegExp(`:${port}\\s`)))
          .map((l) => l.trim().split(/\s+/).pop())
          .filter((p) => p && p !== "0"),
      )];
    }
    const out = execSync(`lsof -ti tcp:${port} -s tcp:LISTEN || true`, { encoding: "utf8" });
    return out.split(/\s+/).filter(Boolean);
  } catch {
    return [];
  }
}

let killed = 0;
for (const port of ports) {
  for (const pid of pidsOnPort(port)) {
    try {
      if (isWindows) execSync(`taskkill /F /PID ${pid} /T`, { stdio: "ignore" });
      else execSync(`kill -9 ${pid}`, { stdio: "ignore" });
      console.log(`[ops-harness] killed pid ${pid} (port ${port})`);
      killed++;
    } catch {
      /* already gone */
    }
  }
}

// A dead uvicorn parent can leave a multiprocessing child holding the API
// socket (netstat still attributes the port to the dead parent PID). Reap
// children whose parent_pid matches a port-holding PID that no longer exists.
if (isWindows && !keepApi) {
  try {
    for (const pid of pidsOnPort(8000)) {
      const alive = (() => {
        try {
          execSync(`powershell -NoProfile -Command "Get-Process -Id ${pid} -ErrorAction Stop"`, { stdio: "ignore" });
          return true;
        } catch { return false; }
      })();
      if (alive) continue;
      const out = execSync(
        `powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'spawn_main.parent_pid=${pid}' } | Select-Object -ExpandProperty ProcessId"`,
        { encoding: "utf8" },
      );
      for (const child of out.split(/\s+/).filter(Boolean)) {
        try {
          execSync(`taskkill /F /PID ${child}`, { stdio: "ignore" });
          console.log(`[ops-harness] killed orphaned uvicorn child pid ${child} (dead parent ${pid})`);
          killed++;
        } catch { /* gone */ }
      }
    }
  } catch { /* best effort */ }
}

// Also reap orphaned scenario runners / seeders / functions-emulator workers.
// On Windows, killing the npm wrapper orphans python children: runners keep
// wiping/driving the emulator underneath any new run, and the functions
// emulator's per-execution Flask workers (random ports, so the port sweep
// above never sees them) accumulate by the dozens across runs until process
// pressure crashes the next emulator mid-suite.
try {
  if (isWindows) {
    const out = execSync(
      `powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"Name='python.exe'\\" | Where-Object { $_.CommandLine -match 'run_ops_scenarios|seed_local_case|ai-playbook.functions' } | Select-Object -ExpandProperty ProcessId"`,
      { encoding: "utf8" },
    );
    for (const pid of out.split(/\s+/).filter(Boolean)) {
      try {
        execSync(`taskkill /F /PID ${pid}`, { stdio: "ignore" });
        console.log(`[ops-harness] killed orphaned runner pid ${pid}`);
        killed++;
      } catch { /* gone */ }
    }
  } else {
    execSync(`pkill -f 'run_ops_scenarios|seed_local_case' || true`, { stdio: "ignore" });
  }
} catch { /* best effort */ }

console.log(killed ? `[ops-harness] stopped (${killed} process(es))` : "[ops-harness] nothing running");
