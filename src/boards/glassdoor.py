"""Glassdoor adapter. Session login recommended."""
from __future__ import annotations
from typing import Any
from urllib.parse import quote_plus
from .base import BoardAdapter, guided_apply


class GlassdoorAdapter(BoardAdapter):
    name = "glassdoor"
    domains = ("glassdoor.com",)
    LOGIN_URL = "https://www.glassdoor.com/profile/login_input.htm"

    def search_jobs(self, driver, query: str, location: str = "") -> list[dict[str, Any]]:
        url = (f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={quote_plus(query)}"
               f"&locT=C&locId=&fromAge=7&sortBy=date_desc")
        driver.goto(url)
        driver.wait(4000)
        cards = driver.page.evaluate(r"""
            () => Array.from(document.querySelectorAll('li[data-test="jobListing"]'))
              .slice(0, 25).map(el => {
                const a = el.querySelector('a[data-test="job-title"]');
                const title = a?.innerText.trim() || '';
                const company = el.querySelector('[data-test="employer-name"]')?.innerText.trim() || '';
                return {title, company, url: a ? a.href.split('?')[0] : ''};
              }).filter(j => j.url)
        """)
        return [{
            "company": c["company"], "role": c["title"], "location": location,
            "role_type": "", "jd_text": "", "contact_name": "", "contact_title": "",
            "contact_email": "", "email_source": "", "source_url": c["url"],
            "apply_url": c["url"], "board": "glassdoor", "why_hidden": "", "fit_note": "",
        } for c in cards]

    def apply(self, driver, job: dict[str, Any], candidate: dict[str, Any],
              resume_path: str | None, llm) -> dict[str, Any]:
        return guided_apply(
            driver, job, candidate, resume_path, llm,
            apply_texts=("easy apply", "apply now", "apply"),
            max_steps=8, name=self.name,
        )
