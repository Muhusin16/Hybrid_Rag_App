# src/llm_orchestration/cast_metal_answer.py
from typing import Dict, Any, List
import json
import re
from langchain_ollama import OllamaLLM

LLM_MODEL = "llama3"

def _extract_json_from_text(raw: str) -> Dict[str, Any]:
    """
    Attempt to extract a JSON object from raw LLM output.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to locate {...} block
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end+1])
            except Exception:
                pass
    return {}

def _validate_against_context(value: str, ctx: str) -> bool:
    """
    Return True if the value appears verbatim in context.
    This is a strict check to avoid hallucination.
    """
    if not value:
        return False
    return value.lower() in ctx.lower()

def answer_cast_metal_query(query: str, context: str) -> Dict[str, Any]:
    """
    Extract structured Cast Metal options from provided context + query.
    RETURN FORMAT (Option B):
    {
      "fonts": [
        {"name": "Arial", "heights": ["2","3"], "depths": ["5/8","3/4"], "profiles": ["prismatic"]}
      ],
      "mounting": ["Stud mount", ...]
    }
    """
    combined_context = context or ""
    prompt = f"""
You are a strict extractor for Cast Metal signage configuration. Use ONLY the CONTEXT to answer.
Do NOT invent values. If something is not in the context, leave it out or return an empty list.

CONTEXT:
{combined_context}

USER QUERY:
{query}

Return strictly valid JSON only (no explanation) following this schema:

{{
  "fonts": [
    {{
      "name": "<font name>",
      "heights": ["<height1>", "<height2>", ...],
      "depths": ["<depth1>", "<depth2>", ...],
      "profiles": ["<profile1>", ...]
    }}
  ],
  "mounting": ["<mount1>", "<mount2>"]
}}

Rules:
- Only include font names and option tokens that appear verbatim in the CONTEXT.
- Heights and depths should be strings exactly as found in the context.
- If no values found for a key, return an empty list for that key.
- Return JSON only.
"""

    llm = OllamaLLM(model=LLM_MODEL)
    raw = llm.invoke(prompt)

    parsed = _extract_json_from_text(raw)
    ctx = combined_context

    # Normalized result
    result: Dict[str, Any] = {"fonts": [], "mounting": []}

    # Validate mounting entries
    for m in parsed.get("mounting", []):
        if isinstance(m, str) and _validate_against_context(m, ctx):
            result["mounting"].append(m)

    # Validate fonts list
    for f in parsed.get("fonts", []):
        if not isinstance(f, dict):
            continue
        name = f.get("name")
        if not name or not _validate_against_context(name, ctx):
            continue
        # Collect validated heights, depths, profiles
        heights = []
        depths = []
        profiles = []

        for h in f.get("heights", []):
            if isinstance(h, (str, int, float)) and _validate_against_context(str(h), ctx):
                heights.append(str(h))

        for d in f.get("depths", []):
            if isinstance(d, (str, int, float)) and _validate_against_context(str(d), ctx):
                depths.append(str(d))

        for p in f.get("profiles", []):
            if isinstance(p, str) and _validate_against_context(p, ctx):
                profiles.append(p)

        result["fonts"].append({
            "name": name,
            "heights": sorted(list(dict.fromkeys(heights))),
            "depths": sorted(list(dict.fromkeys(depths))),
            "profiles": sorted(list(dict.fromkeys(profiles)))
        })

    # Ensure keys exist
    result.setdefault("fonts", [])
    result.setdefault("mounting", [])

    return result
