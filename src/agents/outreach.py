"""Outreach agent: drafts a short, problem-first application / pitch email.

Style rules distilled from the production job-hunt machine:
- Problem-first: open with a sharp observation about what THEY are building.
- Never open with "I am applying for X".
- One proof point from the candidate brief, woven into a sentence (not a credential stack).
- Say plainly what they get if they hire the candidate.
- One low-friction ask. 80-150 words, plain text, contractions.
- No em-dashes; no throat-clearing openers.
"""
from __future__ import annotations
from typing import Any
from .base_agent import BaseAgent

SYSTEM = """You are a job outreach writer. Draft a short application email for ONE role.

FORMAT (hard):
- Subject: role title + one specific hook fragment (never just "Job Application").
- Line 1: a sharp observation proving you understand what they are building (from the JD/company).
  Never generic flattery. Never open with "I am applying for X".
- Bridge: the ONE part of their JD the candidate maps to best, tied to ONE proof point
  from the candidate brief. One proof point in one sentence, never a credential stack.
- Say plainly what they get if they hire the candidate (outcome, not features).
- State the resume is attached. One low-friction ask ("Worth a 20-min chat this week?").
- Sign with the candidate's first name + phone + LinkedIn from the brief.
- 80-150 words, plain text. NO em-dashes (use commas/periods). Contractions always.
- Banned openers: "I hope this email finds you well". Banned words: thrilled, passionate,
  cutting-edge, synergy, "just checking in".

Return ONLY JSON: {"subject": str, "body": str}
"""


class OutreachAgent(BaseAgent):
    def draft(self, job: dict[str, Any], tailored: dict[str, Any] | None = None) -> dict[str, Any]:
        job_txt = job.get("jd_text", "")[:8000]
        tailored_txt = ""
        if tailored:
            import json as _json
            tailored_txt = _json.dumps(tailored)[:4000]
        user = (
            f"CANDIDATE BRIEF:\n{self._candidate_brief()}\n\n"
            f"ROLE: {job.get('role')} @ {job.get('company')} ({job.get('location', '')})\n"
            f"CONTACT: {job.get('contact_name', '')} {job.get('contact_title', '')}\n\n"
            f"JOB DESCRIPTION:\n{job_txt}\n\n"
            + (f"TAILORED RESUME POINTS:\n{tailored_txt}\n" if tailored_txt else "")
        )
        reply = self._ask(SYSTEM, user, temperature=0.7)
        data = self._extract_json(reply)
        if not isinstance(data, dict):
            data = {}
        # plain-text guard: strip any accidental markdown; tolerate missing keys
        data["body"] = str(data.get("body", "")).strip()
        data["subject"] = str(data.get("subject", "")).strip()
        return data
