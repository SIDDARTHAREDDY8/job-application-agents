"""Tailor agent: rewrites resume bullets to mirror a JD without inventing facts."""
from __future__ import annotations
from typing import Any
from .base_agent import BaseAgent

SYSTEM = """You are a resume tailor. Rewrite the candidate's resume for ONE job description.

HARD RULES:
- Every claim must trace to the candidate brief. Never invent companies, dates, metrics, or tools.
- You may REWORD bullets (strict synonym swaps, mirror the JD's role language) but facts stay identical.
- Keep the same number of experience entries; trim only projects/skills if length is a concern.
- Return ONLY JSON. No prose, no markdown fences.

JSON schema:
{"tailored_bullets": [{"company": str, "bullets": [str]}],
 "skills_line": str,
 "summary_line": str,
 "notes": str}
"""


class TailorAgent(BaseAgent):
    def tailor(self, jd_text: str) -> dict[str, Any]:
        user = (
            f"CANDIDATE BRIEF (facts only - never invent beyond this):\n{self._candidate_brief()}\n\n"
            f"JOB DESCRIPTION:\n{jd_text[:10000]}"
        )
        reply = self._ask(SYSTEM, user, temperature=0.4)
        return self._extract_json(reply)
