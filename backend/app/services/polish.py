"""Goal-polish service. Never exposes API keys to the client."""
from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings


SYSTEM_PROMPT = (
    "You polish a single short personal goal/task line into a clear, "
    "actionable phrase. Rules: keep it under 80 characters, preserve "
    "intent, use imperative verbs where natural, no emojis, no quotes, "
    "no trailing period. Return only JSON: "
    '{"text": "<polished>"}'
)


def polish(text: str) -> dict[str, Any]:
    """Return {text, original, used_ai, warning}."""
    original = text.strip()
    settings = get_settings()

    if not settings.openai_api_key:
        return {
            "text": original,
            "original": original,
            "used_ai": False,
            "warning": "OPENAI_API_KEY not configured — returning original text.",
        }

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": original},
            ],
            response_format={"type": "json_object"},
            max_tokens=120,
            temperature=0.4,
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        polished = (data.get("text") or "").strip().strip('"').strip("'")
        if not polished:
            polished = original
        polished = polished.rstrip(".")[:120]
        return {"text": polished, "original": original, "used_ai": True, "warning": None}
    except Exception as e:  # noqa: BLE001
        return {
            "text": original,
            "original": original,
            "used_ai": False,
            "warning": f"AI polish failed: {type(e).__name__}",
        }
