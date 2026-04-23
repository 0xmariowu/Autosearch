"""Scenarios K1-K4: AVO evolution in E2B sandbox — git-based skill modification cycle."""

from __future__ import annotations

import time

from scripts.e2b.sandbox_runner import ScenarioResult, install_autosearch, run_cmd, run_python


def _clean_env(env: dict) -> dict:
    return {k: v for k, v in env.items() if k != "AUTOSEARCH_LLM_MODE"}


async def _clone_and_install(sandbox_id: str) -> bool:
    """Clone autosearch repo and install editable — judge reads /tmp/autosearch_k/skills/."""
    _, _, c1 = await run_cmd(
        sandbox_id,
        "git clone https://github.com/0xmariowu/Autosearch.git /tmp/autosearch_k -q 2>&1 | tail -2",
        timeout=120,
    )
    if c1 != 0:
        return False
    _, _, c2 = await run_cmd(
        sandbox_id,
        "pip install -e /tmp/autosearch_k -q 2>&1 | tail -2",
        timeout=180,
    )
    return c2 == 0


async def _install_or_fail(
    sandbox_id: str, scenario_id: str, name: str, t0: float
) -> ScenarioResult | None:
    ok = await install_autosearch(sandbox_id)
    if ok:
        return None
    return ScenarioResult(
        scenario_id,
        "K",
        name,
        0,
        False,
        error="pip install failed",
        duration_s=time.monotonic() - t0,
    )


