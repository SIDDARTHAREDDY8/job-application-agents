"""ZipRecruiter adapter. Session login recommended."""
from __future__ import annotations
from typing import Any
from urllib.parse import quote_plus
from .base import BoardAdapter, guided_apply


class ZipRecruiterAdapter(BoardAdapter):
    name = "ziprecruiter"
    domains = ("ziprecruiter.com",)
    LOGIN_URL = "https://www.ziprecruiter.com/login"

    def search_jobs(self, driver, query: str, location: str = "") -> list[dict[str, Any]]:
        url = (f"https://www.ziprecruiter.com/candidate/search?search={quote_plus(query)}"
               f"&location={quote_plus(location)}&days=7")
        driver.goto(url)
        driver.wait(4000)
        cards = driver.page.evaluate(r"""
            () => Array.from(document.querySelectorAll('[data-testid="job-card"], .job_content'))
              .slice(0, 25).map(el => {
                const a = el.querySelector('a[href*="/jobs/"], a.job_title');
                const title = el.querySelector('a.job_title, h2')?.innerText.trim() || '';
                const company = el.querySelector('a.company_name, .company_name')?.innerText.trim() || '';
                return {title, company, url: a ? a.href.split('?')[0] : ''};
              }).filter(j => j.url)
        """)
        return [{
            "company": c["company"], "role": c["title"], "location": location,
            "role_type": "", "jd_text": "", "contact_name": "", "contact_title": "",
            "contact_email": "", "email_source": "", "source_url": c["url"],
            "apply_url": c["url"], "board": "ziprecruiter", "why_hidden": "", "fit_note": "",
        } for c in cards]

    def apply(self, driver, job: dict[str, Any], candidate: dict[str, Any],
              resume_path: str | None, llm) -> dict[str, Any]:
        return guided_apply(
            driver, job, candidate, resume_path, llm,
            apply_texts=("apply now", "1-click apply", "apply"),
            max_steps=8, name=self.name,
        )
