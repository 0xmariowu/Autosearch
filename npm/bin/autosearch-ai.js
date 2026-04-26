#!/usr/bin/env node
"use strict";

// Bug 5 (fix-plan): the previous wrapper hardcoded `bash -c "curl ... | bash"`,
// which failed on Windows where bash + curl are not guaranteed. The wrapper
// now picks an installer that works on the current platform, and short-circuits
// `--help` / `--version` so users can inspect the wrapper without triggering
// a remote install prompt.
//
// Plan §P1-8 still applies: this launcher must NEVER be triggered by `npm
// install` (postinstall is removed in package.json). It runs only when the
// user types `npx autosearch-ai` or invokes the installed binary explicitly.
// Even then, an unattended install requires explicit confirmation — y/N
// prompt or `--yes` / `-y` on the command line.

const { execSync, spawnSync } = require("child_process");
const readline = require("readline");

const args = process.argv.slice(2);

const INSTALL_SCRIPT =
  "https://raw.githubusercontent.com/0xmariowu/Autosearch/main/scripts/install.sh";
const PYPI_PAGE = "https://pypi.org/project/autosearch/";

function isWindows() {
  return process.platform === "win32";
}

function hasOnPath(cmd) {
  const probe = isWindows() ? `where ${cmd}` : `command -v ${cmd}`;
  try {
    execSync(probe, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function getInstalledAutosearchVersion() {
  try {
    return execSync("autosearch --version", { encoding: "utf8" }).trim();
  } catch {
    return null;
  }
}

function hasAutosearch() {
  return getInstalledAutosearchVersion() !== null;
}

function expectedAutosearchPath() {
  if (isWindows()) {
    return "%USERPROFILE%\\AppData\\Roaming\\Python\\Python312\\Scripts\\autosearch.exe";
  }
  return `${process.env.HOME || "~"}/.local/bin/autosearch`;
}

function prependHomeLocalBinToPath() {
  if (!process.env.HOME) return;

  const localBin = `${process.env.HOME}/.local/bin`;
  const separator = isWindows() ? ";" : ":";
  const currentPath = process.env.PATH || "";
  if (currentPath.split(separator).includes(localBin)) return;

  process.env.PATH = currentPath
    ? `${localBin}${separator}${currentPath}`
    : localBin;
}

function printAutosearchNotFoundHint(error) {
  process.stderr.write(
    `\nautosearch not found after install.\n` +
      `Expected executable: ${expectedAutosearchPath()}\n` +
      `Your PATH may not include the install location yet.\n` +
      `Re-source your shell profile or install AutoSearch directly:\n` +
      `  curl -fsSL ${INSTALL_SCRIPT} | bash\n` +
      `  pipx install autosearch && autosearch init\n` +
      `  pip install --user autosearch && autosearch init\n` +
      (error?.message ? `\nOriginal error: ${error.message}\n` : "\n"),
  );
}

function printInstallerNotFoundHint(error) {
  process.stderr.write(
    `\nUnable to start the AutoSearch installer.\n` +
      `The underlying installer command was not found. Ensure one of these ` +
      `commands is available on PATH: curl, bash, pipx, py, python.\n` +
      `Then re-run: npx autosearch-ai --yes\n` +
      (error?.message ? `\nOriginal error: ${error.message}\n` : "\n"),
  );
}

// Bug 6 (fix-plan v8 follow-up): compare the wrapper's expected Python CLI
// version against what's actually installed. The npm package version
// `YYYY.M.DD` derives from pyproject `YYYY.MM.DD.N` (N is the daily counter
// that doesn't ride into npm). So a wrapper at `2026.4.24` expects a Python
// CLI tagged `2026.4.24.X` for some X. If the installed version's
// year.month.day prefix doesn't match, surface a warning so users know
// to upgrade the Python package, not just the npm wrapper.
function checkVersionAlignment(installedVersion) {
  let wrapperVersion = "";
  try {
    wrapperVersion = require("../package.json").version || "";
  } catch {
    return;
  }
  if (!wrapperVersion || !installedVersion) return;
  // Compare year.month.day prefix
  const wrapperPrefix = wrapperVersion.split(".").slice(0, 3).join(".");
  const installedPrefix = installedVersion.split(".").slice(0, 3).join(".");
  if (wrapperPrefix !== installedPrefix) {
    process.stderr.write(
      `\nwarning: npm wrapper expects autosearch ${wrapperPrefix}.* but the ` +
        `installed Python CLI is ${installedVersion}.\n` +
        `Upgrade the Python package to match:\n` +
        `  pipx upgrade autosearch\n` +
        `  pip install --upgrade autosearch\n\n`,
    );
  }
}

function popFlag(...names) {
  for (const name of names) {
    const i = args.indexOf(name);
    if (i !== -1) {
      args.splice(i, 1);
      return true;
    }
  }
  return false;
}

function printWrapperHelp() {
  console.log(
    `autosearch-ai — npm wrapper for AutoSearch (Python package).\n\n` +
      `Usage:\n` +
      `  npx autosearch-ai             Launch autosearch (installs first if absent)\n` +
      `  npx autosearch-ai <args>      Forward args to the installed autosearch CLI\n` +
      `  npx autosearch-ai --help      Show this wrapper help (no install prompt)\n` +
      `  npx autosearch-ai --version   Show wrapper + installed autosearch version\n\n` +
      `Wrapper-only flags:\n` +
      `  --yes, -y     Skip the y/N install prompt for non-interactive automation\n\n` +
      `Install paths chosen by platform:\n` +
      `  macOS / Linux: ${INSTALL_SCRIPT} (via curl)\n` +
      `  Windows:       pipx install autosearch  (preferred)\n` +
      `                 or  py -3.12 -m pip install --user autosearch\n` +
      `                 see ${PYPI_PAGE}\n`,
  );
}

function printVersion() {
  let wrapperVersion = "unknown";
  try {
    wrapperVersion = require("../package.json").version;
  } catch {
    /* ignore */
  }
  console.log(`autosearch-ai (npm wrapper) ${wrapperVersion}`);
  if (hasAutosearch()) {
    try {
      const out = execSync("autosearch --version", { encoding: "utf8" });
      process.stdout.write(`autosearch (Python): ${out}`);
    } catch {
      console.log("autosearch (Python): present, but --version exited non-zero");
    }
  } else {
    console.log("autosearch (Python): not installed");
  }
}

function confirm(prompt) {
  return new Promise((resolve) => {
    if (!process.stdin.isTTY) {
      resolve(false);
      return;
    }
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stderr,
    });
    rl.question(prompt, (answer) => {
      rl.close();
      resolve(/^y(es)?$/i.test(answer.trim()));
    });
  });
}

function describeInstallStep() {
  if (isWindows()) {
    if (hasOnPath("pipx")) return `pipx install autosearch`;
    if (hasOnPath("py")) return `py -3.12 -m pip install --user autosearch`;
    if (hasOnPath("python")) return `python -m pip install --user autosearch`;
    return null;
  }
  return `curl -fsSL ${INSTALL_SCRIPT} | bash -s -- --no-init`;
}

function runInstall() {
  if (isWindows()) {
    if (hasOnPath("pipx")) {
      return spawnSync("pipx", ["install", "autosearch"], { stdio: "inherit" });
    }
    if (hasOnPath("py")) {
      return spawnSync(
        "py",
        ["-3.12", "-m", "pip", "install", "--user", "autosearch"],
        { stdio: "inherit" },
      );
    }
    if (hasOnPath("python")) {
      return spawnSync(
        "python",
        ["-m", "pip", "install", "--user", "autosearch"],
        { stdio: "inherit" },
      );
    }
    console.error(
      `\nNo Python installer found on Windows. Install one of:\n` +
        `  - pipx (recommended):  https://pipx.pypa.io/stable/installation/\n` +
        `  - Python 3.12+ from the Microsoft Store or python.org\n\n` +
        `Then re-run: npx autosearch-ai`,
    );
    return { status: 1 };
  }
  return spawnSync(
    "bash",
    ["-c", `curl -fsSL ${INSTALL_SCRIPT} | bash -s -- --no-init`],
    { stdio: "inherit" },
  );
}

async function main() {
  // Wrapper-only flags that must NOT trigger an install prompt — pop first
  // so they don't get forwarded to the autosearch CLI.
  if (popFlag("--help", "-h")) {
    printWrapperHelp();
    return;
  }
  if (popFlag("--version", "-V")) {
    const installedVersion = getInstalledAutosearchVersion();
    if (installedVersion !== null) {
      checkVersionAlignment(installedVersion);
    }
    printVersion();
    return;
  }

  const yes = popFlag("--yes", "-y");

  const installedVersion = getInstalledAutosearchVersion();
  if (installedVersion === null) {
    const installCmd = describeInstallStep();
    if (!yes) {
      const ok = await confirm(
        `\nautosearch is not installed.\n` +
          `This will install AutoSearch via:\n` +
          `  ${installCmd ?? "(no installer detected — see --help)"}\n` +
          `Proceed? [y/N] `,
      );
      if (!ok) {
        console.error(
          `\nAborted. To install non-interactively re-run with --yes,\n` +
            `or install AutoSearch directly via your package manager:\n` +
            `  pip install autosearch && autosearch init\n` +
            `  pipx install autosearch && autosearch init`,
        );
        process.exit(1);
      }
    }
    const result = runInstall();
    if (result.error?.code === "ENOENT") {
      printInstallerNotFoundHint(result.error);
      process.exit(1);
    }
    if ((result.status ?? 0) !== 0) {
      process.exit(result.status ?? 1);
    }
    prependHomeLocalBinToPath();
  } else {
    checkVersionAlignment(installedVersion);
  }

  const cmd = args.length > 0 ? args : ["init"];
  const result = spawnSync("autosearch", cmd, { stdio: "inherit" });
  if (result.error?.code === "ENOENT") {
    printAutosearchNotFoundHint(result.error);
    process.exit(1);
  }
  process.exit(result.status ?? 0);
}

main();
