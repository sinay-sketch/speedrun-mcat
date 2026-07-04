#!/usr/bin/env python3
# License: GNU AGPL v3 or later.
"""Provider-agnostic LLM client for the Speedrun AI harness.

Backend: OpenAI (the user supplies OPENAI_API_KEY). Kept deliberately small so
the harness could be pointed at another provider by swapping this one file.

  from llm import LLM, have_key
  llm = LLM()
  text = llm.chat("You are terse.", "Say hi.")
  obj  = llm.json("Return JSON.", "Give {\"ok\":true}")

Models (override via env):
  SPEEDRUN_GEN_MODEL    default gpt-4o-mini   (bulk generation)
  SPEEDRUN_JUDGE_MODEL  default gpt-4o        (quality-critical judging)
"""
import json
import os

GEN_MODEL = os.environ.get("SPEEDRUN_GEN_MODEL", "gpt-4o-mini")
JUDGE_MODEL = os.environ.get("SPEEDRUN_JUDGE_MODEL", "gpt-4o")


def have_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


class LLM:
    def __init__(self, model: str = GEN_MODEL):
        if not have_key():
            raise RuntimeError("OPENAI_API_KEY not set; live LLM calls unavailable.")
        from openai import OpenAI
        self._client = OpenAI()
        self.model = model

    def chat(self, system: str, user: str, model: str | None = None,
             temperature: float = 0.2) -> str:
        r = self._client.chat.completions.create(
            model=model or self.model,
            temperature=temperature,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return r.choices[0].message.content.strip()

    def json(self, system: str, user: str, model: str | None = None,
             temperature: float = 0.0) -> dict:
        """Chat constrained to a JSON object."""
        r = self._client.chat.completions.create(
            model=model or self.model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return json.loads(r.choices[0].message.content)
