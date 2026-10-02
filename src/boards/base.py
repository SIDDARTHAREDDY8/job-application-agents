"""BoardAdapter interface + shared apply flows.

Two shared flows cover most sites:

  ats_apply_flow()  - for Greenhouse / Lever / Ashby / Workable style forms:
                      goto -> extract fields -> LLM maps candidate data ->
                      fill -> upload resume -> submit -> confirm markers.

  guided_apply()    - best-effort multi-step flow for classic boards
                      (LinkedIn Easy Apply, Indeed, ...): click apply, then
                      loop {extract fields -> LLM map -> fill -> next} until
                      a submit/confirmation or a human-only step appears.

An apply() returns a plain dict:
  {"applied": bool, "confirmation": str, "note": str, "screenshot": str|None}

applied=True ONLY when a confirmation marker is seen on the page.
Anything else is applied=False with a note (never claim a phantom submit).
"""

from __future__ import annotations
import json
from abc import ABC, abstractmethod
from typing import Any


CONFIRM_MARKERS = [
    "application received", "thank you for applying", "thanks for applying",
    "your application has been submitted", "application submitted",
    "we'll be in touch", "we will be in touch", "successfully applied",
]

HUMAN_ONLY_HINTS = [
    "captcha", "puzzle", "drag the", "select all images", "i'm not a robot",
    "verify you are human", "one-time code", "verification code",
]


class BoardAdapter(ABC):
    name: str = "base"
    domains: tuple[str, ...] = ()

    # ------------------------------------------------------------------ matching
    def matches(self, url: str) -> bool:
        url = (url or "").lower()
        return any(d in url for d in self.domains)

    # ------------------------------------------------------------------ to implement
    def search_jobs(self, driver, query: str, location: str = "") -> list[dict[str, Any]]:
        raise NotImplementedError(f"{self.name}: search not implemented")

    def apply(self, driver, job: dict[str, Any], candidate: dict[str, Any],
              resume_path: str | None, llm) -> dict[str, Any]:
        raise NotImplementedError(f"{self.name}: apply not implemented")

    # ------------------------------------------------------------------ shared helpers
    @staticmethod
    def page_looks_human_blocked(driver) -> str | None:
        text = driver.page_text(3000).lower()
        for hint in HUMAN_ONLY_HINTS:
            if hint in text:
                return hint
        return None

    @staticmethod
    def confirmation_seen(driver) -> str | None:
        text = driver.page_text(4000).lower()
        for marker in CONFIRM_MARKERS:
            if marker in text:
                return marker
        return None


# ---------------------------------------------------------------------------
# LLM field mapping: form fields -> candidate values (JSON only)
# ---------------------------------------------------------------------------
MAP_SYSTEM = """You map an application form's fields to a candidate's data.

Return ONLY JSON: {"mappings": [{"key": "<field name or id>", "value": "<value to enter>"}]}

Rules:
- Use ONLY facts from the candidate profile. Never invent.
- For select dropdowns, pick the option text that best matches (copy it exactly).
- For yes/no questions use the candidate's form_answers.
- Leave a field OUT of mappings when you are not confident - do not guess.
- Never fill passwords, SSNs, or anything not in the profile.
- file inputs: map {"key": ..., "value": "__RESUME__"} for the resume upload field.
"""


def llm_map_fields(llm, fields: list[dict[str, Any]], candidate: dict[str, Any]) -> list[dict[str, str]]:
    brief = json.dumps(candidate, default=str)[:6000]
    field_desc = json.dumps(
        [{"name": f.get("name"), "id": f.get("id"), "label": f.get("label"),
          "type": f.get("type"), "required": f.get("required"),
          "options": f.get("options", [])[:20]} for f in fields],
        default=str,
    )[:8000]
    reply = llm.chat(
        [{"role": "system", "content": MAP_SYSTEM},
         {"role": "user", "content": f"CANDIDATE PROFILE:\n{brief}\n\nFORM FIELDS:\n{field_desc}"}],
        temperature=0.1,
    )
    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", reply, re.DOTALL)
        data = json.loads(m.group(0)) if m else {"mappings": []}
    mappings = data.get("mappings", []) if isinstance(data, dict) else []
    # keep only mappings that reference a real field
    valid_keys = {(f.get("name") or f.get("id") or f.get("label")) for f in fields}
    valid_keys |= {f.get("selector") for f in fields}
    out = []
    for m in mappings:
        if isinstance(m, dict) and m.get("key") and "value" in m:
            out.append({"key": str(m["key"]), "value": str(m["value"])})
    return out


def fill_mapped_fields(driver, fields: list[dict[str, Any]],
                       mappings: list[dict[str, str]],
                       resume_path: str | None = None) -> dict[str, int]:
    """Fill mapped fields on the page. Returns counts {filled, skipped, uploaded}."""
    by_key = {}
    for f in fields:
        for k in (f.get("name"), f.get("id"), f.get("label"), f.get("selector")):
            if k:
                by_key[k] = f
                by_key[k.lower()] = f
    filled = skipped = uploaded = 0
    for m in mappings:
        f = by_key.get(m["key"]) or by_key.get(m["key"].lower())
        if not f:
            skipped += 1
            continue
        sel, val, ftype = f["selector"], m["value"], f["type"]
        try:
            if val == "__RESUME__" and resume_path:
                driver.upload(sel, resume_path)
                uploaded += 1
            elif f["tag"] == "select":
                driver.select(sel, val)
                filled += 1
            elif ftype in ("checkbox", "radio"):
                driver.check(sel, val.lower() in ("yes", "true", "1", "checked"))
                filled += 1
            elif ftype == "file":
                if resume_path:
                    driver.upload(sel, resume_path)
                    uploaded += 1
                else:
                    skipped += 1
            else:
                driver.fill(sel, val)
                filled += 1
        except Exception:
            skipped += 1
    return {"filled": filled, "skipped": skipped, "uploaded": uploaded}


