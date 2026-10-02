"""Coordinator: source -> dedupe -> tailor -> draft -> apply, one clean run.

Phases mirror the production job-hunt machine:
  1. source   - SourcerAgent extracts structured jobs from your raw signals
  2. dedupe   - drop anything already in state/applications.json
  3. tailor   - TailorAgent rewrites resume bullets per JD
  4. draft    - OutreachAgent drafts the application email (always, for review)
  5. apply    - ApplyAgent submits (email via Gmail, or board via Playwright)
                ONLY when dry_run=False. applied=True requires a verified
                send receipt or an on-page confirmation marker.

Usage:
    coord = Coordinator(llm, candidate, driver=driver, gmail=gmail)
    out = coord.run(sources, max_jobs=5, dry_run=True)   # safe: drafts only
    out = coord.run(sources, max_jobs=5, dry_run=False)  # actually applies
"""
from __future__ import annotations
import json
import os
from datetime import date
from typing import Any
from ..llm.base import LLMClient
from .sourcer import SourcerAgent
from .tailor import TailorAgent
from .outreach import OutreachAgent
from .apply import ApplyAgent


class Coordinator:
    def __init__(self, llm: LLMClient, candidate: dict[str, Any],
                 state_path: str = "state/applications.json",
                 driver=None, gmail=None):
        self.llm = llm
        self.candidate = candidate
        self.state_path = state_path
        self.sourcer = SourcerAgent(llm, candidate)
        self.tailor = TailorAgent(llm, candidate)
        self.outreach = OutreachAgent(llm, candidate)
        self.applier = ApplyAgent(llm, candidate, driver=driver, gmail=gmail)

    # ------------------------------------------------------------------ state
    def _load_seen(self) -> set[str]:
        if not os.path.exists(self.state_path):
            return set()
        with open(self.state_path) as f:
            data = json.load(f)
        seen: set[str] = set()
        for e in data if isinstance(data, list) else data.get("applications", []):
            seen.add(f"{str(e.get('company','')).lower()}|{str(e.get('role','')).lower()}")
            if e.get("contact_email"):
                seen.add(str(e["contact_email"]).lower())
        return seen

    def _save(self, records: list[dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        existing: list = []
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                data = json.load(f)
            existing = data if isinstance(data, list) else data.get("applications", [])
        existing.extend(records)
        with open(self.state_path, "w") as f:
            json.dump(existing, f, indent=2)

    # ------------------------------------------------------------------ run
    def run(self, raw_sources: list[dict[str, str]], max_jobs: int = 5,
            dry_run: bool = True, resume_path: str | None = None) -> dict[str, Any]:
        """raw_sources: [{"text": "...", "source_url": "..."}] - your collected hiring signals."""
        seen = self._load_seen()

        # Phase 1: source
        all_jobs: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for src in raw_sources:
            out = self.sourcer.extract(src.get("text", ""), src.get("source_url", ""))
            all_jobs.extend(out.get("jobs", []))
            skipped.extend(out.get("skipped", []))

        # Phase 2: dedupe
        fresh = SourcerAgent.dedupe(all_jobs, seen)[:max_jobs]

        # Phases 3-5: tailor -> draft -> apply
        results: list[dict[str, Any]] = []
        for job in fresh:
            tailored = self.tailor.tailor(job.get("jd_text", ""))
            email = self.outreach.draft(job, tailored)
            applied = self.applier.apply(job, tailored, resume_path, dry_run=dry_run)
            results.append({**applied, "tailored": tailored,
                            "draft_subject": email.get("subject"),
                            "draft_body": email.get("body")})

        if not dry_run:
            self._save(results)

        applied_n = sum(1 for r in results if r.get("applied"))
        return {
            "sourced": len(all_jobs),
            "fresh": len(fresh),
            "applied": applied_n,
            "results": results,
            "skipped": skipped,
            "dry_run": dry_run,
            "model": self.llm.model_name,
        }
