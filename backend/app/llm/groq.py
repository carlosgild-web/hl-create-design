"""The cloud provider: Groq's OpenAI-compatible `/chat/completions` with native `tools`
(decision 0012).

Plain `httpx`, no vendor SDK. The key comes from `GROQ_API_KEY`; errors that the person
running the tool can fix (no key, rate limit, unknown model) say what to do.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.llm.base import ChatTurn, LLMClient, LLMError, Message, ToolCall, ToolSpec

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_TIMEOUT_S = 60.0
# The free tier allows few tokens per minute. A short wait (a per-minute limit) is retried;
# a long one (a daily limit) is reported at once.
MAX_RETRIES = 4
MAX_WAIT_S = 30.0
_WAIT_IN_MESSAGE_RE = re.compile(r"try again in ([\d.]+)s", re.IGNORECASE)


class GroqClient(LLMClient):
    provider = "groq"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise LLMError("LLM_PROVIDER=groq needs GROQ_API_KEY. Set it in .env.")
        self.model = model
        self._sleep = sleep
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> ChatTurn:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [_to_openai(m) for m in messages],
            "temperature": 0,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        try:
            response = self._post(body)
        except httpx.TimeoutException as exc:
            raise LLMError(f"Groq took too long to answer ({exc}).") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Groq is not reachable at {self._base_url}: {exc}") from exc
        if not response.is_success:
            raise LLMError(self._error_text(response))

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise LLMError(f"Groq returned no answer for {self.model}.")
        message = choices[0].get("message") or {}
        calls = [_call(c) for c in message.get("tool_calls") or ()]
        usage = data.get("usage") or {}
        return ChatTurn(
            content=(message.get("content") or "").strip(),
            tool_calls=tuple(c for c in calls if c is not None),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
        )

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        """POST, waiting and retrying while Groq says a short wait will do (HTTP 429)."""
        for attempt in range(MAX_RETRIES + 1):
            response = self._http.post("/chat/completions", json=body)
            wait = _retry_wait(response) if response.status_code == 429 else None
            if wait is None or wait > MAX_WAIT_S or attempt == MAX_RETRIES:
                return response
            self._sleep(wait + 0.5)
        return response  # pragma: no cover

    def close(self) -> None:
        self._http.close()

    def _error_text(self, response: httpx.Response) -> str:
        try:
            reason = str((response.json().get("error") or {}).get("message") or response.text)
        except (ValueError, AttributeError):
            reason = response.text
        reason = reason.strip()
        status = response.status_code
        if status == 429:
            wait = response.headers.get("retry-after")
            when = f" Retry in about {wait} s." if wait else " Try again later (daily quota?)."
            return f"Groq rate limit reached for {self.model}.{when} ({reason})"
        if status in (401, 403):
            return "Groq rejected the API key. Check GROQ_API_KEY."
        if status == 404 or "model" in reason.lower() and status == 400:
            return f"Groq has no usable model '{self.model}'. Check GROQ_MODEL. ({reason})"
        return f"Groq error {status} for {self.model}: {reason}"


def _retry_wait(response: httpx.Response) -> float | None:
    """Seconds Groq asks us to wait: the Retry-After header, else 'try again in 4.4s'."""
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            return None
    match = _WAIT_IN_MESSAGE_RE.search(response.text)
    return float(match.group(1)) if match else None


def _to_openai(message: Message) -> dict[str, Any]:
    data: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        data["tool_calls"] = [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
            }
            for c in message.tool_calls
        ]
    if message.role == "tool":
        data["tool_call_id"] = message.tool_call_id or ""
    return data


def _call(raw: dict[str, Any]) -> ToolCall | None:
    function = raw.get("function") or {}
    name = function.get("name")
    if not name:
        return None
    return ToolCall(raw.get("id") or f"groq_{name}", name, _arguments(function.get("arguments")))


def _arguments(raw: Any) -> dict[str, Any]:
    """OpenAI-style APIs send the arguments as a JSON string."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {"__invalid__": str(raw)}
    return parsed if isinstance(parsed, dict) else {"__invalid__": str(raw)}