# ---------------------------------------------------------------------------
# Shared ATS flow (single-page application form)
# ---------------------------------------------------------------------------
def ats_apply_flow(driver, job: dict[str, Any], candidate: dict[str, Any],
                   resume_path: str | None, llm,
                   submit_texts: tuple[str, ...] = ("submit application", "submit"),
                   name: str = "ats") -> dict[str, Any]:
    url = job.get("apply_url") or job.get("source_url", "")
    if not url:
        return {"applied": False, "confirmation": "", "note": "no apply URL"}

    driver.goto(url)
    driver.wait(2500)

    blocked = BoardAdapter.page_looks_human_blocked(driver)
    if blocked:
        return {"applied": False, "confirmation": "",
                "note": f"human-only step detected ({blocked}); needs manual completion",
                "screenshot": driver.screenshot()}

    fields = driver.form_fields()
    if not fields:
        return {"applied": False, "confirmation": "",
                "note": "no form fields found; page may need login or JS render",
                "screenshot": driver.screenshot()}

    mappings = llm_map_fields(llm, fields, candidate)
    stats = fill_mapped_fields(driver, fields, mappings, resume_path)

    # resume fallback: if the LLM missed the file input, upload to the first one
    if resume_path and stats["uploaded"] == 0:
        for sel in driver.find_file_inputs():
            try:
                driver.upload(sel, resume_path)
                stats["uploaded"] += 1
                break
            except Exception:
                continue

    submitted = False
    for text in submit_texts:
        try:
            driver.click_text(text)
            submitted = True
            break
        except Exception:
            continue
    if not submitted:
        # last resort: click the first submit-type button
        for b in driver.find_submit_buttons():
            try:
                driver.click(b["selector"])
                submitted = True
                break
            except Exception:
                continue

    if not submitted:
        return {"applied": False, "confirmation": "",
                "note": f"fields filled {stats}, but no submit button found",
                "screenshot": driver.screenshot()}

    driver.wait(4000)
    marker = BoardAdapter.confirmation_seen(driver)
    shot = driver.screenshot()
    if marker:
        return {"applied": True, "confirmation": marker,
                "note": f"fields filled {stats}", "screenshot": shot}
    return {"applied": False, "confirmation": "",
            "note": f"submitted but no confirmation marker (fields {stats}); treat as unverified",
            "screenshot": shot}


# ---------------------------------------------------------------------------
# Guided multi-step flow (classic boards: click Apply, step through)
# ---------------------------------------------------------------------------
def guided_apply(driver, job: dict[str, Any], candidate: dict[str, Any],
                 resume_path: str | None, llm,
                 apply_texts: tuple[str, ...] = ("easy apply", "apply now", "apply"),
                 max_steps: int = 8, name: str = "board") -> dict[str, Any]:
    url = job.get("apply_url") or job.get("source_url", "")
    if not url:
        return {"applied": False, "confirmation": "", "note": "no apply URL"}
    driver.goto(url)
    driver.wait(2500)

    clicked = False
    for text in apply_texts:
        try:
            driver.click_text(text)
            clicked = True
            driver.wait(2500)
            break
        except Exception:
            continue
    if not clicked:
        return {"applied": False, "confirmation": "",
                "note": "apply button not found; may need login",
                "screenshot": driver.screenshot()}

    for step in range(max_steps):
        blocked = BoardAdapter.page_looks_human_blocked(driver)
        if blocked:
            return {"applied": False, "confirmation": "",
                    "note": f"step {step}: human-only step ({blocked})",
                    "screenshot": driver.screenshot()}
        marker = BoardAdapter.confirmation_seen(driver)
        if marker:
            return {"applied": True, "confirmation": marker,
                    "note": f"completed in {step} steps",
                    "screenshot": driver.screenshot()}

        fields = [f for f in driver.form_fields() if f["tag"] != "button"]
        if fields:
            mappings = llm_map_fields(llm, fields, candidate)
            fill_mapped_fields(driver, fields, mappings, resume_path)

        # advance: Next / Continue / Review / Submit
        advanced = False
        for text in ("submit application", "submit", "review", "continue", "next"):
            try:
                driver.click_text(text)
                advanced = True
                driver.wait(2500)
                break
            except Exception:
                continue
        if not advanced:
            return {"applied": False, "confirmation": "",
                    "note": f"step {step}: no next/submit button; likely needs login or manual step",
                    "screenshot": driver.screenshot()}

    return {"applied": False, "confirmation": "",
            "note": f"max steps ({max_steps}) reached without confirmation",
            "screenshot": driver.screenshot()}
