"""AI-driven search orchestration using capabilities as tools."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

from capabilities import dispatch, load_manifest, manifest_json, manifest_text


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_ORCHESTRATOR_MODEL = "google/gemini-2.5-flash"


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Convert capability tool definitions to OpenAI function-calling format."""
    openai_tools = []
    for tool in tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get(
                        "input_schema", {"type": "object", "properties": {}}
                    ),
                },
            }
        )
    return openai_tools


def _call_llm(messages: list[dict], tools: list[dict], model: str = "") -> dict:
    """Call OpenRouter API with tool-use. Pattern from goal_editor.py."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    if not model:
        model = os.environ.get(
            "OPENROUTER_ORCHESTRATOR_MODEL", DEFAULT_ORCHESTRATOR_MODEL
        )

    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 2048,
            "messages": messages,
            "tools": _to_openai_tools(tools),
            "temperature": 0.3,
        }
    ).encode()

    req = urllib.request.Request(
        OPENROUTER_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _extract_tool_call(response: dict) -> dict | None:
    """Extract first tool call from OpenRouter/OpenAI response."""
    message = response.get("choices", [{}])[0].get("message", {})
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return None
    tc = tool_calls[0]
    func = tc.get("function", {})
    try:
        args = json.loads(func.get("arguments", "{}"))
    except (json.JSONDecodeError, TypeError):
        args = {}
    return {
        "id": tc.get("id", ""),
        "name": func.get("name", ""),
        "input": args,
    }


def _extract_text(response: dict) -> str:
    """Extract text content from OpenRouter/OpenAI response."""
    message = response.get("choices", [{}])[0].get("message", {})
    return str(message.get("content") or "")


def _summarize_result(result: Any, max_items: int = 8) -> str:
    """Summarize capability result for LLM context (keep it short to save tokens)."""
    if isinstance(result, list):
        count = len(result)
        sample = result[:max_items]
        summary_items = []
        for item in sample:
            if isinstance(item, dict):
                title = item.get("title", item.get("query", ""))
                url = item.get("url", "")
                summary_items.append(f"  - {title} ({url})" if url else f"  - {title}")
            else:
                summary_items.append(f"  - {str(item)[:100]}")
        text = "\n".join(summary_items)
        return f"Returned {count} items:\n{text}" + (
            f"\n  ... and {count - max_items} more" if count > max_items else ""
        )
    elif isinstance(result, dict):
        # Special handling for health reports — summarize source statuses
        if "sources" in result and isinstance(result["sources"], dict):
            lines = ["Provider health report:"]
            for name, info in result["sources"].items():
                if isinstance(info, dict):
                    status = info.get("status", "?")
                    msg = str(info.get("message", ""))[:60]
                    lines.append(f"  {name}: {status} — {msg}")
                else:
                    lines.append(f"  {name}: {info}")
            return "\n".join(lines)
        return json.dumps(result, indent=2, default=str)[:800]
    return str(result)[:500]


def run_task(
    task_spec: str,
    *,
    max_steps: int = 50,
    budget: dict[str, Any] | None = None,
    mode: str = "balanced",
    model: str = "",
    dry_run: bool = False,
    task_id: str = "",
    resume_from: str = "",
    system_prompt: str = "",
) -> dict[str, Any]:
    """Run an AI-orchestrated search task.

    Args:
        task_spec: Natural language description of what to find
        max_steps: Maximum capability calls before forcing completion
        budget: Optional budget constraints (not yet implemented)
        mode: Research mode (speed/balanced/deep)
        model: LLM model override
        dry_run: If True, return first plan without executing

    Returns:
        dict with: status, summary, collected_count, evidence, learnings
    """
    from orchestrator_prompts import (
        SYSTEM_PROMPT,
        TASK_PROMPT,
        PROGRESS_TEMPLATE,
        STUCK_NUDGE,
    )

    # Build tool definitions from capabilities
    cap_tools = manifest_json()
    # Add terminate tool (OpenManus pattern)
    cap_tools.append(
        {
            "name": "terminate",
            "description": "Call when the task is complete or budget exhausted. Provide a summary of findings.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Summary of what was found",
                    },
                    "collected_count": {
                        "type": "integer",
                        "description": "Number of items collected",
                    },
                },
                "required": ["summary"],
            },
        }
    )

    # Use custom prompt if provided (AVO evolution), otherwise default
    if system_prompt:
        base_prompt = system_prompt
    else:
        # Use AVO-evolved prompt if available, otherwise default
        evolved_path = Path(__file__).parent / "sources" / "evolved-prompt.txt"
        if evolved_path.exists():
            try:
                base_prompt = evolved_path.read_text()
            except Exception:
                base_prompt = SYSTEM_PROMPT
        else:
            base_prompt = SYSTEM_PROMPT
    # Build initial messages
    system_msg = base_prompt.format(manifest=manifest_text())
    task_msg = TASK_PROMPT.format(
        task_spec=task_spec,
        mode=mode,
        max_steps=max_steps,
        budget_status="unlimited" if not budget else json.dumps(budget),
        learnings_context="",
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": task_msg},
    ]

    # State tracking
    all_evidence: list[dict] = []
    all_learnings: list[str] = []
    # Load historical learnings from patterns.jsonl
    try:
        historical = dispatch("learnings_persist", None, action="load", max_load=15)
        if isinstance(historical, list) and historical:
            all_learnings.extend(historical)
            print(
                f"[orchestrator] Loaded {len(historical)} historical learnings",
                file=sys.stderr,
            )
    except Exception:
        pass
    # Rebuild task prompt with historical learnings if any were loaded
    if all_learnings:
        task_msg = TASK_PROMPT.format(
            task_spec=task_spec,
            mode=mode,
            max_steps=max_steps,
            budget_status="unlimited" if not budget else json.dumps(budget),
            learnings_context="Historical learnings from past sessions:\n"
            + "\n".join(f"- {l}" for l in all_learnings[:10]),
        )
        messages[-1] = {"role": "user", "content": task_msg}
    step_history: list[dict] = []

    # Generate task_id
    if not task_id:
        import hashlib

        task_id = hashlib.sha1(task_spec.encode()).hexdigest()[:8]
    checkpoint_dir = Path("sources/checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / f"{task_id}.json"

    # Resume from checkpoint if requested
    if resume_from:
        _resume_path = (
            Path(resume_from) if Path(resume_from).exists() else checkpoint_path
        )
        if _resume_path.exists():
            try:
                saved = json.loads(_resume_path.read_text())
                all_evidence = saved.get("evidence", [])
                all_learnings = saved.get("learnings", [])
                step_history = saved.get("step_history", [])
                start_step = saved.get("steps_used", 0)
                print(
                    f"[orchestrator] Resumed from checkpoint: {len(all_evidence)} evidence, step {start_step}",
                    file=sys.stderr,
                )
            except Exception:
                start_step = 0
        else:
            start_step = 0
    else:
        start_step = 0

    if dry_run:
        # Just get the first plan
        try:
            response = _call_llm(messages, cap_tools, model=model)
            tool_call = _extract_tool_call(response)
            text = _extract_text(response)
            return {
                "status": "dry_run",
                "plan": tool_call,
                "reasoning": text,
                "manifest_size": len(load_manifest()),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # Main ReAct loop
    for step in range(start_step, max_steps):
        try:
            response = _call_llm(messages, cap_tools, model=model)
        except Exception as exc:
            print(
                f"[orchestrator] LLM call failed at step {step}: {exc}", file=sys.stderr
            )
            break

        tool_call = _extract_tool_call(response)
        text = _extract_text(response)

        # If LLM returned text without tool call, add it and prompt again
        if not tool_call:
            if text:
                messages.append({"role": "assistant", "content": text})
                messages.append(
                    {
                        "role": "user",
                        "content": "Please call a capability or terminate.",
                    }
                )
                continue
            break

        # Handle terminate
        if tool_call["name"] == "terminate":
            # Save learnings for future sessions
            if all_learnings:
                try:
                    dispatch(
                        "learnings_persist",
                        all_learnings,
                        action="save",
                        task_spec=task_spec,
                    )
                except Exception:
                    pass
            return {
                "status": "done",
                "summary": tool_call["input"].get("summary", ""),
                "collected_count": len(all_evidence),
                "evidence": all_evidence,
                "learnings": all_learnings,
                "steps_used": step + 1,
            }

        # Dispatch capability
        cap_name = tool_call["name"]
        cap_input = tool_call["input"].get("input")
        cap_context = tool_call["input"].get("context", {})

        # Inject accumulated learnings into context
        if all_learnings:
            cap_context.setdefault("learnings", all_learnings)

        print(
            f"[orchestrator] Step {step + 1}/{max_steps}: {cap_name}", file=sys.stderr
        )

        try:
            result = dispatch(cap_name, cap_input, **cap_context)
        except Exception as exc:
            result = {"error": str(exc)}
            print(
                f"[orchestrator] Capability {cap_name} failed: {exc}", file=sys.stderr
            )

        # Track evidence (anything with URLs)
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict) and item.get("url"):
                    all_evidence.append(item)

        # Track learnings
        if isinstance(result, list) and all(isinstance(x, str) for x in result):
            all_learnings.extend(result)
        elif isinstance(result, dict) and result.get("learnings"):
            all_learnings.extend(result["learnings"])

        # Record step
        step_record = {
            "step": step + 1,
            "capability": cap_name,
            "new_count": len(result) if isinstance(result, list) else 0,
            "urls": [item.get("url", "") for item in result[:5]]
            if isinstance(result, list) and result and isinstance(result[0], dict)
            else [],
        }
        step_history.append(step_record)

        # Save checkpoint after each step
        try:
            checkpoint_data = {
                "task_spec": task_spec,
                "task_id": task_id,
                "steps_used": step + 1,
                "evidence": all_evidence[-200:],  # cap to avoid huge files
                "learnings": all_learnings,
                "step_history": step_history,
                "mode": mode,
            }
            checkpoint_path.write_text(json.dumps(checkpoint_data, default=str))
        except Exception:
            pass

        # Build tool result message with progress
        result_summary = _summarize_result(result)
        progress = PROGRESS_TEMPLATE.format(
            step=step + 1,
            max_steps=max_steps,
            collected=len(all_evidence),
            new_count=step_record["new_count"],
            extra=f"Learnings: {len(all_learnings)}" if all_learnings else "",
        )
        tool_result_content = f"{result_summary}\n\n{progress}"

        # Add to conversation (OpenAI tool-use message format)
        # Clean assistant message: strip null fields and index from tool_calls
        # to avoid 400 errors with some models
        raw_msg = response.get("choices", [{}])[0].get("message", {})
        assistant_msg = {"role": "assistant"}
        if raw_msg.get("content"):
            assistant_msg["content"] = raw_msg["content"]
        else:
            assistant_msg["content"] = ""
        if raw_msg.get("tool_calls"):
            assistant_msg["tool_calls"] = [
                {"id": tc.get("id", ""), "type": "function", "function": tc.get("function", {})}
                for tc in raw_msg["tool_calls"]
            ]
        messages.append(assistant_msg)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": tool_result_content,
            }
        )

        # Check stuck (every 3 steps)
        if len(step_history) >= 3 and len(step_history) % 3 == 0:
            try:
                stuck_result = dispatch("stuck_detect", None, history=step_history[-6:])
                if stuck_result.get("stuck"):
                    nudge = STUCK_NUDGE.format(
                        confidence=stuck_result.get("confidence", 0),
                        suggestions="; ".join(stuck_result.get("suggestions", [])),
                    )
                    messages.append({"role": "user", "content": nudge})
            except Exception:
                pass

        # Compress old messages when conversation grows too long
        if len(messages) > 24:
            # Keep system message + last 16 messages
            system_msgs = [
                m for m in messages[:2] if m.get("role") in ("system", "user")
            ]
            recent = messages[-16:]
            # Build compression summary
            old_count = len(messages) - len(system_msgs) - len(recent)
            compression_note = {
                "role": "user",
                "content": f"[Previous {old_count} messages compressed. You have collected {len(all_evidence)} evidence items and {len(all_learnings)} learnings so far. Continue the task.]",
            }
            messages = system_msgs + [compression_note] + recent

    # Max steps reached — beast mode
    print("[orchestrator] Max steps reached, entering beast mode", file=sys.stderr)
    # Save learnings for future sessions
    if all_learnings:
        try:
            dispatch(
                "learnings_persist", all_learnings, action="save", task_spec=task_spec
            )
        except Exception:
            pass
    try:
        beast_result = dispatch(
            "beast_mode", all_evidence, learnings=all_learnings, task_spec=task_spec
        )
        return {
            "status": "beast_mode",
            "summary": beast_result.get("summary", ""),
            "collected_count": len(all_evidence),
            "evidence": all_evidence,
            "learnings": all_learnings,
            "steps_used": max_steps,
        }
    except Exception:
        return {
            "status": "max_steps",
            "summary": f"Completed {max_steps} steps, collected {len(all_evidence)} items",
            "collected_count": len(all_evidence),
            "evidence": all_evidence,
            "learnings": all_learnings,
            "steps_used": max_steps,
        }
