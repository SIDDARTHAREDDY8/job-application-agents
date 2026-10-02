"""ApplyAgent: actually submits applications, the way the production machine does.

Routing per job:
  1. contact_email present -> draft with OutreachAgent, send via GmailSender
     (resume PDF attached), return the send receipt.
  2. apply_url/board matches a known adapter -> drive it with Playwright,
     fill the form via the LLM, upload resume, submit, and verify the
     confirmation marker. applied=True ONLY on a seen confirmation.
  3. Neither -> applied=False with a note (never a phantom submit).

Safety:
  - dry_run=True (default) drafts everything and touches nothing.
  - Human-only steps (CAPTCHA, OTP) abort the item with a note, never retried.
"""

from __future__ import annotations
from datetime import date
from typing import Any
from .base_agent import BaseAgent
from .outreach import OutreachAgent


class ApplyAgent(BaseAgent):
    def __init__(self, llm, candidate: dict[str, Any], driver=None, gmail=None):
        super().__init__(llm, candidate)
        self.driver = driver
        self.gmail = gmail
        self.outreach = OutreachAgent(llm, candidate)

    # ------------------------------------------------------------------ main entry
    def apply(self, job: dict[str, Any], tailored: dict[str, Any] | None = None,
              resume_path: str | None = None, dry_run: bool = True) -> dict[str, Any]:
        company = job.get("company", "")
        role = job.get("role", "")
        base = {
            "company": company, "role": role,
            "location": job.get("location", ""),
            "role_type": job.get("role_type", ""),
            "contact_name": job.get("contact_name", ""),
            "contact_email": job.get("contact_email", ""),
            "source_url": job.get("source_url", ""),
            "apply_url": job.get("apply_url", ""),
            "board": job.get("board", ""),
            "date": str(date.today()),
        }

        if dry_run:
            route = self._route(job)
            email = self.outreach.draft(job, tailored) if route == "email" else None
            return {**base, "applied": False, "route": route,
                    "subject": (email or {}).get("subject", ""),
                    "body": (email or {}).get("body", ""),
                    "note": "dry-run: drafted, nothing sent or submitted",
                    "status": "drafted"}

        route = self._route(job)
        if route == "email":
            return self._apply_by_email(job, tailored, resume_path, base)
        if route == "board":
            return self._apply_on_board(job, resume_path, base)
        return {**base, "applied": False, "route": "none",
                "note": "no contact email and no supported board URL; needs manual apply",
                "status": "manual"}

    # ------------------------------------------------------------------ routing
    def _route(self, job: dict[str, Any]) -> str:
        if job.get("contact_email"):
            return "email"
        from ..boards import get_adapter
        url = job.get("apply_url") or job.get("source_url") or ""
        board = job.get("board") or ""
        if get_adapter(url) or get_adapter(board):
            return "board"
        return "none"

    # ------------------------------------------------------------------ email route
    def _apply_by_email(self, job, tailored, resume_path, base) -> dict[str, Any]:
        if self.gmail is None:
            return {**base, "applied": False, "route": "email",
                    "note": "no GmailSender configured; set GMAIL_* in .env",
                    "status": "blocked"}
        email = self.outreach.draft(job, tailored)
        to = job["contact_email"]
        try:
            receipt = self.gmail.send(
                to=to, subject=email["subject"], body=email["body"],
                attachments=[resume_path] if resume_path else None,
            )
        except Exception as e:
            return {**base, "applied": False, "route": "email",
                    "subject": email["subject"], "body": email["body"],
                    "note": f"send failed: {e}", "status": "failed"}
        message_id = receipt.get("message_id", "")
        # A send counts only with a real id back from the provider.
        applied = bool(message_id)
        return {**base, "applied": applied, "route": "email",
                "subject": email["subject"], "body": email["body"],
                "message_id": message_id,
                "note": "" if applied else "provider returned no message id",
                "status": "applied" if applied else "failed"}

    # ------------------------------------------------------------------ board route
    def _apply_on_board(self, job, resume_path, base) -> dict[str, Any]:
        if self.driver is None:
            return {**base, "applied": False, "route": "board",
                    "note": "no PlaywrightManager configured",
                    "status": "blocked"}
        from ..boards import get_adapter
        url = job.get("apply_url") or job.get("source_url") or ""
        adapter = get_adapter(url) or get_adapter(job.get("board") or "")
        if adapter is None:
            return {**base, "applied": False, "route": "board",
                    "note": f"no adapter for {url}", "status": "manual"}
        try:
            result = adapter.apply(self.driver, job, self.candidate, resume_path, self.llm)
        except Exception as e:
            return {**base, "applied": False, "route": "board",
                    "board": adapter.name,
                    "note": f"adapter error: {str(e)[:200]}", "status": "failed"}
        return {**base, "applied": bool(result.get("applied")), "route": "board",
                "board": adapter.name,
                "confirmation": result.get("confirmation", ""),
                "note": result.get("note", ""),
                "screenshot": result.get("screenshot"),
                "status": "applied" if result.get("applied") else "failed"}
