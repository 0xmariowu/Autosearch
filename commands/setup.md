---
description: "Set up AutoSearch dependencies (Python venv + packages)"
user-invocable: true
---

# AutoSearch Setup

Install AutoSearch dependencies into a dedicated Python virtual environment.

## Steps

1. Check Python 3.11+ is available:
```bash
python3 --version
```
If version < 3.11, tell the user to install Python 3.11+.

2. Run the setup script:
```bash
bash ${CLAUDE_SKILL_DIR}/../scripts/setup.sh
```

3. Verify installation:
```bash
$HOME/.autosearch/venv/bin/python -c "import ddgs; import httpx; print('AutoSearch dependencies OK')"
```

4. Test channel loading:
```bash
PYTHONPATH=${CLAUDE_SKILL_DIR}/.. $HOME/.autosearch/venv/bin/python -c "from channels import load_channels; ch = load_channels(); print(f'{len(ch)} channels loaded')"
```

5. Report results to user:
- If all steps pass: "AutoSearch setup complete! Run /autosearch to start researching."
- If any step fails: show the error and suggest fixes.
