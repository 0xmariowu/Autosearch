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

function checkPython() {
  try {
    execSync("python3 --version", { stdio: "ignore" });
    return true;
  } catch {
    try {
      execSync("python --version", { stdio: "ignore" });
      return true;
    } catch {
      return false;
    }
  }
}

function install() {
  console.log("Installing autosearch...");
  // pip3 first, then pip — both hardcoded, not from user input
  let result = spawnSync("pip3", ["install", "--quiet", "--upgrade", "autosearch"], {
    stdio: "inherit",
  });
  if (result.status !== 0) {
    result = spawnSync("pip", ["install", "--quiet", "--upgrade", "autosearch"], {
      stdio: "inherit",
    });
  }
  return result.status === 0;
}

if (!checkPython()) {
  if (isPostinstall) {
    console.log("\nautosearch-ai installed. To complete setup, install Python 3.12+ then run: autosearch-ai");
    process.exit(0);
  }
  console.error("Python not found. Install Python 3.12+ first: https://python.org");
  process.exit(1);
}

if (!hasAutosearch()) {
  const ok = install();
  if (!ok) {
    if (isPostinstall) {
      console.log("\nautosearch-ai installed. To complete setup, run: autosearch-ai");
      console.log("(requires Python 3.12+: pip install autosearch)");
      process.exit(0);
    }
    console.error("pip install failed. Try manually: pip install autosearch");
    process.exit(1);
  }
}

const cmd = args.length > 0 ? args : ["init"];
const result = spawnSync("autosearch", cmd, { stdio: "inherit" });
process.exit(result.status ?? 0);
