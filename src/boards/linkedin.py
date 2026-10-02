"""LinkedIn adapter.

Requires a logged-in session: run once with --headed, log in at
https://www.linkedin.com/login, close the browser. The persistent profile
(state/browser_profile/) keeps the session for later headless runs.

Pace yourself: keep searches/applies slow and human-like. Aggressive
automation risks the account; the driver adds small delays by default.
"""
from __future__ import annotations
from typing import Any
from urllib.parse import quote_plus
from .base import BoardAdapter, guided_apply


class LinkedInAdapter(BoardAdapter):
    name = "linkedin"
    domains = ("linkedin.com",)
    LOGIN_URL = "https://www.linkedin.com/login"

    def search_jobs(self, driver, query: str, location: str = "") -> list[dict[str, Any]]:
        url = (f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(query)}"
               f"&location={quote_plus(location)}&f_TPR=r86400&sortBy=DD")
        driver.goto(url)
        driver.wait(4000)
        cards = driver.page.evaluate(r"""
            () => Array.from(document.querySelectorAll('.job-card-container, .scaffold-layout__list-item'))
              .slice(0, 25).map(el => {
                const a = el.querySelector('a.job-card-container__link, a[href*="/jobs/view"]');
                const title = el.querySelector('.job-card-list__title, .job-card-container__link')?.innerText.trim() || '';
                const company = el.querySelector('.job-card-container__primary-description, .job-card-list__company')?.innerText.trim() || '';
                return {title, company, url: a ? a.href.split('?')[0] : ''};
              }).filter(j => j.url)
        """)
        jobs = []
        for c in cards:
            jobs.append({
                "company": c["company"], "role": c["title"],
                "location": location, "role_type": "",
                "jd_text": "", "contact_name": "", "contact_title": "",
                "contact_email": "", "email_source": "",
                "source_url": c["url"], "apply_url": c["url"],
                "board": "linkedin", "why_hidden": "",
                "fit_note": "",
            })
        return jobs

    def apply(self, driver, job: dict[str, Any], candidate: dict[str, Any],
              resume_path: str | None, llm) -> dict[str, Any]:
        return guided_apply(
            driver, job, candidate, resume_path, llm,
            apply_texts=("easy apply", "apply"),
            max_steps=8, name=self.name,
        )
