import logging

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Raised when the local LLM cannot be reached or returns an error."""


class LLMClient:
    """The only place in the project that talks to the local LLM (Ollama)."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 300,
        timeout: int = 120,
    ):
        self.model = model or settings.LLM_MODEL
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.max_tokens = max_tokens
        self.timeout = timeout

        self._session = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        self._session.mount("http://", HTTPAdapter(max_retries=retry))

    def complete(
        self,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.0,
    ) -> tuple[str, dict]:
        """Send one prompt. Returns (reply text, token usage)."""
        payload = {
            "model": self.model,
            "stream": False,
            "keep_alive": "30s",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": self.max_tokens,
                "num_ctx": 2048,
            },
        }
        if json_mode:
            payload["format"] = "json"

        try:
            response = self._session.post(
                f"{self.base_url}/api/chat", json=payload, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMUnavailableError(
                f"Could not get an answer from Ollama at {self.base_url} "
                f"(model {self.model}). Is Ollama running and is the model "
                f"downloaded? Details: {exc}"
            ) from exc

        data = response.json()
        text = data.get("message", {}).get("content", "")
        usage = {
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
        }
        logger.info(
            "LLM call: model=%s input_tokens=%d output_tokens=%d",
            self.model,
            usage["input_tokens"],
            usage["output_tokens"],
        )
        return text, usage
