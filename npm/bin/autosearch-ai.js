#!/usr/bin/env node
"use strict";

const { execSync, spawnSync } = require("child_process");
const args = process.argv.slice(2);

const INSTALL_SCRIPT =
  "https://raw.githubusercontent.com/0xmariowu/Autosearch/main/scripts/install.sh";

function hasAutosearch() {
  try {
    execSync("autosearch --version", { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

if (!hasAutosearch()) {
  // Download and run install.sh — handles uv/pipx/pip + shows init screen
  const result = spawnSync("bash", ["-c", `curl -fsSL ${INSTALL_SCRIPT} | bash`], {
    stdio: "inherit",
  });
  process.exit(result.status ?? 0);
}

const cmd = args.length > 0 ? args : ["init"];
const result = spawnSync("autosearch", cmd, { stdio: "inherit" });
process.exit(result.status ?? 0);
