#!/usr/bin/env node
"use strict";

const { execSync, spawnSync } = require("child_process");
const args = process.argv.slice(2);
const isPostinstall = process.env.npm_lifecycle_event === "postinstall";

function hasAutosearch() {
  try {
    execSync("autosearch --version", { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

// Find Python 3.12+ and return the executable path, or null if not found.
function findPython312() {
  const candidates = ["python3.13", "python3.12", "python3", "python"];
  for (const cmd of candidates) {
    try {
      const out = execSync(`${cmd} -c "import sys; print(sys.version_info[:2])"`, {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      }).trim();
      const match = out.match(/\((\d+),\s*(\d+)\)/);
      if (match && parseInt(match[1]) === 3 && parseInt(match[2]) >= 12) {
        return cmd;
      }
    } catch {
      // try next
    }
  }
  return null;
}

function install(python) {
  console.log("Installing autosearch...");
  // Use the detected Python 3.12+ to run pip, falling back to pip3/pip
  const pipCmds = [
    [python, ["-m", "pip", "install", "--quiet", "--upgrade", "autosearch"]],
    ["pip3", ["install", "--quiet", "--upgrade", "autosearch"]],
    ["pip", ["install", "--quiet", "--upgrade", "autosearch"]],
  ];
  for (const [cmd, pipArgs] of pipCmds) {
    const result = spawnSync(cmd, pipArgs, { stdio: "inherit" });
    if (result.status === 0) return true;
  }
  return false;
}

const python = findPython312();

if (!python) {
  if (isPostinstall) {
    console.log("\nautosearch-ai installed. To complete setup, install Python 3.12+ then run: autosearch-ai");
    process.exit(0);
  }
  console.error("Python 3.12+ not found. Install it first: https://python.org");
  process.exit(1);
}

if (!hasAutosearch()) {
  const ok = install(python);
  if (!ok) {
    if (isPostinstall) {
      console.log("\nautosearch-ai installed. To complete setup, run: autosearch-ai");
      console.log("(pip install autosearch failed — ensure Python 3.12+ pip is working)");
      process.exit(0);
    }
    console.error("pip install failed. Try manually: pip install autosearch");
    process.exit(1);
  }
}

const cmd = args.length > 0 ? args : ["init"];
const result = spawnSync("autosearch", cmd, { stdio: "inherit" });
process.exit(result.status ?? 0);
