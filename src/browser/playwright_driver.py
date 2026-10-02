"""PlaywrightManager: the agents' hands on the web.

- Persistent browser profile (state/browser_profile/) so logins survive restarts.
  Log in ONCE manually (headed mode), the session is reused afterwards.
- form_fields(): extracts every input/select/textarea on the page with its label,
  so the LLM can map candidate data onto application forms.
- Screenshots on demand for debugging.

Setup on any computer:
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations
import os
from typing import Any


FORM_FIELDS_JS = r"""
() => {
  const els = Array.from(document.querySelectorAll('input, select, textarea, button[type=submit]'));
  const out = [];
  const seen = new Set();
  function cssPath(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && parts.length < 4) {
      let sel = cur.tagName.toLowerCase();
      if (cur.name) sel += `[name="${cur.name}"]`;
      else {
        const sibs = Array.from(cur.parentNode ? cur.parentNode.children : [])
          .filter(e => e.tagName === cur.tagName);
        if (sibs.length > 1) sel += `:nth-of-type(${sibs.indexOf(cur) + 1})`;
      }
      parts.unshift(sel);
      cur = cur.parentNode;
    }
    return parts.join(' > ');
  }
  for (const el of els) {
    const type = (el.type || el.tagName).toLowerCase();
    if (type === 'hidden' || type === 'submit' && el.tagName !== 'BUTTON') {
      if (el.tagName === 'INPUT' && (type === 'submit' || type === 'hidden')) continue;
    }
    let label = '';
    if (el.labels && el.labels.length) label = el.labels[0].innerText.trim();
    if (!label) label = el.getAttribute('aria-label') || '';
    if (!label) label = el.getAttribute('placeholder') || '';
    if (!label && el.id) {
      const lab = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (lab) label = lab.innerText.trim();
    }
    if (!label) {
      // walk up: nearest preceding text-ish sibling
      let p = el.parentElement;
      if (p) {
        const t = (p.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
        if (t.length) label = t[0].slice(0, 80);
      }
    }
    const key = (el.name || el.id || label || type) + '|' + type;
    if (seen.has(key)) continue;
    seen.add(key);
    const field = {
      tag: el.tagName.toLowerCase(),
      type: type,
      name: el.name || '',
      id: el.id || '',
      label: label.slice(0, 120),
      selector: cssPath(el),
      required: !!(el.required || el.getAttribute('aria-required') === 'true'),
      value: (el.value || '').slice(0, 200),
    };
    if (el.tagName === 'SELECT') {
      field.options = Array.from(el.options).map(o => o.text.trim()).filter(Boolean).slice(0, 60);
    }
    if (el.tagName === 'INPUT' && (type === 'checkbox' || type === 'radio')) {
      field.checked = !!el.checked;
    }
    out.push(field);
  }
  return out;
}
"""


class PlaywrightManager:
    """Thin, agent-friendly wrapper around Playwright."""

    def __init__(self, headless: bool = True, profile_dir: str = "state/browser_profile",
                 slow_mo_ms: int = 0):
        self.headless = headless
        self.profile_dir = profile_dir
        self.slow_mo_ms = slow_mo_ms
        self._pw = None
        self._context = None
        self._page = None

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise ImportError(
                "Playwright is required for browser automation. Install it with:\n"
                "    pip install playwright\n"
                "    playwright install chromium"
            ) from e
        os.makedirs(self.profile_dir, exist_ok=True)
        self._pw = sync_playwright().start()
        self._context = self._pw.chromium.launch_persistent_context(
            self.profile_dir,
            headless=self.headless,
            slow_mo=self.slow_mo_ms,
            viewport={"width": 1366, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"),
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self

    def close(self):
        try:
            if self._context:
                self._context.close()
        finally:
            if self._pw:
                self._pw.stop()
            self._pw = self._context = self._page = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()

    @property
    def page(self):
        if self._page is None:
            raise RuntimeError("Call start() first (or use 'with PlaywrightManager() as m:').")
        return self._page

    # ------------------------------------------------------------------ navigation
    def goto(self, url: str, wait: str = "domcontentloaded", timeout_ms: int = 30000) -> str:
        self.page.goto(url, wait_until=wait, timeout=timeout_ms)
        return self.page.url

    @property
    def url(self) -> str:
        return self.page.url

    def title(self) -> str:
        return self.page.title()

    def page_text(self, max_chars: int = 8000) -> str:
        try:
            text = self.page.evaluate("() => document.body.innerText || ''")
        except Exception:
            text = ""
        return text[:max_chars]

    # ------------------------------------------------------------------ interaction
    def click(self, selector: str, timeout_ms: int = 10000) -> None:
        self.page.click(selector, timeout=timeout_ms)

    def click_text(self, text: str, timeout_ms: int = 10000) -> None:
        self.page.get_by_text(text, exact=False).first.click(timeout=timeout_ms)

    def fill(self, selector: str, value: str, timeout_ms: int = 10000) -> None:
        self.page.fill(selector, value, timeout=timeout_ms)

    def select(self, selector: str, value: str, timeout_ms: int = 10000) -> None:
        """Select a dropdown option by visible text (falls back to value)."""
        try:
            self.page.select_option(selector, label=value, timeout=timeout_ms)
        except Exception:
            self.page.select_option(selector, value=value, timeout=timeout_ms)

    def check(self, selector: str, checked: bool = True, timeout_ms: int = 10000) -> None:
        self.page.set_checked(selector, checked, timeout=timeout_ms)

    def upload(self, selector: str, file_path: str, timeout_ms: int = 15000) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Upload file not found: {file_path}")
        self.page.set_input_files(selector, file_path, timeout=timeout_ms)

    def wait(self, ms: int) -> None:
        self.page.wait_for_timeout(ms)

    def wait_for_text(self, text: str, timeout_ms: int = 15000) -> bool:
        try:
            self.page.get_by_text(text, exact=False).first.wait_for(timeout=timeout_ms)
            return True
        except Exception:
            return False

    def screenshot(self, path: str = "state/last_screenshot.png") -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.page.screenshot(path=path, full_page=False)
        return path

    # ------------------------------------------------------------------ form introspection
    def form_fields(self) -> list[dict[str, Any]]:
        """Every fillable field on the current page: label, type, selector, options."""
        try:
            return self.page.evaluate(FORM_FIELDS_JS)
        except Exception:
            return []

    def find_file_inputs(self) -> list[str]:
        fields = self.form_fields()
        return [f["selector"] for f in fields
                if f["tag"] == "input" and f["type"] == "file"]

    def find_submit_buttons(self) -> list[dict[str, Any]]:
        return [f for f in self.form_fields()
                if f["tag"] == "button" or (f["tag"] == "input" and f["type"] == "submit")]
