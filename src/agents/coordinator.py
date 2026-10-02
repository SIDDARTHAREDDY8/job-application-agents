"""Coordinator: source -> dedupe -> tailor -> draft outreach, one clean run."""
from __future__ import annotations
import json
import os
from datetime import date
from typing import Any
from ..llm.base import LLMClient
from .sourcer import SourcerAgent
from .tailor import TailorAgent
from .outreach import OutreachAgent


class Coordinator:
    def __init__(self, llm: LLMClient, candidate: dict[str, Any], state_path: str = "state/applications.json"):
        self.llm = llm
        self.candidate = candidate
        self.state_path = state_path
        self.sourcer = SourcerAgent(llm, candidate)
        self.tailor = TailorAgent(llm, candidate)
        self.outreach = OutreachAgent(llm, candidate)

    # ---- state ----
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

    # ---- run ----
    def run(self, raw_sources: list[dict[str, str]], max_jobs: int = 5, dry_run: bool = True) -> dict[str, Any]:
        """raw_sources: [{"text": "...", "source_url": "..."}] - your collected hiring signals."""
        seen = self._load_seen()
        all_jobs: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for src in raw_sources:
            out = self.sourcer.extract(src.get("text", ""), src.get("source_url", ""))
            all_jobs.extend(out.get("jobs", []))
            skipped.extend(out.get("skipped", []))

        fresh = SourcerAgent.dedupe(all_jobs, seen)[:max_jobs]

        results: list[dict[str, Any]] = []
        for job in fresh:
            tailored = self.tailor.tailor(job.get("jd_text", ""))
            email = self.outreach.draft(job, tailored)
            record = {
                "company": job.get("company"),
                "role": job.get("role"),
                "location": job.get("location"),
                "role_type": job.get("role_type"),
                "contact_name": job.get("contact_name"),
                "contact_email": job.get("contact_email"),
                "source_url": job.get("source_url"),
                "date": str(date.today()),
                "subject": email.get("subject"),
                "body": email.get("body"),
                "tailored": tailored,
                "status": "drafted" if dry_run else "ready_to_send",
            }
            results.append(record)

        if not dry_run:
            self._save(results)
        return {
            "sourced": len(all_jobs),
            "fresh": len(fresh),
            "results": results,
            "skipped": skipped,
            "dry_run": dry_run,
            "model": self.llm.model_name,
        }
