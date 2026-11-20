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
PROBE_TIMEOUT_S = 8.0
MAX_RETRIES = 4
MAX_WAIT_S = 30.0
DAILY_WAIT_S = 900.0  # a wait this long is a daily quota, not a per-minute limit
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

    def probe(self) -> tuple[bool, str]:
        """Is this provider usable right now? One tiny request (a few tokens), no retries.
        A daily quota that is used up is "no"; a short per-minute limit is still "yes"."""
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 4,
            "temperature": 0,
        }
        try:
            response = self._http.post("/chat/completions", json=body, timeout=PROBE_TIMEOUT_S)
        except httpx.TimeoutException:
            return False, "Groq did not answer in time"
        except httpx.HTTPError as exc:
            return False, f"Groq is not reachable ({type(exc).__name__})"
        if response.is_success:
            return True, "ok"
        if response.status_code == 429:
            wait = _retry_wait(response)
            if wait is not None and wait <= MAX_WAIT_S:
                return True, "rate-limited for a moment; calls wait and retry"
            if wait is not None and wait <= DAILY_WAIT_S:
                return False, f"Groq is rate-limited for about {_human(wait)}"
            when = f", resets in about {_human(wait)}" if wait else ""
            return False, f"Groq daily quota used up{when}"
        return False, self._error_text(response)

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
            wait = _retry_wait(response)
            if wait is not None and wait <= DAILY_WAIT_S:
                retry = f"Retry in about {wait:g} s."
                return f"Groq rate limit reached for {self.model}. {retry} ({reason})"
            when = f" (resets in about {_human(wait)})" if wait else ""
            return (
                f"Groq rate limit reached for {self.model}: the daily quota is used up{when}. "
                "Restart with start.cmd to use Ollama or the demo model, or set "
                f"LLM_PROVIDER=auto. ({reason})"
            )
        if status in (401, 403):
            return "Groq rejected the API key. Check GROQ_API_KEY."
        if status == 404 or "model" in reason.lower() and status == 400:
            return f"Groq has no usable model '{self.model}'. Check GROQ_MODEL. ({reason})"
        return f"Groq error {status} for {self.model}: {reason}"


def _human(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{max(minutes, 1)} min"
    return f"{minutes // 60} h {minutes % 60} min"


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
