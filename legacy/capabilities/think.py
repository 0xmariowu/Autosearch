"""No-op reflection tool that forces the AI to think before acting."""

name = "think"
description = "Record a thought or reflection without executing any action. Use this to reason about strategy, plan next steps, or analyze what you have learned so far. The thought is recorded but no search or processing happens."
when = "Before making a strategic decision. When you need to reason about what to search next, evaluate progress, or change approach."
input_type = "any"
output_type = "any"
input_schema = {
    "type": "object",
    "properties": {
        "input": {"type": "string", "description": "Your thought or reflection text"},
    },
    "required": ["input"],
}


def run(thought, **context):
    return {
        "thought": str(thought or ""),
        "recorded": True,
    }


def test():
    result = run("I should try different keywords")
    assert result["recorded"]
    assert result["thought"] == "I should try different keywords"
    return "ok"
