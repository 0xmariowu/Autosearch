#!/usr/bin/env node
"use strict";

const { execSync, spawnSync } = require("child_process");
const args = process.argv.slice(2);

function hasPip() {
  for (const cmd of ["pip", "pip3"]) {
    try {
      execSync(`${cmd} --version`, { stdio: "ignore" });
      return cmd;
    } catch {}
  }
  return null;
}

function hasAutosearch() {
  try {
    execSync("autosearch --version", { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function install(pip) {
  console.log("Installing autosearch...");
  const result = spawnSync(pip, ["install", "--quiet", "--upgrade", "autosearch"], {
    stdio: "inherit",
  });
  if (result.status !== 0) {
    console.error("pip install failed. Try: pip install autosearch");
    process.exit(1);
  }
}

const pip = hasPip();
if (!pip) {
  console.error("Python pip not found. Install Python 3.12+ first: https://python.org");
  process.exit(1);
}

if (!hasAutosearch()) {
  install(pip);
}

const cmd = args.length > 0 ? args : ["init"];
const result = spawnSync("autosearch", cmd, { stdio: "inherit" });
process.exit(result.status ?? 0);
