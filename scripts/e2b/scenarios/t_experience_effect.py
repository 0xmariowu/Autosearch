"""Scenarios T1-T8: Experience layer effectiveness — patterns improve subsequent searches."""

from __future__ import annotations

import time
from typing import Any

from scripts.e2b.sandbox_runner import ScenarioResult, install_autosearch, run_python


def _clean_env(env: dict) -> dict:
    return {k: v for k, v in env.items() if k != "AUTOSEARCH_LLM_MODE"}


def _as_dict(result: Any) -> dict[str, Any]:
    return result if isinstance(result, dict) else {"ok": False, "raw_result": repr(result)}


async def _install_or_fail(
    sandbox_id: str, scenario_id: str, name: str, t0: float
) -> ScenarioResult | None:
    ok = await install_autosearch(sandbox_id)
    if ok:
        return None
    return ScenarioResult(
        scenario_id,
        "T",
        name,
        0,
        False,
        error="pip install failed",
        duration_s=time.monotonic() - t0,
    )


async def t1_experience_injected_in_rationale(sandbox_id: str, env: dict) -> ScenarioResult:
    """T1: Repeated winning patterns appear in the compact experience digest."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "T1", "experience_injected_in_rationale", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, asyncio, tempfile
from pathlib import Path
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event
try:
    from autosearch.skills.experience import get_experience_digest
except ImportError:
    from autosearch.skills.experience import load_experience_digest as get_experience_digest
from datetime import datetime, UTC

os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
from autosearch.mcp.server import create_server
from unittest.mock import patch

def compact_skill(skill, root):
    try:
        from autosearch.skills.experience import compact
        return compact(skill, _skills_root=root)
    except Exception:
        try:
            from autosearch.core.experience_compact import compact
            return compact(skill)
        except Exception:
            from autosearch.core.experience_compact import compact_skill as compact_path
            return compact_path(root / 'channels' / skill)

async def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        exp_mod._SKILLS_ROOT = root
        ch_dir = root / 'channels' / 'arxiv'
        ch_dir.mkdir(parents=True)

        for i in range(3):
            append_event('arxiv', {
                'skill': 'arxiv', 'query': 'transformer', 'outcome': 'success',
                'count_returned': 8, 'winning_pattern': 'use specific technical terms',
                'ts': datetime.now(UTC).isoformat()
            })

        compacted = compact_skill('arxiv', root)
        try:
            digest = get_experience_digest('arxiv')
        except TypeError:
            digest = get_experience_digest('arxiv', _skills_root=root)
        if digest is None:
            try:
                digest = get_experience_digest('arxiv', _skills_root=root)
            except TypeError:
                digest = ''
        has_pattern = 'use specific technical terms' in (digest or '')

        with patch('autosearch.mcp.server._build_channels', return_value=channels_list):
            create_server()

        print(json.dumps({'ok': has_pattern, 'has_pattern': has_pattern, 'compacted': bool(compacted), 'digest_len': len(digest or ''), 'digest_preview': (digest or '')[:200]}))

asyncio.run(main())
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    score = 100 if ok else (50 if int(result.get("digest_len", 0) or 0) > 0 else 0)
    return ScenarioResult(
        "T1",
        "T",
        "experience_injected_in_rationale",
        score=score,
        passed=ok,
        details=result,
        report_length=int(result.get("digest_len", 0) or 0),
        error=result.get("error", ""),
        duration_s=dur,
    )


async def t2_pattern_quality_threshold(sandbox_id: str, env: dict) -> ScenarioResult:
    """T2: One-off successes are not promoted, repeated successes are."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "T2", "pattern_quality_threshold", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, tempfile
from pathlib import Path
from datetime import datetime, UTC
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event
from autosearch.core.experience_compact import compact

