"""Workable ATS adapter (workable.com)."""
from __future__ import annotations
from typing import Any
from .base import BoardAdapter, ats_apply_flow


class WorkableAdapter(BoardAdapter):
    name = "workable"
    domains = ("workable.com",)

    def apply(self, driver, job: dict[str, Any], candidate: dict[str, Any],
              resume_path: str | None, llm) -> dict[str, Any]:
        return ats_apply_flow(
            driver, job, candidate, resume_path, llm,
            submit_texts=("submit application", "submit"),
            name=self.name,
        )
