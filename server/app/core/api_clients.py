"""
Centralized API Client Managers with automatic key rotation.
When one API key fails (rate limit, auth error, etc.), automatically tries the next key.
Supports: Groq, Mistral, OpenRouter
"""
import asyncio
import time
from app.core.logger import add_log


class GroqClientManager:
    """Manages multiple Groq API keys with automatic failover."""

    def __init__(self, api_keys: list):
        from groq import Groq
        self.clients = [Groq(api_key=key) for key in api_keys]
        self.current_index = 0
        self.total_keys = len(self.clients)
        add_log(f"[API_CLIENTS] GroqClientManager initialized with {self.total_keys} keys")

    def _next_client(self):
        """Rotate to the next client."""
        self.current_index = (self.current_index + 1) % self.total_keys

    async def call(self, model: str, messages: list, **kwargs) -> object:
        """
        Call Groq API with automatic key rotation on failure.
        Tries each key once before giving up.
        """
        last_error = None

        for attempt in range(self.total_keys):
            client = self.clients[self.current_index]
            key_num = self.current_index + 1

            try:
                def _do_call():
                    return client.chat.completions.create(
                        model=model,
                        messages=messages,
                        **kwargs
                    )

                response = await asyncio.to_thread(_do_call)
                add_log(f"[GROQ_OK] Key #{key_num} succeeded")
                return response

            except Exception as e:
                last_error = e
                error_str = str(e)
                add_log(f"[GROQ_FAIL] Key #{key_num} failed: {error_str[:100]}")
                self._next_client()

                # Small delay before trying next key
                if attempt < self.total_keys - 1:
                    await asyncio.sleep(0.1)

        # All keys exhausted
        add_log(f"[GROQ_EXHAUSTED] All {self.total_keys} keys failed")
        raise last_error


class MistralClientManager:
    """Manages multiple Mistral API keys with automatic failover."""

    def __init__(self, api_keys: list):
        from mistralai import Mistral
        self.clients = [Mistral(api_key=key) for key in api_keys]
        self.current_index = 0
        self.total_keys = len(self.clients)
        add_log(f"[API_CLIENTS] MistralClientManager initialized with {self.total_keys} keys")

    def _next_client(self):
        """Rotate to the next client."""
        self.current_index = (self.current_index + 1) % self.total_keys

    async def call(self, model: str, messages: list, **kwargs) -> object:
        """
        Call Mistral API with automatic key rotation on failure.
        Tries each key once before giving up.
        """
        last_error = None

        for attempt in range(self.total_keys):
            client = self.clients[self.current_index]
            key_num = self.current_index + 1

            try:
                response = client.chat.complete(
                    model=model,
                    messages=messages,
                    **kwargs
                )
                add_log(f"[MISTRAL_OK] Key #{key_num} succeeded")
                return response

            except Exception as e:
                last_error = e
                error_str = str(e)
                add_log(f"[MISTRAL_FAIL] Key #{key_num} failed: {error_str[:100]}")
                self._next_client()

                if attempt < self.total_keys - 1:
                    await asyncio.sleep(0.1)

        add_log(f"[MISTRAL_EXHAUSTED] All {self.total_keys} keys failed")
        raise last_error


class OpenRouterClientManager:
    """Manages multiple OpenRouter API keys with automatic failover."""

    def __init__(self, api_keys: list):
        from openai import OpenAI
        self.clients = [
            OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
            for key in api_keys
        ]
        self.current_index = 0
        self.total_keys = len(self.clients)
        add_log(f"[API_CLIENTS] OpenRouterClientManager initialized with {self.total_keys} keys")

    def _next_client(self):
        """Rotate to the next client."""
        self.current_index = (self.current_index + 1) % self.total_keys

    async def call(self, model: str, messages: list, **kwargs) -> object:
        """
        Call OpenRouter API with automatic key rotation on failure.
        Tries each key once before giving up.
        """
        last_error = None

        for attempt in range(self.total_keys):
            client = self.clients[self.current_index]
            key_num = self.current_index + 1

            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **kwargs
                )
                add_log(f"[OPENROUTER_OK] Key #{key_num} succeeded")
                return response

            except Exception as e:
                last_error = e
                error_str = str(e)
                add_log(f"[OPENROUTER_FAIL] Key #{key_num} failed: {error_str[:100]}")
                self._next_client()

                if attempt < self.total_keys - 1:
                    await asyncio.sleep(0.1)

        add_log(f"[OPENROUTER_EXHAUSTED] All {self.total_keys} keys failed")
        raise last_error


# ── Singleton instances (initialized on first import of config) ──

groq_manager: GroqClientManager = None
mistral_manager: MistralClientManager = None
openrouter_manager: OpenRouterClientManager = None


def init_clients(groq_keys: list, mistral_keys: list, openrouter_keys: list):
    """Initialize all client managers. Called once from config.py."""
    global groq_manager, mistral_manager, openrouter_manager

    groq_manager = GroqClientManager(groq_keys)
    mistral_manager = MistralClientManager(mistral_keys)
    openrouter_manager = OpenRouterClientManager(openrouter_keys)
