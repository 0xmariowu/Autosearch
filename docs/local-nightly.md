---
title: "Local Nightly Runner"
description: "Schedule the F101 baseline regression on your own machine via macOS launchd, cron, or manual invocation"
---

# Local Nightly Runner

`scripts/nightly-local.sh` drives the same F101 baseline regression that `.github/workflows/e2b-nightly.yml` runs, but locally — without uploading any keys to GitHub Actions secrets. It reads your LLM / E2B keys directly from `~/.config/ai-secrets.env`.

Use this when you want Gate 13 observation-period evidence (3 consecutive nightly greens) but don't want a GitHub Actions footprint.

## One-off manual run

```bash
./scripts/nightly-local.sh
```

Outputs land in `reports/nightly-$(date -u +%Y-%m-%d)/`. The `summary.md` in that directory is what the release gate observation period evaluates.

Override defaults via env vars:

| Variable | Default | Purpose |
|---|---|---|
| `AUTOSEARCH_PARALLEL` | `15` | Sandbox pool size (cap is 15 per `~/.config/ai-secrets.env` quota) |
| `AUTOSEARCH_SECRETS_FILE` | `~/.config/ai-secrets.env` | Where the orchestrator reads API keys |

## macOS launchd (daily schedule)

Drop this plist at `~/Library/LaunchAgents/com.autosearch.nightly.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.autosearch.nightly</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-lc</string>
        <string>cd ~/Projects/autosearch && ./scripts/nightly-local.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>3</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/autosearch-nightly.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/autosearch-nightly.stderr.log</string>
    <key>RunAtLoad</key>
    <false/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
```

Adjust the repo path (`cd ~/Projects/autosearch`) if you cloned elsewhere. Then:

```bash
launchctl load ~/Library/LaunchAgents/com.autosearch.nightly.plist
launchctl start com.autosearch.nightly      # immediate smoke run
```

To unload later: `launchctl unload ~/Library/LaunchAgents/com.autosearch.nightly.plist`.

Check run logs:

```bash
tail -f /tmp/autosearch-nightly.stderr.log     # orchestrator progress
ls -lt reports/nightly-*/                       # produced reports
```

## Linux systemd (optional)

For a Linux box (personal workstation, not CI runner), drop a unit + timer in `~/.config/systemd/user/`:

```ini
# ~/.config/systemd/user/autosearch-nightly.service
[Unit]
Description=AutoSearch F101 nightly regression

[Service]
Type=oneshot
WorkingDirectory=%h/Projects/autosearch
ExecStart=%h/Projects/autosearch/scripts/nightly-local.sh
StandardOutput=append:/tmp/autosearch-nightly.stdout.log
StandardError=append:/tmp/autosearch-nightly.stderr.log
```

```ini
# ~/.config/systemd/user/autosearch-nightly.timer
[Unit]
Description=Run AutoSearch F101 nightly regression daily

[Timer]
OnCalendar=*-*-* 03:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

Activate:

```bash
systemctl --user daemon-reload
systemctl --user enable --now autosearch-nightly.timer
systemctl --user list-timers autosearch-nightly.timer
```

## Comparison with the GitHub Actions workflow

| Concern | Local (launchd / systemd) | GitHub Actions (`e2b-nightly.yml`) |
|---|---|---|
| Secret sync | Reads `~/.config/ai-secrets.env` in place | Requires `gh secret set` for each key |
| Keeps running if your machine is off | No — scheduler fires only when the machine is on | Yes — runs on GitHub's runners |
| Failure notification | stderr log file | Auto-opens a GitHub issue via `peter-evans/create-issue-from-file` |
| Cost | Just E2B sandbox minutes + LLM calls | Same + GH Actions minutes (free within quota) |
| Good fit | Solo maintainer, always-on workstation | Team, intermittent developer availability |

They're not mutually exclusive — you can run both.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `error: no orchestrator venv found` | `scripts/e2b/` venv never created and shared `~/.claude/scripts/e2b/.venv` is missing | `uv venv scripts/e2b/.venv --python 3.12 && uv pip install --python scripts/e2b/.venv/bin/python e2b e2b-code-interpreter rich pyyaml` |
| `error: secrets file not readable` | `~/.config/ai-secrets.env` missing or wrong perms | Create the file with `chmod 600`; populate with `E2B_API_KEY=...`, `ANTHROPIC_API_KEY=...` lines |
| launchd starts but exits 78 / 126 | `PATH` inside launchd is minimal by default | Keep the `EnvironmentVariables.PATH` stanza above; adjust for your own `uv` install location if needed |
| No reports produced, no error | Scheduler fired while machine asleep | launchd uses `StartCalendarInterval`; wake-on-LAN or `caffeinate` around the hour if you suspend the machine at night |

## Where to go next

- F101 matrix definition: [`tests/e2b/matrix.yaml`](../tests/e2b/matrix.yaml)
- Release gate definitions: `../RELEASE-READINESS.md` (per-run, under `reports/`)
- Orchestrator internals: [`scripts/e2b/README.md`](../scripts/e2b/README.md) (post PR #196)
