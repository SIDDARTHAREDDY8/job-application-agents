"""Board registry: URL or name -> adapter instance."""
from __future__ import annotations
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter
from .ashby import AshbyAdapter
from .workable import WorkableAdapter
from .linkedin import LinkedInAdapter
from .indeed import IndeedAdapter
from .dice import DiceAdapter
from .ziprecruiter import ZipRecruiterAdapter
from .glassdoor import GlassdoorAdapter

_ADAPTERS = [
    GreenhouseAdapter(),
    LeverAdapter(),
    AshbyAdapter(),
    WorkableAdapter(),
    LinkedInAdapter(),
    IndeedAdapter(),
    DiceAdapter(),
    ZipRecruiterAdapter(),
    GlassdoorAdapter(),
]


def list_boards() -> list[str]:
    return [a.name for a in _ADAPTERS]


def get_adapter(url_or_name: str):
    """Return the adapter matching a job URL or board name, or None."""
    key = (url_or_name or "").lower().strip()
    for a in _ADAPTERS:
        if a.name == key or a.matches(key):
            return a
    return None
