#!/usr/bin/env node
"use strict";

const { execSync, spawnSync } = require("child_process");
const args = process.argv.slice(2);

function hasAutosearch() {
  try {
    execSync("autosearch --version", { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

if (!hasAutosearch()) {
  console.log("");
  console.log("AutoSearch is not installed yet. Run:");
  console.log("");
  console.log("  curl -fsSL https://raw.githubusercontent.com/0xmariowu/Autosearch/main/scripts/install.sh | bash");
  console.log("");
  process.exit(0);
}

const cmd = args.length > 0 ? args : ["init"];
const result = spawnSync("autosearch", cmd, { stdio: "inherit" });
process.exit(result.status ?? 0);
