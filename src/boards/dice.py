"""Dice adapter (tech-contract heavy). Session login recommended."""
from __future__ import annotations
from typing import Any
from urllib.parse import quote_plus
from .base import BoardAdapter, guided_apply


class DiceAdapter(BoardAdapter):
    name = "dice"
    domains = ("dice.com",)
    LOGIN_URL = "https://www.dice.com/dashboard/login"

    def search_jobs(self, driver, query: str, location: str = "") -> list[dict[str, Any]]:
        url = (f"https://www.dice.com/jobs?q={quote_plus(query)}"
               f"&location={quote_plus(location)}&filters.postedDate=SEVEN")
        driver.goto(url)
        driver.wait(4000)
        cards = driver.page.evaluate(r"""
            () => Array.from(document.querySelectorAll('dhi-search-card, .search-card'))
              .slice(0, 25).map(el => {
                const a = el.querySelector('a[href*="/job-detail/"]');
                const title = el.querySelector('.card-title-link, a[href*="/job-detail/"]')?.innerText.trim() || '';
                const company = el.querySelector('[data-cy="search-card-company-link"]')?.innerText.trim() || '';
                return {title, company, url: a ? a.href.split('?')[0] : ''};
              }).filter(j => j.url)
        """)
        return [{
            "company": c["company"], "role": c["title"], "location": location,
            "role_type": "", "jd_text": "", "contact_name": "", "contact_title": "",
            "contact_email": "", "email_source": "", "source_url": c["url"],
            "apply_url": c["url"], "board": "dice", "why_hidden": "", "fit_note": "",
        } for c in cards]

    def apply(self, driver, job: dict[str, Any], candidate: dict[str, Any],
              resume_path: str | None, llm) -> dict[str, Any]:
        return guided_apply(
            driver, job, candidate, resume_path, llm,
            apply_texts=("apply now", "easy apply", "apply"),
            max_steps=8, name=self.name,
        )