def section(content, names):
    active = False
    lines = []
    for line in content.splitlines():
        if line.startswith('## '):
            heading = line.strip('# ').lower()
            active = any(name in heading for name in names)
            continue
        if active:
            lines.append(line)
    return '\\n'.join(lines)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    exp_mod._SKILLS_ROOT = root
    skill_dir = root / 'channels' / 'arxiv'
    skill_dir.mkdir(parents=True)

    single_pattern = 'single success should not promote'
    append_event('arxiv', {
        'skill': 'arxiv', 'query': 'one', 'outcome': 'success',
        'count_returned': 4, 'winning_pattern': single_pattern,
        'ts': datetime.now(UTC).isoformat(),
    })
    compact('arxiv')
    content_one = (skill_dir / 'experience.md').read_text(encoding='utf-8')
    positive_one = section(content_one, ['best patterns', 'active rules'])
    one_ok = single_pattern not in positive_one

    repeated_pattern = 'use exact benchmark terminology'
    for i in range(3):
        append_event('arxiv', {
            'skill': 'arxiv', 'query': f'three {i}', 'outcome': 'success',
            'count_returned': 5, 'winning_pattern': repeated_pattern,
            'ts': datetime.now(UTC).isoformat(),
        })
    compact('arxiv')
    content_three = (skill_dir / 'experience.md').read_text(encoding='utf-8')
    positive_three = section(content_three, ['best patterns', 'active rules'])
    three_ok = repeated_pattern in positive_three
    print(json.dumps({'ok': one_ok and three_ok, 'one_ok': one_ok, 'three_ok': three_ok, 'line_count': len(content_three.splitlines())}))
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok_count = int(bool(result.get("one_ok"))) + int(bool(result.get("three_ok")))
    return ScenarioResult(
        "T2",
        "T",
        "pattern_quality_threshold",
        score=100 if ok_count == 2 else (50 if ok_count == 1 else 0),
        passed=ok_count == 2,
        details=result,
        report_length=int(result.get("line_count", 0) or 0),
        error=result.get("error", ""),
        duration_s=dur,
    )


async def t3_failure_not_promoted(sandbox_id: str, env: dict) -> ScenarioResult:
    """T3: Failure modes are recorded as failures, not positive patterns."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "T3", "failure_not_promoted", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, tempfile
from pathlib import Path
from datetime import datetime, UTC
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event
from autosearch.core.experience_compact import compact

def section(content, names):
    active = False
    lines = []
    for line in content.splitlines():
        if line.startswith('## '):
            heading = line.strip('# ').lower()
            active = any(name in heading for name in names)
            continue
        if active:
            lines.append(line)
    return '\\n'.join(lines)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    exp_mod._SKILLS_ROOT = root
    skill_dir = root / 'channels' / 'arxiv'
    skill_dir.mkdir(parents=True)
    failure_mode = 'rate limited with sparse query'
    append_event('arxiv', {
        'skill': 'arxiv', 'query': 'bad query', 'outcome': 'failure',
        'count_returned': 0, 'winning_pattern': failure_mode,
        'failure_mode': failure_mode, 'ts': datetime.now(UTC).isoformat(),
    })
    compact('arxiv')
    content = (skill_dir / 'experience.md').read_text(encoding='utf-8')
    positive = section(content, ['best patterns', 'active rules'])
    failures = section(content, ['known failures', 'failure modes', 'failure'])
    has_failure = failure_mode in failures
    not_positive = failure_mode not in positive
    print(json.dumps({'ok': has_failure and not_positive, 'has_failure': has_failure, 'not_positive': not_positive, 'line_count': len(content.splitlines())}))
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    wrong_section = not bool(result.get("not_positive", True))
    return ScenarioResult(
        "T3",
        "T",
        "failure_not_promoted",
        score=100 if ok else (0 if wrong_section else 0),
        passed=ok,
        details=result,
        report_length=int(result.get("line_count", 0) or 0),
        error=result.get("error", ""),
        duration_s=dur,
    )


async def t4_experience_size_compliance(sandbox_id: str, env: dict) -> ScenarioResult:
    """T4: Compacted experience.md remains within the target size."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "T4", "experience_size_compliance", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, tempfile
