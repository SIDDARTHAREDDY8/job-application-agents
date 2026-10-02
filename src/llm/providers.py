"""Provider implementations. Each one wraps a different LLM API behind LLMClient."""

from __future__ import annotations
from .base import LLMClient, LLMConfig


class OpenAICompatibleClient(LLMClient):
    """Covers OpenAI, Ollama, OpenRouter, Groq, Together, DeepSeek, Mistral,
    or any custom OpenAI-compatible endpoint (just set base_url)."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "The 'openai' package is required for this provider. "
                "Install it with: pip install openai"
            ) from e
        kwargs: dict = {}
        if config.api_key:
            kwargs["api_key"] = config.api_key
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = OpenAI(**kwargs)

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        resp = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )
        return (resp.choices[0].message.content or "").strip()


class AnthropicClient(LLMClient):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise ImportError(
                "The 'anthropic' package is required. Install it with: pip install anthropic"
            ) from e
        self._client = Anthropic(api_key=config.api_key) if config.api_key else Anthropic()

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        # Anthropic wants system separate from messages
        system = ""
        convo = []
        for m in messages:
            if m["role"] == "system":
                system += m["content"] + "\n"
            else:
                convo.append(m)
        params: dict = {
            "model": self.config.model,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": convo,  # type: ignore[arg-type]
        }
        if system.strip():
            params["system"] = system.strip()
        if "temperature" in kwargs or self.config.temperature is not None:
            params["temperature"] = kwargs.get("temperature", self.config.temperature)
        resp = self._client.messages.create(**params)
        parts = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts).strip()


class GeminiClient(LLMClient):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise ImportError(
                "The 'google-generativeai' package is required. "
                "Install it with: pip install google-generativeai"
            ) from e
        genai.configure(api_key=config.api_key)
        self._model = genai.GenerativeModel(config.model)

    def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        # Flatten to a single prompt; keep it simple and robust
        prompt = "\n\n".join(
            f"{'System' if m['role']=='system' else m['role'].capitalize()}: {m['content']}"
            for m in messages
        )
        resp = self._model.generate_content(
            prompt,
            generation_config={
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            },
        )
        return (getattr(resp, "text", "") or "").strip()
