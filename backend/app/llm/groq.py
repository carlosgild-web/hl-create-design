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
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.llm.base import ChatTurn, LLMClient, LLMError, Message, ToolCall, ToolSpec

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_TIMEOUT_S = 60.0
# The free tier has per-minute limits (TPM/RPM) and daily ones (TPD/RPD). A per-minute limit
# is waited out and retried; a daily one is reported at once.
PROBE_TIMEOUT_S = 15.0
PROBE_MAX_TOKENS = 8
MAX_RETRIES = 4
MAX_WAIT_S = 65.0  # one per-minute window, plus a little
_WAIT_IN_MESSAGE_RE = re.compile(
    r"try again in ((?:[\d.]+h)?(?:[\d.]+m(?!s))?(?:[\d.]+s)?(?:[\d.]+ms)?)", re.IGNORECASE
)
_WAIT_PART_RE = re.compile(r"([\d.]+)(ms|h|m|s)")
_LIMIT_RE = re.compile(r"\((TPM|RPM|TPD|RPD)\)", re.IGNORECASE)
_USAGE_RE = re.compile(r"Limit (\d+), Used (\d+)", re.IGNORECASE)

GroqState = Literal["ok", "per_minute", "daily", "no_key", "bad_key", "unreachable", "error"]


@dataclass(frozen=True)
class RateLimit:
    """What a 429 means: a per-minute or a daily limit, how long to wait, and the usage
    Groq reports ("Limit 200000, Used 199500") when it says so."""

    scope: Literal["minute", "day"]
    wait: float | None
    unit: str = "tokens"  # or "requests"
    limit: int | None = None
    used: int | None = None

    def describe(self) -> str:
        if self.scope == "minute":
            when = f"; calls wait about {self.wait:.0f} s and retry" if self.wait else ""
            return f"per-minute {self.unit} limit reached for the moment{when}"
        usage = f"used {self.used:,} of {self.limit:,}" if self.used and self.limit else ""
        resets = f"resets in about {_human(self.wait)}" if self.wait else ""
        details = "; ".join(p for p in (usage, resets) if p)
        return f"daily {self.unit[:-1]} quota used up" + (f" ({details})" if details else "")


@dataclass(frozen=True)
class GroqProbe:
    state: GroqState
    detail: str

    @property
    def usable(self) -> bool:
        """A per-minute limit is still usable: calls wait for the window and retry."""
        return self.state in ("ok", "per_minute")


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

    def _body(self, messages: list[Message], tools: list[ToolSpec]) -> dict[str, Any]:
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
        return body

    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> ChatTurn:
        body = self._body(messages, tools)
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
        """POST, waiting out per-minute limits (HTTP 429); a daily limit returns at once."""
        for attempt in range(MAX_RETRIES + 1):
            response = self._http.post("/chat/completions", json=body)
            if response.status_code != 429 or attempt == MAX_RETRIES:
                return response
            limit = rate_limit(response)
            if limit.scope == "day" or limit.wait is None or limit.wait > MAX_WAIT_S:
                return response
            self._sleep(limit.wait + 0.5)
        return response  # pragma: no cover

    def probe(
        self, messages: list[Message] | None = None, tools: list[ToolSpec] | None = None
    ) -> GroqProbe:
        """Can Groq serve a real turn right now? Send `messages` and `tools` (the size of a
        first chat turn: system prompt and tool specs) with a tiny `max_tokens`, no retries.
        Without them it sends a one-word ping, which says little about the token limits."""
        body = self._body(messages or [Message("user", "ping")], tools or [])
        body["max_tokens"] = PROBE_MAX_TOKENS
        try:
            response = self._http.post("/chat/completions", json=body, timeout=PROBE_TIMEOUT_S)
        except httpx.TimeoutException:
            return GroqProbe("unreachable", "Groq did not answer in time")
        except httpx.HTTPError as exc:
            return GroqProbe("unreachable", f"Groq is not reachable ({type(exc).__name__})")
        if response.is_success:
            return GroqProbe("ok", f"quota available ({self.model})")
        if response.status_code == 429:
            limit = rate_limit(response)
            return GroqProbe("per_minute" if limit.scope == "minute" else "daily", limit.describe())
        if response.status_code in (401, 403):
            return GroqProbe("bad_key", "the API key was rejected (check GROQ_API_KEY)")
        return GroqProbe("error", self._error_text(response))

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
            limit = rate_limit(response)
            if limit.scope == "minute":
                retry = f" Retry in about {limit.wait:.0f} s." if limit.wait else ""
                return (
                    f"Groq rate limit reached for {self.model}: {limit.describe()}.{retry} "
                    f"({reason})"
                )
            return (
                f"Groq rate limit reached for {self.model}: {limit.describe()}. "
                "Restart with start.cmd to use Ollama or the demo model. "
                f"({reason})"
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


def rate_limit(response: httpx.Response) -> RateLimit:
    """Classify a 429 by Groq's message ("... on tokens per day (TPD): Limit 200000, Used
    199500, Requested 2400. Please try again in 3h10m5s."). Without that text (a bare
    Retry-After), a wait over two minutes is taken as a daily limit."""
    text = response.text
    wait = _retry_wait(response)
    kind = _LIMIT_RE.search(text)
    if kind:
        code = kind.group(1).upper()
        scope: Literal["minute", "day"] = "day" if code.endswith("D") else "minute"
        unit = "requests" if code.startswith("R") else "tokens"
    else:
        lowered = text.lower()
        scope = "day" if "per day" in lowered or (wait is not None and wait > 120) else "minute"
        unit = "requests" if "requests per" in lowered else "tokens"
    usage = _USAGE_RE.search(text)
    limit, used = (int(usage.group(1)), int(usage.group(2))) if usage else (None, None)
    return RateLimit(scope, wait, unit, limit, used)


def _retry_wait(response: httpx.Response) -> float | None:
    """Seconds Groq asks us to wait: the Retry-After header, else 'try again in 3h10m5.5s'."""
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    match = _WAIT_IN_MESSAGE_RE.search(response.text)
    if not match or not match.group(1):
        return None
    factor = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
    return sum(float(n) * factor[u] for n, u in _WAIT_PART_RE.findall(match.group(1)))


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
