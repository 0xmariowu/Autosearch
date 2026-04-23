"""Generate human-readable Markdown report from E2B test results."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scripts.e2b.sandbox_runner import ScenarioResult


_CATEGORY_NAMES = {
    "A": "Infrastructure",
    "B": "English Tech Search",
    "C": "Chinese UGC",
    "D": "Academic / Specialist",
    "E": "Clarify Flow",
    "F": "Parallel Search",
    "G": "Full Report",
    "H": "Install Diversity",
    "I": "Per-Channel Quality",
    "J": "Error & Edge Cases",
    "K": "AVO Evolution",
    "L": "Report Quality",
}

_READINESS_EMOJI = {"READY": "🟢", "BETA": "🟡", "NOT_READY": "🔴"}


def render(results: list[ScenarioResult], summary: dict, output_dir: Path) -> str:
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    readiness = summary["readiness"]
    emoji = _READINESS_EMOJI.get(readiness, "⚪")

    lines += [
        "# AutoSearch E2B 综合测试报告",
        "",
        f"> 生成时间：{now}",
        "",
        "## 总结",
        "",
        "| 指标 | 数值 |",
        "|---|---|",
        f"| 总体得分 | **{summary['overall_score']}/100** |",
        f"| v1.0 就绪 | {emoji} **{readiness}** |",
        f"| 通过场景 | {summary['passed']}/{summary['total']} ({summary['pass_rate']}%) |",
        f"| 收集证据总数 | {summary['total_evidence']} 条 |",
        f"| 报告总字符 | {summary['total_report_chars']} 字 |",
        "",
        "**就绪判断标准**：≥80分 = READY（无保留发布）/ 60-80分 = BETA / <60分 = 需修复",
        "",
        "## 各类别得分",
        "",
        "| 类别 | 名称 | 得分 |",
        "|---|---|---|",
    ]

    for cat, score in sorted(summary["category_scores"].items()):
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        lines.append(f"| {cat} | {_CATEGORY_NAMES.get(cat, cat)} | {bar} {score}/100 |")

    lines += ["", "## 场景详情", ""]

    by_cat: dict[str, list[ScenarioResult]] = {}
    for r in results:
        if r.category == "W":
            continue
        by_cat.setdefault(r.category, []).append(r)

    for cat in sorted(by_cat):
        lines += [f"### 类别 {cat} — {_CATEGORY_NAMES.get(cat, cat)}", ""]
        for r in sorted(by_cat[cat], key=lambda x: x.scenario_id):
            status = "✅" if r.passed else "❌"
            lines.append(
                f"**{r.scenario_id}: {r.name}** {status} — {r.score}/100 — {r.duration_s:.1f}s"
            )
            if r.evidence_count:
                lines.append(f"  - 证据数：{r.evidence_count}")
            if r.report_length:
                lines.append(f"  - 报告长度：{r.report_length} 字符")
            if r.error:
                lines.append(f"  - ⚠️ 错误：`{r.error[:120]}`")
            # Notable details
            details = r.details
            if "pubmed_ok" in details:
                lines.append(f"  - PubMed 新渠道：{'✅' if details['pubmed_ok'] else '❌'}")
            if "dockerhub_available" in details:
                lines.append(
                    f"  - DockerHub 新渠道：{'✅' if details.get('dockerhub_available') else '❌'}"
                )
            if "graceful_fail" in details and details["graceful_fail"]:
                lines.append("  - ℹ️ 渠道不可用（graceful fail，非 crash）")
            if "synthesis_used_llm" in details:
                lines.append(
                    f"  - LLM 合成：{'✅ OpenRouter' if details['synthesis_used_llm'] else '⚠️ 无 key，跳过'}"
                )
            lines.append("")

    if summary["failures"]:
        lines += ["## 失败场景", ""]
        for f in summary["failures"]:
            lines.append(f"- **{f['id']} {f['name']}** (score={f['score']}): {f['error']}")
        lines.append("")

    if summary.get("bonus_total", 0) > 0:
        lines += [
            "",
            "## Windows Emulation Bonus",
            "",
            f"*Crash-safety only — not counted in score. {summary['bonus_passed']}/{summary['bonus_total']} passed.*",
            "",
            "| ID | Name | Passed |",
            "|---|---|---|",
        ]
        for br in summary.get("bonus_results", []):
            lines.append(f"| {br['scenario_id']} | {br['name']} | {'✅' if br['passed'] else '❌'} |")
        lines.append("")

    lines += [
        "## 结论",
        "",
        _conclusion(summary),
        "",
    ]

    report = "\n".join(lines)
    (output_dir / "summary.md").write_text(report, encoding="utf-8")
    return report


def _conclusion(summary: dict) -> str:
    r = summary["readiness"]
    score = summary["overall_score"]
    cat = summary["category_scores"]

    if r == "READY":
        return (
            f"**总体得分 {score}/100，达到 READY 标准（≥80）。**\n\n"
            f"AutoSearch v1.0 可以发布。所有核心渠道正常，报告质量达标，追问流程正确。"
        )
    if r == "BETA":
        weak = [f"类别{k}({v}分)" for k, v in cat.items() if v < 60]
        return (
            f"**总体得分 {score}/100，达到 BETA 标准（60-80）。**\n\n"
            f"建议以 v1.0-beta 发布，说明已知限制。弱项：{', '.join(weak) or '无'}。\n"
            f"加强这些类别后可打 v1.0 正式版。"
        )
    weak = [f"类别{k}({v}分)" for k, v in cat.items() if v < 60]
    return (
        f"**总体得分 {score}/100，未达 BETA 标准。**\n\n"
        f"需要修复后再发布。失败集中在：{', '.join(weak) or '多个类别'}。"
    )
