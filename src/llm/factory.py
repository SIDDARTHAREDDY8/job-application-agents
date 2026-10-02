"""Create an LLMClient from config / environment. This is the 'connect any LLM' entry point."""

from __future__ import annotations
import os
from .base import LLMClient, LLMConfig
from .providers import AnthropicClient, GeminiClient, OpenAICompatibleClient


# Defaults per provider so `LLM_PROVIDER=ollama` just works.
PROVIDER_DEFAULTS: dict[str, dict] = {
    "openai":     {"model": "gpt-4o-mini", "base_url": None},
    "anthropic":  {"model": "claude-sonnet-4-20250514", "base_url": None},
    "gemini":     {"model": "gemini-2.0-flash", "base_url": None},
    "ollama":     {"model": "llama3.1:8b", "base_url": "http://localhost:11434/v1"},
    "openrouter": {"model": "openai/gpt-4o-mini", "base_url": "https://openrouter.ai/api/v1"},
    "groq":       {"model": "llama-3.3-70b-versatile", "base_url": "https://api.groq.com/openai/v1"},
    "together":   {"model": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "base_url": "https://api.together.xyz/v1"},
    "deepseek":   {"model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"},
    "mistral":    {"model": "mistral-large-latest", "base_url": "https://api.mistral.ai/v1"},
    "lmstudio":   {"model": "local-model", "base_url": "http://localhost:1234/v1"},
}

OPENAI_COMPATIBLE = {"openai", "ollama", "openrouter", "groq", "together", "deepseek", "mistral", "lmstudio", "custom"}


def from_env() -> LLMClient:
    """Build a client purely from environment variables.

    Required:
        LLM_PROVIDER  one of: openai, anthropic, gemini, ollama, openrouter,
                      groq, together, deepseek, mistral, lmstudio, custom
    Optional:
        LLM_MODEL     overrides the provider default
        LLM_API_KEY   (not needed for ollama / lmstudio)
        LLM_BASE_URL  overrides the provider default (required for provider=custom)
        LLM_TEMPERATURE, LLM_MAX_TOKENS
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower().strip()
    return create(
        provider=provider,
        model=os.getenv("LLM_MODEL") or None,
        api_key=os.getenv("LLM_API_KEY") or None,
        base_url=os.getenv("LLM_BASE_URL") or None,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
    )


def create(
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    **extra,
) -> LLMClient:
    provider = provider.lower().strip()
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    cfg = LLMConfig(
        provider=provider,
        model=model or defaults.get("model") or "gpt-4o-mini",
        api_key=api_key,
        base_url=base_url or defaults.get("base_url"),
        temperature=temperature,
        max_tokens=max_tokens,
        extra=extra,
    )
    if provider == "anthropic":
        return AnthropicClient(cfg)
    if provider == "gemini":
        return GeminiClient(cfg)
    if provider in OPENAI_COMPATIBLE:
        return OpenAICompatibleClient(cfg)
    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        f"Choose from: {sorted(set(list(PROVIDER_DEFAULTS) + ['custom']))}"
    )


def list_providers() -> list[str]:
    return sorted(set(list(PROVIDER_DEFAULTS) + ["custom"]))
