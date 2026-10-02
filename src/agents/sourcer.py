"""Sourcer agent: turns hiring signals into structured job leads.

Portable version of the hidden-market sourcer: instead of being hard-wired to a
specific search stack, it takes raw posting text / search results YOU collected
and extracts clean, deduped job records. Bring your own sourcing (HN thread,
X posts, career pages, VC boards) - the agent structures it.
"""
from __future__ import annotations
from typing import Any
from .base_agent import BaseAgent

SYSTEM = """You are a job sourcer. Extract real open roles from the raw text given.
Return ONLY JSON. No prose, no markdown fences.

Rules:
- One object per real role. Skip duplicates.
- jd_text must be the actual posting text (or the longest description available).
- contact_email: copy verbatim if the posting names one; else "" (never invent).
- why_hidden: one line on where this was found and why it is not on big job boards.
- fit_note: one line tying the role to the candidate brief.
- Skip roles that require US citizenship or that clearly mismatch the candidate's target roles.

JSON schema:
{"jobs": [{"company": str, "role": str, "location": str, "role_type": str,
"jd_text": str, "contact_name": str, "contact_title": str, "contact_email": str,
"email_source": str, "source_url": str, "why_hidden": str, "fit_note": str}],
"skipped": [{"company": str, "role": str, "reason": str}]}
"""


class SourcerAgent(BaseAgent):
    def extract(self, raw_text: str, source_url: str = "") -> dict[str, Any]:
        user = (
            f"CANDIDATE BRIEF:\n{self._candidate_brief()}\n\n"
            f"SOURCE URL (if any): {source_url}\n\n"
            f"RAW TEXT TO EXTRACT FROM:\n{raw_text[:12000]}"
        )
        reply = self._ask(SYSTEM, user, temperature=0.2)
        data = self._extract_json(reply)
        if isinstance(data, list):
            data = {"jobs": data, "skipped": []}
        data.setdefault("jobs", [])
        data.setdefault("skipped", [])
        return data

    @staticmethod
    def dedupe(jobs: list[dict[str, Any]], seen_keys: set[str]) -> list[dict[str, Any]]:
        """Drop jobs whose company+role (or contact email) was already touched."""
        fresh = []
        for j in jobs:
            key = f"{str(j.get('company','')).lower().strip()}|{str(j.get('role','')).lower().strip()}"
            email = str(j.get("contact_email", "")).lower().strip()
            if key in seen_keys or (email and email in seen_keys):
                continue
            seen_keys.add(key)
            if email:
                seen_keys.add(email)
            fresh.append(j)
        return fresh