from pathlib import Path
from datetime import datetime, UTC
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event
from autosearch.core.experience_compact import compact

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    exp_mod._SKILLS_ROOT = root
    skill_dir = root / 'channels' / 'arxiv'
    skill_dir.mkdir(parents=True)
    for i in range(50):
        append_event('arxiv', {
            'skill': 'arxiv', 'query': f'query {i}', 'outcome': 'success',
            'count_returned': 5, 'winning_pattern': f'pattern family {i % 12}',
            'good_query': f'good query {i % 20}', 'ts': datetime.now(UTC).isoformat(),
        })
    compact('arxiv')
    exp_md = skill_dir / 'experience.md'
    content = exp_md.read_text(encoding='utf-8') if exp_md.exists() else ''
    lines = len(content.splitlines())
    print(json.dumps({'ok': exp_md.exists() and lines <= 120, 'exists': exp_md.exists(), 'line_count': lines, 'length': len(content)}))
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    lines = int(result.get("line_count", 999) or 999)
    score = 100 if lines <= 120 else (60 if lines <= 200 else 0)
    return ScenarioResult(
        "T4",
        "T",
        "experience_size_compliance",
        score=score,
        passed=lines <= 120 and bool(result.get("exists")),
        details=result,
        report_length=lines,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def t5_multi_channel_independence(sandbox_id: str, env: dict) -> ScenarioResult:
    """T5: Per-channel experience digests remain independent."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "T5", "multi_channel_independence", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, tempfile
from pathlib import Path
from datetime import datetime, UTC
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event
from autosearch.core.experience_compact import compact

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    exp_mod._SKILLS_ROOT = root
    for skill in ['arxiv', 'hackernews']:
        (root / 'channels' / skill).mkdir(parents=True)

    for i in range(3):
        append_event('arxiv', {
            'skill': 'arxiv', 'query': f'arxiv {i}', 'outcome': 'success',
            'count_returned': 6, 'winning_pattern': 'arxiv exact title terms',
            'ts': datetime.now(UTC).isoformat(),
        })
        append_event('hackernews', {
            'skill': 'hackernews', 'query': f'hn {i}', 'outcome': 'success',
            'count_returned': 6, 'winning_pattern': 'hackernews product discussion terms',
            'ts': datetime.now(UTC).isoformat(),
        })

    compact('arxiv')
    compact('hackernews')
    arxiv_md = root / 'channels' / 'arxiv' / 'experience.md'
    hn_md = root / 'channels' / 'hackernews' / 'experience.md'
    arxiv_content = arxiv_md.read_text(encoding='utf-8') if arxiv_md.exists() else ''
    hn_content = hn_md.read_text(encoding='utf-8') if hn_md.exists() else ''
    no_cross = 'hackernews product discussion terms' not in arxiv_content and 'arxiv exact title terms' not in hn_content
    ok = arxiv_md.exists() and hn_md.exists() and arxiv_content != hn_content and no_cross
    print(json.dumps({'ok': ok, 'arxiv_exists': arxiv_md.exists(), 'hackernews_exists': hn_md.exists(), 'content_differs': arxiv_content != hn_content, 'no_cross': no_cross}))
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "T5",
        "T",
        "multi_channel_independence",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        error=result.get("error", ""),
        duration_s=dur,
    )


async def t6_experience_append_atomic(sandbox_id: str, env: dict) -> ScenarioResult:
    """T6: Experience append writes one valid JSON line per event."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "T6", "experience_append_atomic", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, tempfile
from pathlib import Path
from datetime import datetime, UTC
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    exp_mod._SKILLS_ROOT = root
    skill_dir = root / 'channels' / 'arxiv'
    skill_dir.mkdir(parents=True)
    for i in range(5):
        append_event('arxiv', {
            'skill': 'arxiv', 'query': f'query {i}', 'outcome': 'success',
            'count_returned': i, 'winning_pattern': f'pattern {i}',
            'ts': datetime.now(UTC).isoformat(),
        })
    patterns = skill_dir / 'experience' / 'patterns.jsonl'
    valid = 0
    expected_fields = True
    lines = patterns.read_text(encoding='utf-8').splitlines() if patterns.exists() else []
    for line in lines:
        try:
            payload = json.loads(line)
            valid += 1
            expected_fields = expected_fields and all(k in payload for k in ['skill', 'query', 'outcome', 'ts'])
        except json.JSONDecodeError:
            expected_fields = False
    ok = len(lines) == 5 and valid == 5 and expected_fields
    print(json.dumps({'ok': ok, 'line_count': len(lines), 'valid_json': valid, 'expected_fields': expected_fields}))
""",
        env=_clean_env(env),
        timeout=30,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "T6",
        "T",
        "experience_append_atomic",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        evidence_count=int(result.get("line_count", 0) or 0),
        error=result.get("error", ""),
        duration_s=dur,
    )


async def t7_failure_only_in_known_failures(sandbox_id: str, env: dict) -> ScenarioResult:
    """T7: A failure mode appears only in the failure section."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "T7", "failure_only_in_known_failures", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, tempfile
from pathlib import Path
from datetime import datetime, UTC
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event
from autosearch.core.experience_compact import compact

def sections(content):
    current = 'preamble'
    out = {current: []}
    for line in content.splitlines():
        if line.startswith('## '):
            current = line.strip('# ').lower()
            out.setdefault(current, [])
            continue
        out.setdefault(current, []).append(line)
    return {k: '\\n'.join(v) for k, v in out.items()}

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    exp_mod._SKILLS_ROOT = root
    skill_dir = root / 'channels' / 'arxiv'
    skill_dir.mkdir(parents=True)
    failure_mode = 'channel_timeout'
    append_event('arxiv', {
        'skill': 'arxiv', 'query': 'timeout query', 'outcome': 'failure',
        'count_returned': 0, 'failure_mode': failure_mode,
        'ts': datetime.now(UTC).isoformat(),
    })
    compact('arxiv')
    content = (skill_dir / 'experience.md').read_text(encoding='utf-8')
    parsed = sections(content)
    failure_sections = {k: v for k, v in parsed.items() if 'failure' in k}
    positive_sections = {k: v for k, v in parsed.items() if 'active rules' in k or 'best patterns' in k}
    in_failure = any(failure_mode in text for text in failure_sections.values())
    in_positive = any(failure_mode in text for text in positive_sections.values())
    ok = in_failure and not in_positive
    print(json.dumps({'ok': ok, 'in_failure': in_failure, 'in_positive': in_positive, 'sections': list(parsed.keys()), 'line_count': len(content.splitlines())}))
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    ok = bool(result.get("ok"))
    return ScenarioResult(
        "T7",
        "T",
        "failure_only_in_known_failures",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        report_length=int(result.get("line_count", 0) or 0),
        error=result.get("error", ""),
        duration_s=dur,
    )


async def t8_experience_compact_integration(sandbox_id: str, env: dict) -> ScenarioResult:
    """T8: Compacting mixed events preserves raw logs and bounded digest size."""
    t0 = time.monotonic()
    install_error = await _install_or_fail(sandbox_id, "T8", "experience_compact_integration", t0)
    if install_error:
        return install_error

    result, _ = await run_python(
        sandbox_id,
        """
import os, json, tempfile
from pathlib import Path
from datetime import datetime, UTC
from autosearch.core.channel_bootstrap import _build_channels
channels_list = _build_channels()
os.environ['AUTOSEARCH_LLM_MODE'] = 'dummy'
import autosearch.skills.experience as exp_mod
from autosearch.skills.experience import append_event
from autosearch.core.experience_compact import compact

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    exp_mod._SKILLS_ROOT = root
    skill_dir = root / 'channels' / 'arxiv'
    skill_dir.mkdir(parents=True)
    for i in range(12):
        event = {
            'skill': 'arxiv',
            'query': f'integration {i}',
            'outcome': 'success' if i % 4 != 0 else 'failure',
            'count_returned': 5 if i % 4 != 0 else 0,
            'ts': datetime.now(UTC).isoformat(),
        }
        if event['outcome'] == 'success':
            event['winning_pattern'] = 'integration repeated success pattern'
            event['good_query'] = f'integration good query {i % 3}'
        else:
            event['failure_mode'] = 'integration transient failure'
        append_event('arxiv', event)
    compacted = compact('arxiv')
    exp_md = skill_dir / 'experience.md'
    patterns = skill_dir / 'experience' / 'patterns.jsonl'
    content = exp_md.read_text(encoding='utf-8') if exp_md.exists() else ''
    lines = len(content.splitlines())
    raw_lines = len(patterns.read_text(encoding='utf-8').splitlines()) if patterns.exists() else 0
    ok = exp_md.exists() and len(content) > 0 and patterns.exists() and lines <= 120
    print(json.dumps({'ok': ok, 'compacted': bool(compacted), 'experience_exists': exp_md.exists(), 'patterns_exists': patterns.exists(), 'line_count': lines, 'raw_lines': raw_lines, 'length': len(content)}))
""",
        env=_clean_env(env),
        timeout=45,
    )
    dur = time.monotonic() - t0
    result = _as_dict(result)
    checks = [
        bool(result.get("experience_exists")),
        bool(result.get("patterns_exists")),
        int(result.get("line_count", 999) or 999) <= 120,
    ]
    ok = all(checks) and bool(result.get("ok"))
    return ScenarioResult(
        "T8",
        "T",
        "experience_compact_integration",
        score=100 if ok else 0,
        passed=ok,
        details=result,
        evidence_count=int(result.get("raw_lines", 0) or 0),
        report_length=int(result.get("line_count", 0) or 0),
        error=result.get("error", ""),
        duration_s=dur,
    )
