"""
Base async Claude caller with prompt caching support.

Model strategy:
  - FAST  (claude-haiku-4-5)  → parse step, quick extractions
  - MID   (claude-sonnet-4-6) → intermediate agents (historical, opinion)
  - FULL  (claude-opus-4-6)   → strategy-bot final output only
"""
import json
import re
import anthropic
from typing import Any

MODEL_FAST = "claude-haiku-4-5"
MODEL_MID  = "claude-sonnet-4-6"
MODEL_FULL = "claude-opus-4-6"

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
    return _client


async def call_agent(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 8000,
    model: str = MODEL_MID,
) -> str:
    """
    Call Claude with a given system prompt and user message.
    Returns the raw text response.

    The system prompt is marked with cache_control so repeated calls
    with the same prompt hit the prompt cache instead of reprocessing.
    """
    client = get_client()

    # Adaptive thinking is only supported on Opus and Sonnet, not Haiku
    supports_thinking = model in (MODEL_MID, MODEL_FULL)

    create_kwargs: dict[str, Any] = dict(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    if supports_thinking:
        create_kwargs["thinking"] = {"type": "adaptive"}

    response = await client.messages.create(**create_kwargs)

    # Extract text from response content blocks (skip thinking blocks)
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n".join(parts)


def extract_json(text: str) -> Any:
    """
    Extract and parse the first JSON object or array found in a text response.
    Tries fenced code blocks first, then bare JSON.
    Never raises — falls back to {"raw_response": text} on any parse failure.
    """
    # Try ```json ... ``` or ``` ... ```
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass  # fall through to bare-JSON search

    # Try first { ... } span
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break  # malformed — fall through

    # Return raw text if no valid JSON found
    return {"raw_response": text}