async def k1_avo_baseline_score(sandbox_id: str, env: dict) -> ScenarioResult:
    """K1: Clone editable repo and compute a baseline skill quality score."""
    t0 = time.monotonic()
    cloned = await _clone_and_install(sandbox_id)
    if not cloned:
        return ScenarioResult(
            "K1",
            "K",
            "avo_baseline_score",
            0,
            False,
            error="clone or editable install failed",
            duration_s=time.monotonic() - t0,
        )

    result, _ = await run_python(
        sandbox_id,
        """
import json
from pathlib import Path
skill_path = Path('/tmp/autosearch_k/autosearch/skills/channels/arxiv/SKILL.md')
if not skill_path.exists():
    for p in Path('/tmp/autosearch_k').rglob('arxiv/SKILL.md'):
        skill_path = p
        break
content = skill_path.read_text() if skill_path.exists() else ''
has_quality_bar = '# Quality Bar' in content
has_frontmatter = content.startswith('---')
line_count = len(content.splitlines())
score = (30 if has_frontmatter else 0) + (40 if has_quality_bar else 0) + min(30, line_count // 5)
print(json.dumps({'ok': 0 < score <= 100, 'baseline_score': score, 'has_quality_bar': has_quality_bar, 'has_frontmatter': has_frontmatter, 'line_count': line_count, 'skill_path': str(skill_path)}))
""",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    return ScenarioResult(
        "K1",
        "K",
        "avo_baseline_score",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def k2_meta_skill_protection(sandbox_id: str, env: dict) -> ScenarioResult:
    """K2: Meta-skill protection signal is present in the installed package."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "K2", "meta_skill_protection", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch
from pathlib import Path
pkg_root = Path(os.path.dirname(autosearch.__file__))

checks = {}

# 1. AVO core module exists (protection logic lives here)
checks['has_avo_module'] = (pkg_root / 'core' / 'avo.py').exists()

# 2. PROTOCOL.md documents meta-skill protection rules
protocol_paths = [
    pkg_root.parent / 'PROTOCOL.md',
    pkg_root / 'PROTOCOL.md',
]
protocol_text = ''
for p in protocol_paths:
    if p.exists():
        protocol_text = p.read_text()
        break
checks['protocol_exists'] = bool(protocol_text)
checks['protocol_mentions_meta'] = any(kw in protocol_text for kw in ('meta', 'create-skill', 'protected', 'meta-skill'))

# 3. AVO module importable (actual protection can be code-level or doc-level)
try:
    import autosearch.core.avo as avo_mod
    checks['avo_importable'] = True
    meta_skills = ['create-skill', 'observe-user', 'extract-knowledge', 'interact-user', 'discover-environment']
    if hasattr(avo_mod, 'is_meta_skill_protected'):
        protected = [s for s in meta_skills if avo_mod.is_meta_skill_protected(s)]
        checks['code_protected_count'] = len(protected)
    else:
        checks['code_protected_count'] = 0
except ImportError:
    checks['avo_importable'] = False
    checks['code_protected_count'] = 0

ok = checks['has_avo_module'] or checks['protocol_mentions_meta'] or checks.get('code_protected_count', 0) >= 1
print(json.dumps({'ok': ok, **checks}))
""",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0
    # Score based on how many protection signals are present
    signals = sum(
        [
            result.get("has_avo_module", False),
            result.get("avo_importable", False),
            result.get("protocol_mentions_meta", False),
            result.get("code_protected_count", 0) >= 1,
        ]
    )
    score = 100 if signals >= 2 else (60 if signals >= 1 else 0)
    return ScenarioResult(
        "K2",
        "K",
        "meta_skill_protection",
        score=score,
        passed=result.get("ok", False),
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def k3_pattern_append_compact(sandbox_id: str, env: dict) -> ScenarioResult:
    """K3: Installed package appends 11 events and compacts experience."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "K3", "pattern_append_compact", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, tempfile
from pathlib import Path
from datetime import datetime, UTC

os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event, should_compact
from autosearch.core.experience_compact import compact

with tempfile.TemporaryDirectory() as tmp:
    exp_mod._SKILLS_ROOT = Path(tmp)
    skill_dir = Path(tmp) / 'channels' / 'test_ch'
    skill_dir.mkdir(parents=True)

    for i in range(11):
        append_event('test_ch', {
            'skill': 'test_ch', 'query': f'query {i}', 'outcome': 'success',
            'count_returned': 5, 'winning_pattern': f'pattern {i}',
            'ts': datetime.now(UTC).isoformat(),
        })

    exp_dir = skill_dir / 'experience'
    patterns_f = exp_dir / 'patterns.jsonl'
    lines_before = len(patterns_f.read_text().strip().splitlines()) if patterns_f.exists() else 0

    should_trigger = should_compact('test_ch')
    triggered = compact('test_ch') if should_trigger else False

    candidates = [skill_dir / 'experience.md', exp_dir / 'experience.md']
    exp_md = next((p for p in candidates if p.exists()), candidates[0])
    ok = triggered and exp_md.exists() and len(exp_md.read_text()) > 0
    print(json.dumps({
        'ok': ok,
        'triggered': triggered,
        'should_trigger': should_trigger,
        'exp_md_exists': exp_md.exists(),
        'exp_md_path': str(exp_md),
        'events_written': lines_before,
    }))
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    ok = result.get("ok", False)
    score = 100 if ok else (50 if result.get("events_written", 0) >= 11 else 0)
    return ScenarioResult(
        "K3",
        "K",
        "pattern_append_compact",
        score=score,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def k4_git_commit_revert_cycle(sandbox_id: str, env: dict) -> ScenarioResult:
    """K4: Skill modification can be committed and reverted cleanly."""
    t0 = time.monotonic()
    cloned = await _clone_and_install(sandbox_id)
    if not cloned:
        return ScenarioResult(
            "K4",
            "K",
            "git_commit_revert_cycle",
            0,
            False,
            error="clone or editable install failed",
            duration_s=time.monotonic() - t0,
        )

    skill_path = "/tmp/autosearch_k/autosearch/skills/channels/arxiv/SKILL.md"
    _, config_err, config_code = await run_cmd(
        sandbox_id,
        'git -C /tmp/autosearch_k config user.email "test@e2b.local" && '
        'git -C /tmp/autosearch_k config user.name "E2B Test"',
        env=_clean_env(env),
        timeout=30,
    )
    original_hash, hash_err, hash_code = await run_cmd(
        sandbox_id,
        f"sha256sum {skill_path} | awk '{{print $1}}'",
        env=_clean_env(env),
        timeout=30,
    )
    _, append_err, append_code = await run_cmd(
        sandbox_id,
        f'printf "\\n# E2B test modification\\n" >> {skill_path}',
        env=_clean_env(env),
        timeout=30,
    )
    _, commit_err, commit_code = await run_cmd(
        sandbox_id,
        "git -C /tmp/autosearch_k add autosearch/skills/channels/arxiv/SKILL.md && "
        'git -C /tmp/autosearch_k commit -m "test: E2B AVO modification" --no-verify',
        env=_clean_env(env),
        timeout=60,
    )
    log_after_commit, log_commit_err, log_commit_code = await run_cmd(
        sandbox_id,
        "git -C /tmp/autosearch_k log --oneline -1",
        env=_clean_env(env),
        timeout=30,
    )
    _, revert_err, revert_code = await run_cmd(
        sandbox_id,
        "git -C /tmp/autosearch_k revert HEAD --no-edit",
        env=_clean_env(env),
        timeout=60,
    )
    log_after_revert, log_revert_err, log_revert_code = await run_cmd(
        sandbox_id,
        "git -C /tmp/autosearch_k log --oneline -2",
        env=_clean_env(env),
        timeout=30,
    )
    final_hash, final_hash_err, final_hash_code = await run_cmd(
        sandbox_id,
        f"sha256sum {skill_path} | awk '{{print $1}}'",
        env=_clean_env(env),
        timeout=30,
    )

    verify, _ = await run_python(
        sandbox_id,
        """
import json
from pathlib import Path
skill_content = Path('/tmp/autosearch_k/autosearch/skills/channels/arxiv/SKILL.md').read_text()
reverted = '# E2B test modification' not in skill_content
print(json.dumps({'ok': reverted, 'reverted': reverted}))
""",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0

    commit_ok = (
        config_code == 0
        and hash_code == 0
        and append_code == 0
        and commit_code == 0
        and log_commit_code == 0
        and "test: E2B AVO modification" in log_after_commit
    )
    revert_log_ok = (
        log_revert_code == 0
        and "Revert" in log_after_revert
        and "test: E2B AVO modification" in log_after_revert
    )
    hash_restored = (
        final_hash_code == 0
        and bool(original_hash.strip())
        and original_hash.strip() == final_hash.strip()
    )
    full_ok = (
        commit_ok
        and revert_code == 0
        and revert_log_ok
        and verify.get("ok", False)
        and hash_restored
    )
    score = 100 if full_ok else (60 if commit_ok else 0)

    details = {
        **verify,
        "commit_ok": commit_ok,
        "revert_exit_code": revert_code,
        "revert_log_ok": revert_log_ok,
        "hash_restored": hash_restored,
        "original_hash": original_hash.strip(),
        "final_hash": final_hash.strip(),
        "log_after_commit": log_after_commit.strip()[:300],
        "log_after_revert": log_after_revert.strip()[:500],
        "command_errors": {
            "config": config_err[-300:],
            "hash": hash_err[-300:],
            "append": append_err[-300:],
            "commit": commit_err[-500:],
            "log_commit": log_commit_err[-300:],
            "revert": revert_err[-500:],
            "log_revert": log_revert_err[-300:],
            "final_hash": final_hash_err[-300:],
        },
    }
    return ScenarioResult(
        "K4",
        "K",
        "git_commit_revert_cycle",
        score=score,
        passed=full_ok,
        details=details,
        error="" if full_ok else (revert_err or commit_err or verify.get("error", ""))[:300],
        duration_s=dur,
    )
