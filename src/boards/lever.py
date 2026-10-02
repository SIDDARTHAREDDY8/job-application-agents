"""Lever ATS adapter (lever.co)."""
from __future__ import annotations
from typing import Any
from .base import BoardAdapter, ats_apply_flow


class LeverAdapter(BoardAdapter):
    name = "lever"
    domains = ("lever.co",)

    def apply(self, driver, job: dict[str, Any], candidate: dict[str, Any],
              resume_path: str | None, llm) -> dict[str, Any]:
        return ats_apply_flow(
            driver, job, candidate, resume_path, llm,
            submit_texts=("submit application", "submit"),
            name=self.name,
        )
