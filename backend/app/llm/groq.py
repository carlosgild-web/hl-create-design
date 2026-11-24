"""The cloud providers: OpenAI-compatible `/chat/completions` with native `tools`.

`GroqClient` (decision 0012) and `DahlClient` (decision 0029) are the same client with
another name, key, model and URL. Plain `httpx`, no vendor SDK. The key comes from
`GROQ_API_KEY` / `DAHL_API_KEY`; errors that the person running the tool can fix (no key,
rate limit, no credit, unknown model) say what to do.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.llm.base import (
    ChatTurn,
    LLMClient,
    LLMError,
    Message,
    QuotaExhausted,
    ToolCall,
    ToolSpec,
    report,
    wait,
)

log = logging.getLogger("app.llm")

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_TIMEOUT_S = 60.0
# The free tier has per-minute limits (TPM/RPM) and daily ones (TPD/RPD). A per-minute limit
# is waited out and retried; a daily one is reported at once.
PROBE_TIMEOUT_S = 20.0
# Groq does not report the daily tokens left, but it refuses a request whose prompt plus
# `max_tokens` does not fit. So the probe asks for room for a whole first turn (a real turn
# uses ~2.5k prompt tokens per call over 2-4 calls), staying under the 8k tokens per minute.
PROBE_MAX_TOKENS = 4000
MAX_RETRIES = 4
MAX_WAIT_S = 65.0  # one per-minute window, plus a little
_WAIT_IN_MESSAGE_RE = re.compile(
    r"try again in ((?:[\d.]+h)?(?:[\d.]+m(?!s))?(?:[\d.]+s)?(?:[\d.]+ms)?)", re.IGNORECASE
)
_WAIT_PART_RE = re.compile(r"([\d.]+)(ms|h|m|s)")
_LIMIT_RE = re.compile(r"\((TPM|RPM|TPD|RPD)\)", re.IGNORECASE)
_USAGE_RE = re.compile(r"Limit (\d+), Used (\d+)", re.IGNORECASE)
# Some models (e.g. MiniMax on Dahl) put their reasoning in the reply as <think>...</think>;
# an unclosed block at the start is reasoning cut off by the turn. Never shown to the user.
_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL | re.IGNORECASE)

GroqState = Literal[
    "ok", "per_minute", "daily", "no_credit", "no_key", "bad_key", "unreachable", "error"
]
# HTTP 402: the account's credit is used up (Dahl). Like a daily limit: no retry, and the
# app moves to the next provider (decision 0029).
PAYMENT_REQUIRED = 402


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
        # The day is a rolling window: tokens free up gradually, not all at once.
        frees = f"room for this request frees up in about {_human(self.wait)}" if self.wait else ""
        details = "; ".join(p for p in (usage, frees) if p)
        return f"daily {self.unit[:-1]} quota used up" + (f" ({details})" if details else "")


@dataclass(frozen=True)
class GroqProbe:
    state: GroqState
    detail: str
    model: str | None = None  # Dahl: the model that answered the probe (decision 0031)

    @property
    def usable(self) -> bool:
        """A per-minute limit is still usable: calls wait for the window and retry."""
        return self.state in ("ok", "per_minute")


class GroqClient(LLMClient):
    provider = "groq"
    label = "Groq"  # in messages to the person running the app
    key_env = "GROQ_API_KEY"
    model_env = "GROQ_MODEL"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] | None = None,  # tests; default: interruptible wait
    ) -> None:
        if not api_key:
            raise LLMError(f"LLM_PROVIDER={self.provider} needs {self.key_env}. Set it in .env.")
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
            raise LLMError(f"{self.label} took too long to answer ({exc}).") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.label} is not reachable at {self._base_url}: {exc}") from exc
        if not response.is_success:
            used_up = response.status_code == PAYMENT_REQUIRED or (
                response.status_code == 429 and rate_limit(response).scope == "day"
            )
            if used_up:
                raise QuotaExhausted(self._error_text(response))
            raise LLMError(self._error_text(response))

        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise LLMError(f"{self.label} returned no answer for {self.model}.")
        message = choices[0].get("message") or {}
        calls = [_call(c) for c in message.get("tool_calls") or ()]
        usage = data.get("usage") or {}
        return ChatTurn(
            content=_THINK_RE.sub("", message.get("content") or "").strip(),
            tool_calls=tuple(c for c in calls if c is not None),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
        )

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        """POST, waiting out per-minute limits (HTTP 429); a daily limit returns at once.
        Each wait is reported (`report("rate_limited")`) and can be interrupted."""
        for attempt in range(MAX_RETRIES + 1):
            started = time.perf_counter()
            response = self._http.post("/chat/completions", json=body)
            ms = (time.perf_counter() - started) * 1000
            if response.status_code != 429:
                _log_call(self.provider, self.model, response, ms)
                return response
            limit = rate_limit(response)
            log.warning(
                "%s %s: 429 %s limit, wait %s s (%.0f ms)",
                self.provider,
                self.model,
                limit.scope,
                f"{limit.wait:.1f}" if limit.wait is not None else "?",
                ms,
            )
            if attempt == MAX_RETRIES:
                return response
            if limit.scope == "day" or limit.wait is None or limit.wait > MAX_WAIT_S:
                return response
            report("rate_limited", provider=self.provider, scope=limit.scope, wait_s=limit.wait)
            wait(limit.wait + 0.5, self._sleep)
        return response  # pragma: no cover

    def probe(
        self, messages: list[Message] | None = None, tools: list[ToolSpec] | None = None
    ) -> GroqProbe:
        """Can the provider serve a real turn right now? Send `messages` and `tools` (the size of a
        first chat turn: system prompt and tool specs) with a tiny `max_tokens`, no retries.
        Without them it sends a one-word ping, which says little about the token limits."""
        body = self._body(messages or [Message("user", "ping")], tools or [])
        body["max_tokens"] = PROBE_MAX_TOKENS
        try:
            response = self._http.post("/chat/completions", json=body, timeout=PROBE_TIMEOUT_S)
        except httpx.TimeoutException:
            return GroqProbe("unreachable", f"{self.label} did not answer in time")
        except httpx.HTTPError as exc:
            name = type(exc).__name__
            return GroqProbe("unreachable", f"{self.label} is not reachable ({name})")
        if response.is_success:
            return GroqProbe("ok", f"quota available ({self.model})")
        if response.status_code == 429:
            limit = rate_limit(response)
            return GroqProbe("per_minute" if limit.scope == "minute" else "daily", limit.describe())
        if response.status_code == PAYMENT_REQUIRED:
            return GroqProbe("no_credit", "no credit left on the account")
        if response.status_code in (401, 403):
            return GroqProbe("bad_key", f"the API key was rejected (check {self.key_env})")
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
        name = self.label
        if status == PAYMENT_REQUIRED:
            return (
                f"{name} has no credit left for {self.model}. "
                f"Restart with start.cmd to use another model. ({reason})"
            )
        if status == 429:
            limit = rate_limit(response)
            if limit.scope == "minute":
                retry = f" Retry in about {limit.wait:.0f} s." if limit.wait else ""
                return (
                    f"{name} rate limit reached for {self.model}: {limit.describe()}.{retry} "
                    f"({reason})"
                )
            return (
                f"{name} rate limit reached for {self.model}: {limit.describe()}. "
                "Restart with start.cmd to use Ollama or the demo model. "
                f"({reason})"
            )
        if status in (401, 403):
            return f"{name} rejected the API key. Check {self.key_env}."
        if status == 404 or "model" in reason.lower() and status == 400:
            return f"{name} has no usable model '{self.model}'. Check {self.model_env}. ({reason})"
        return f"{name} error {status} for {self.model}: {reason}"


class DahlClient(GroqClient):
    """Dahl inference (inference.dahl.global): OpenAI-compatible, so the same client
    (decision 0029). It answers 429 when a model is at capacity, and 402 when the account's
    credit is used up.

    With `fallback_models` (decision 0031), a 429 or a timeout moves the call to the next
    model at once instead of waiting; the client stays on the model that answered, and says
    so once through `take_notice()`. When every model is busy, it waits out the last 429 on
    the current model as before."""

    provider = "dahl"
    label = "Dahl"
    key_env = "DAHL_API_KEY"
    model_env = "DAHL_MODEL"

    def __init__(
        self, api_key: str, model: str, *, fallback_models: Sequence[str] = (), **kwargs: Any
    ) -> None:
        super().__init__(api_key, model, **kwargs)
        self._models = tuple(dict.fromkeys([model, *fallback_models]))
        self._notice: dict[str, str] | None = None

    def _others(self) -> list[str]:
        """The models after the current one, wrapping round, in the configured order."""
        i = self._models.index(self.model) if self.model in self._models else -1
        return [*self._models[i + 1 :], *self._models[: max(i, 0)]]

    def _move_to(self, model: str, reason: str) -> None:
        log.warning("dahl: %s %s, trying %s", self.model, reason, model)
        previous, self.model = self.model, model
        report("model_switched", provider=self.provider, from_model=previous, to_model=model)
        self._notice = {
            "code": "model_switched",
            "from": previous,
            "to": model,
            "provider": self.provider,
            "model": model,
            "reason": reason,
        }

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        tried = {self.model}
        while True:
            body["model"] = self.model
            try:
                started = time.perf_counter()
                response = self._http.post("/chat/completions", json=body)
            except httpx.TimeoutException:
                untried = [m for m in self._others() if m not in tried]
                if not untried:
                    raise
                self._move_to(untried[0], "did not answer in time")
                tried.add(self.model)
                continue
            if response.status_code != 429:
                ms = (time.perf_counter() - started) * 1000
                _log_call(self.provider, self.model, response, ms)
                return response
            untried = [m for m in self._others() if m not in tried]
            if not untried or rate_limit(response).scope == "day":
                return super()._post(body)  # every model busy: wait it out on this one
            self._move_to(untried[0], "is at capacity")
            tried.add(self.model)

    def probe(
        self, messages: list[Message] | None = None, tools: list[ToolSpec] | None = None
    ) -> GroqProbe:
        """Probe each model in order and stay on the first that answers. If none does, the
        result of the first model is reported (a per-minute limit is still usable)."""
        first: GroqProbe | None = None
        for model in self._models:
            self.model = model
            result = super().probe(messages, tools)
            result = GroqProbe(result.state, result.detail, model)
            if result.state == "ok":
                if model != self._models[0]:
                    head = first.detail if first else "busy"
                    detail = f"{result.detail}; {self._models[0]}: {head}"
                    result = GroqProbe("ok", detail, model)
                return result
            if result.state in ("bad_key", "no_credit"):
                self.model = self._models[0]
                return result
            first = first or result
        self.model = self._models[0]
        assert first is not None
        return first

    def take_notice(self) -> dict[str, str] | None:
        notice, self._notice = self._notice, None
        return notice


def _human(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{max(minutes, 1)} min"
    return f"{minutes // 60} h {minutes % 60} min"


def _log_call(provider: str, model: str, response: httpx.Response, ms: float) -> None:
    tokens = ""
    if response.is_success:
        try:
            usage = response.json().get("usage") or {}
            tokens = (
                f", {usage.get('prompt_tokens', '?')}+{usage.get('completion_tokens', '?')} tokens"
            )
        except ValueError:
            pass
    log.info("%s %s: HTTP %d in %.0f ms%s", provider, model, response.status_code, ms, tokens)


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
    return ToolCall(raw.get("id") or f"call_{name}", name, _arguments(function.get("arguments")))


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
