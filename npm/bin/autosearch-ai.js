#!/usr/bin/env node
"use strict";

// Plan §P1-8: this launcher must NEVER be triggered by `npm install` (the
// postinstall hook is removed in package.json). It runs only when the user
// types `npx autosearch-ai` or invokes the installed binary explicitly. Even
// then, an unattended remote `curl | bash` requires explicit confirmation —
// either an interactive y/N prompt or `--yes` / `-y` on the command line.

const { execSync, spawnSync } = require("child_process");
const readline = require("readline");

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

function popFlag(name) {
  const i = args.indexOf(name);
  if (i === -1) return false;
  args.splice(i, 1);
  return true;
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

async function main() {
  const yes = popFlag("--yes") || popFlag("-y");

  if (!hasAutosearch()) {
    if (!yes) {
      const ok = await confirm(
        `\nautosearch is not installed.\n` +
          `This will download and execute a remote install script:\n` +
          `  ${INSTALL_SCRIPT}\n` +
          `Proceed? [y/N] `,
      );
      if (!ok) {
        console.error(
          `\nAborted. To install non-interactively re-run with --yes,\n` +
            `or install AutoSearch directly via your package manager:\n` +
            `  pip install autosearch && autosearch init\n` +
            `  pipx install autosearch && autosearch init\n` +
            `  curl -fsSL ${INSTALL_SCRIPT} | bash`,
        );
        process.exit(1);
      }
    }
    const result = spawnSync(
      "bash",
      ["-c", `curl -fsSL ${INSTALL_SCRIPT} | bash`],
      { stdio: "inherit" },
    );
    process.exit(result.status ?? 0);
  }

  const cmd = args.length > 0 ? args : ["init"];
  const result = spawnSync("autosearch", cmd, { stdio: "inherit" });
  process.exit(result.status ?? 0);
}

main();
