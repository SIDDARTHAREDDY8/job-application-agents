"""Shared base for all job-hunt agents."""
from __future__ import annotations
import json
import re
from typing import Any
from ..llm.base import LLMClient


class BaseAgent:
    def __init__(self, llm: LLMClient, candidate: dict[str, Any] | None = None):
        self.llm = llm
        self.candidate = candidate or {}

    def _ask(self, system: str, user: str, **kwargs) -> str:
        return self.llm.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )

    @staticmethod
    def _extract_json(text: str) -> Any:
        """Pull the first JSON object/array out of an LLM reply (tolerant of fences/prose)."""
        text = text.strip()
        # strip code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        raise ValueError(f"No JSON found in LLM reply: {text[:300]}")

    def _candidate_brief(self) -> str:
        c = self.candidate
        lines = [
            f"Name: {c.get('name', '[Your Name]')}",
            f"Target roles: {', '.join(c.get('target_roles', []))}",
            f"Location / work: {c.get('location', '')} / {c.get('work_preference', '')}",
            f"Experience summary: {c.get('summary', '')}",
        ]
        if c.get("skills"):
            lines.append(f"Key skills: {', '.join(c['skills'])}")
        if c.get("experience"):
            lines.append("Experience:")
            for e in c["experience"]:
                lines.append(
                    f"- {e.get('title')} @ {e.get('company')} ({e.get('dates')}): "
                    + "; ".join(e.get("bullets", []))
                )
        return "\n".join(lines)
