"""The local provider: Ollama's `/api/chat` with native `tools` (decision 0002, 0009).

Runs on the user's own PC, so no key is needed and nothing leaves the machine. Small
models sometimes write a tool call as text instead of using the `tool_calls` field;
`_calls_from_text` recovers those here, so the agent loop never sees the quirk.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from app.llm.base import ChatTurn, LLMClient, LLMError, Message, ToolCall, ToolSpec

DEFAULT_TIMEOUT_S = 180.0
PROBE_TIMEOUT_S = 3.0
NUM_CTX = 8192

OllamaState = Literal["ready", "no_model", "not_running", "not_installed"]


@dataclass(frozen=True)
class OllamaProbe:
    state: OllamaState
    detail: str

    @property
    def usable(self) -> bool:
        return self.state == "ready"


def find_ollama() -> Path | None:
    """The `ollama` executable: on PATH, or where the Windows installer puts it."""
    found = shutil.which("ollama")
    if found:
        return Path(found)
    local = os.environ.get("LOCALAPPDATA")
    candidate = Path(local) / "Programs" / "Ollama" / "ollama.exe" if local else None
    return candidate if candidate and candidate.is_file() else None


def start_ollama(executable: Path) -> None:
    """Start `ollama serve` in the background, detached and without a window. It keeps
    running after the app stops, like the Ollama tray app would."""
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        # its own process group, so Ctrl+C in the start window does not stop it
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([str(executable), "serve"], **kwargs)  # noqa: S603 - our own executable


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_TAGGED_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_FENCED_JSON_RE = re.compile(r"^```(?:json)?\s*(\{.*\})\s*```$", re.DOTALL)
# `tool_name{"arg": 1}` or `tool_name({"arg": 1})`: the whole message is exactly one call.
_NAME_JSON_RE = re.compile(r"^(\w+)\s*\(?\s*(\{.*\})\s*\)?$", re.DOTALL)


class OllamaClient(LLMClient):
    provider = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self._base_url, timeout=timeout, transport=transport)
        self._ids = itertools.count(1)

    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> ChatTurn:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [_to_ollama(m) for m in messages],
            "stream": False,
            "options": {"temperature": 0, "num_ctx": NUM_CTX},
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
            response = self._http.post("/api/chat", json=body)
        except httpx.TimeoutException as exc:
            raise LLMError(f"Ollama at {self._base_url} took too long to answer ({exc}).") from exc
        except httpx.HTTPError as exc:
            raise LLMError(
                f"Ollama is not reachable at {self._base_url}. Start Ollama, or set "
                "OLLAMA_BASE_URL."
            ) from exc
        if not response.is_success:
            raise LLMError(self._error_text(response))

        data = response.json()
        message = data.get("message") or {}
        content = _THINK_RE.sub("", message.get("content") or "").strip()
        offered = {t.name for t in tools}
        tool_calls = [self._call(c) for c in message.get("tool_calls") or ()]
        tool_calls = [c for c in tool_calls if c is not None]
        if not tool_calls and offered:
            recovered = _calls_from_text(content, offered)
            if recovered:
                tool_calls = [self._new_call(name, args) for name, args in recovered]
                content = ""
        return ChatTurn(
            content=content,
            tool_calls=tuple(tool_calls),
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=int(data.get("eval_count") or 0),
        )

    def probe(self) -> OllamaProbe:
        """Is Ollama running here, with the configured model pulled? If it does not answer,
        is it installed on this machine (so it could be started)?"""
        try:
            response = self._http.get("/api/tags", timeout=PROBE_TIMEOUT_S)
            names = {m.get("name") for m in response.json().get("models") or ()}
        except (httpx.HTTPError, ValueError, AttributeError):
            if find_ollama() is not None:
                return OllamaProbe("not_running", f"installed, not running at {self._base_url}")
            return OllamaProbe("not_installed", f"not installed (nothing at {self._base_url})")
        if self.model in names or f"{self.model}:latest" in names:
            return OllamaProbe("ready", f"installed, running, model ready ({self.model})")
        return OllamaProbe(
            "no_model",
            f"running, but model '{self.model}' is not pulled (run `ollama pull {self.model}`)",
        )

    def close(self) -> None:
        self._http.close()

    # --- helpers ---------------------------------------------------------------------

    def _new_call(self, name: str, arguments: Any) -> ToolCall:
        return ToolCall(f"ollama_{next(self._ids)}", name, _arguments(arguments))

    def _call(self, raw: dict[str, Any]) -> ToolCall | None:
        function = raw.get("function") or {}
        name = function.get("name")
        return self._new_call(name, function.get("arguments")) if name else None

    def _error_text(self, response: httpx.Response) -> str:
        try:
            reason = str(response.json().get("error") or response.text)
        except ValueError:
            reason = response.text
        if response.status_code == 404 and "not found" in reason.lower():
            return (
                f"Ollama has no model '{self.model}'. Run `ollama pull {self.model}` or set "
                "OLLAMA_MODEL."
            )
        return f"Ollama error {response.status_code} for {self.model}: {reason.strip()}"


def _to_ollama(message: Message) -> dict[str, Any]:
    data: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        data["tool_calls"] = [
            {"function": {"name": c.name, "arguments": c.arguments}} for c in message.tool_calls
        ]
    if message.role == "tool" and message.name:
        data["tool_name"] = message.name
    return data


def _arguments(raw: Any) -> dict[str, Any]:
    """Ollama sends a dict; some models send a JSON string, or nothing."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {"__invalid__": raw}
        return parsed if isinstance(parsed, dict) else {"__invalid__": raw}
    return {"__invalid__": str(raw)}


def _calls_from_text(content: str, offered: set[str]) -> list[tuple[str, Any]]:
    """Tool calls written as text: `<tool_call>{...}</tool_call>`, a fenced JSON block or a
    bare JSON object, with `name` (one of the offered tools) and `arguments`; or the whole
    message as `tool_name{...}`."""
    candidates = _TAGGED_CALL_RE.findall(content)
    if not candidates:
        text = content.strip()
        fenced = _FENCED_JSON_RE.match(text)
        if fenced:
            candidates = [fenced.group(1)]
        elif text.startswith("{") and text.endswith("}"):
            candidates = [text]
    found: list[tuple[str, Any]] = []
    if not candidates:
        named = _NAME_JSON_RE.match(content.strip())
        if named and named.group(1) in offered:
            try:
                arguments = json.loads(named.group(2))
            except ValueError:
                return found
            return [(named.group(1), arguments)]
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("name") in offered:
            found.append((data["name"], data.get("arguments", data.get("parameters"))))
    return found
