"""Boards package: one adapter per job board / ATS."""
from .registry import get_adapter, list_boards

__all__ = ["get_adapter", "list_boards"]
