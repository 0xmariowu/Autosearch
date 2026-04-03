"""AVO variation operator: evolve orchestrator prompts from lineage."""

name = "avo_vary"
description = "Examine prior orchestrator prompts and their scores, then generate an improved prompt. This is the core of AVO: the agent evolves its own search methodology by mutating the instructions."
when = "At the start of each AVO generation, to produce a new orchestrator prompt."
input_type = "any"
output_type = "any"
input_schema = {
    "type": "object",
    "properties": {
        "input": {"description": "Not used, pass null"},
        "context": {
            "type": "object",
            "properties": {
                "population": {
                    "type": "array",
                    "description": "Prior generations: [{prompt, scores}]",
                },
                "knowledge": {
                    "type": "string",
                    "description": "Capabilities manifest text",
                },
                "task_spec": {"type": "string", "description": "The search task"},
                "use_llm": {"type": "boolean", "default": True},
            },
        },
    },
}

import json
import os
import urllib.request

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def _template_vary(population, knowledge, task_spec):
    """Fallback: template-based variation without LLM."""
    if not population:
        return None  # Use default prompt

    best = max(population, key=lambda x: x.get("scores", {}).get("total", 0))
    prompt = best.get("prompt", "")
    scores = best.get("scores", {})

    weakest = min(
        ["quantity_score", "diversity", "relevance", "efficiency"],
        key=lambda k: scores.get(k, 0),
    )

    mutations = {
        "quantity_score": "\n- PRIORITY: Maximize unique URLs. Use limit=50 on every search. Search 4+ providers.",
        "diversity": "\n- PRIORITY: Maximize diversity. Use ALL provider types: github, web, social, semantic.",
        "relevance": "\n- PRIORITY: Maximize relevance. Use persona_expand for diverse queries. Extract learnings.",
        "efficiency": "\n- PRIORITY: Maximize efficiency. Spend 80% of steps searching. Minimize think/processing.",
    }

    if prompt:
        return prompt + mutations.get(weakest, "")
    return None


def _llm_vary(population, knowledge, task_spec):
    """LLM-based variation: generate improved prompt."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return None

    pop_summary = ""
    if population:
        sorted_pop = sorted(
            population, key=lambda x: x.get("scores", {}).get("total", 0), reverse=True
        )
        for i, entry in enumerate(sorted_pop[:5]):
            s = entry.get("scores", {})
            pop_summary += f"\nGen (score {s.get('total', 0):.3f}): urls={s.get('unique_urls', 0)}, "
            pop_summary += (
                f"div={s.get('diversity', 0):.2f}, eff={s.get('efficiency', 0):.2f}"
            )
            pop_summary += f"\nPrompt: {str(entry.get('prompt', ''))[:200]}..."

    meta_prompt = f"""You are evolving a search system's orchestrator prompt.

Task: {task_spec}

Available capabilities (the AI can call these):
{knowledge[:1500]}

Prior generations (best first):
{pop_summary or "No prior generations (first run)"}

Generate an improved SYSTEM PROMPT. It must:
1. Use {{manifest}} placeholder where capability list goes
2. Tell the AI to search broadly using multiple providers
3. Include workflow: search → process (consensus_score, dedup) → learn → repeat
4. Fix weaknesses from prior generations
5. Be concise

Return ONLY the prompt text."""

    payload = json.dumps(
        {
            "model": os.environ.get(
                "OPENROUTER_ORCHESTRATOR_MODEL", "google/gemini-2.5-flash"
            ),
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": meta_prompt}],
            "temperature": 0.7,
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

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        if content and len(content) > 100:
            if "{manifest}" not in content:
                content += "\n\n## Available Capabilities\n{manifest}"
            return content
    except Exception:
        pass

    return None


def run(input_data, **context):
    population = context.get("population", [])
    knowledge = context.get("knowledge", "")
    task_spec = context.get("task_spec", "")
    use_llm = context.get("use_llm", True)

    if use_llm:
        prompt = _llm_vary(population, knowledge, task_spec)
        method = "llm" if prompt else "template_fallback"
        if not prompt:
            prompt = _template_vary(population, knowledge, task_spec)
    else:
        prompt = _template_vary(population, knowledge, task_spec)
        method = "template"

    return {"prompt": prompt, "method": method}


def test():
    pop = [
        {
            "prompt": "Search broadly",
            "scores": {
                "total": 0.3,
                "quantity_score": 0.5,
                "diversity": 0.1,
                "relevance": 0.3,
                "efficiency": 0.3,
            },
        },
        {
            "prompt": "Search deeply",
            "scores": {
                "total": 0.5,
                "quantity_score": 0.7,
                "diversity": 0.3,
                "relevance": 0.5,
                "efficiency": 0.5,
            },
        },
    ]
    result = run(
        None,
        population=pop,
        knowledge="test capabilities",
        task_spec="test",
        use_llm=False,
    )
    assert result["prompt"] is not None
    assert "PRIORITY" in result["prompt"]

    result2 = run(None, population=[], use_llm=False)
    assert result2["prompt"] is None
    return "ok"
