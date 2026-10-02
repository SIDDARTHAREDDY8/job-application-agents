"""Abstract LLM interface. Every provider implements this."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMConfig:
    provider: str = "openai"          # openai | anthropic | gemini | ollama | openrouter | groq | together | custom
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None       # for ollama / custom OpenAI-compatible endpoints
    temperature: float = 0.7
    max_tokens: int = 2000
    extra: dict[str, Any] = field(default_factory=dict)


class LLMClient(ABC):
    """Any LLM that can chat can drive the agents."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Send chat messages, return the assistant's text reply."""
        raise NotImplementedError

    def chat_system_user(self, system: str, user: str, **kwargs: Any) -> str:
        return self.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )

    @property
    def model_name(self) -> str:
        return self.config.model
