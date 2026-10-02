"""Indeed adapter. Session login recommended (Google SSO) for full apply flow."""
from __future__ import annotations
from typing import Any
from urllib.parse import quote_plus
from .base import BoardAdapter, guided_apply


class IndeedAdapter(BoardAdapter):
    name = "indeed"
    domains = ("indeed.com",)
    LOGIN_URL = "https://secure.indeed.com/account/login"

    def search_jobs(self, driver, query: str, location: str = "") -> list[dict[str, Any]]:
        url = (f"https://www.indeed.com/jobs?q={quote_plus(query)}"
               f"&l={quote_plus(location)}&fromage=7&sort=date")
        driver.goto(url)
        driver.wait(4000)
        cards = driver.page.evaluate(r"""
            () => Array.from(document.querySelectorAll('.jobsearch-ResultsList > li'))
              .slice(0, 25).map(el => {
                const a = el.querySelector('a.jcs-JobTitle');
                const title = a?.innerText.trim() || '';
                const company = el.querySelector('[data-testid="company-name"]')?.innerText.trim() || '';
                const href = a?.getAttribute('href') || '';
                return {title, company,
                        url: href ? 'https://www.indeed.com' + href.split('&')[0] : ''};
              }).filter(j => j.url)
        """)
        return [{
            "company": c["company"], "role": c["title"], "location": location,
            "role_type": "", "jd_text": "", "contact_name": "", "contact_title": "",
            "contact_email": "", "email_source": "", "source_url": c["url"],
            "apply_url": c["url"], "board": "indeed", "why_hidden": "", "fit_note": "",
        } for c in cards]

    def apply(self, driver, job: dict[str, Any], candidate: dict[str, Any],
              resume_path: str | None, llm) -> dict[str, Any]:
        return guided_apply(
            driver, job, candidate, resume_path, llm,
            apply_texts=("apply now", "apply"),
            max_steps=8, name=self.name,
        )
