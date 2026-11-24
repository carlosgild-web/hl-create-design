"""Dahl moves to the next model when one is busy (decision 0031)."""

import json

import httpx
import pytest

from app.core.config import Settings
from app.llm.base import LLMError, Message, call_with
from app.llm.factory import reset_shared
from app.llm.groq import DahlClient
from app.llm.resolve import dahl_client, reset_auto, resolve_auto

OK = {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 3}}
BUSY = {"error": {"message": "This model is at concurrency capacity."}}


@pytest.fixture(autouse=True)
def fresh_cache():
    reset_auto()
    reset_shared()
    yield
    reset_auto()
    reset_shared()


def per_model(answers: dict[str, object]) -> tuple[httpx.MockTransport, list[str]]:
    """Each model answers as given: an HTTP status (busy / ok) or an exception class."""
    seen: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        seen.append(model)
        answer = answers[model]
        if isinstance(answer, type):
            raise answer("slow")
        if answer == 429:
            return httpx.Response(429, headers={"retry-after": "10"}, json=BUSY)
        return httpx.Response(200, json=OK)

    return httpx.MockTransport(handle), seen


def client(transport, sleep=lambda s: None) -> DahlClient:
    return DahlClient("dk_t", "a", fallback_models=["b", "c"], transport=transport, sleep=sleep)


def test_settings_list_the_models_in_order_without_repeats():
    s = Settings(_env_file=None, dahl_model="a", dahl_fallback_models=" b, a ,c,")
    assert s.dahl_models == ("a", "b", "c")
    assert Settings(_env_file=None, dahl_model="a", dahl_fallback_models="").dahl_models == ("a",)


def test_a_busy_model_moves_the_call_to_the_next_at_once():
    transport, seen = per_model({"a": 429, "b": 429, "c": 200})
    waits: list[float] = []
    dahl = client(transport, sleep=waits.append)
    events: list[tuple[str, dict]] = []
    listen = lambda k, d: events.append((k, d))  # noqa: E731
    turn = call_with(listen, None, lambda: dahl.chat([Message("user", "x")], []))
    assert turn.content == "hi"
    assert seen == ["a", "b", "c"] and waits == []  # no Retry-After wait
    assert dahl.model == "c"  # and it stays there
    assert [d["to_model"] for k, d in events if k == "model_switched"] == ["b", "c"]
    notice = dahl.take_notice()
    assert notice["code"] == "model_switched" and notice["to"] == "c" and notice["from"] == "b"
    assert dahl.take_notice() is None
    dahl.chat([Message("user", "y")], [])
    assert seen[-1] == "c"


def test_a_timeout_also_moves_to_the_next_model():
    transport, seen = per_model({"a": httpx.ReadTimeout, "b": 200, "c": 200})
    dahl = client(transport)
    assert dahl.chat([Message("user", "x")], []).content == "hi"
    assert seen == ["a", "b"] and dahl.model == "b"


def test_every_model_busy_waits_on_the_last_one_tried():
    transport, seen = per_model({"a": 429, "b": 429, "c": 429})
    waits: list[float] = []
    with pytest.raises(LLMError, match="rate limit"):
        client(transport, sleep=waits.append).chat([Message("user", "x")], [])
    assert seen[:3] == ["a", "b", "c"] and set(seen[3:]) == {"c"} and waits


def test_every_model_timing_out_reports_the_timeout():
    transport, _ = per_model({m: httpx.ReadTimeout for m in "abc"})
    with pytest.raises(LLMError, match="too long"):
        client(transport).chat([Message("user", "x")], [])


def test_probe_starts_on_the_first_model_that_answers():
    transport, seen = per_model({"a": 429, "b": 200, "c": 200})
    probe = client(transport).probe()
    assert probe.state == "ok" and probe.model == "b" and seen == ["a", "b"]
    assert "a:" in probe.detail


def test_probe_with_every_model_busy_reports_the_first():
    transport, _ = per_model({m: 429 for m in "abc"})
    dahl = client(transport)
    probe = dahl.probe()
    assert probe.state == "per_minute" and probe.model == "a" and dahl.model == "a"


def test_auto_starts_the_session_on_the_model_the_probe_found():
    transport, _ = per_model({"a": 429, "b": 200, "c": 200})
    s = Settings(_env_file=None, dahl_api_key="dk_t", dahl_model="a", dahl_fallback_models="b,c")
    res = resolve_auto(s, dahl_transport=transport)
    assert res.provider == "dahl" and res.client.model == "b"


def test_dahl_client_without_fallbacks_keeps_one_model():
    s = Settings(_env_file=None, dahl_api_key="dk_t", dahl_model="a", dahl_fallback_models="")
    transport, seen = per_model({"a": 429})
    dahl = dahl_client(s, transport)
    dahl._sleep = lambda seconds: None
    with pytest.raises(LLMError):
        dahl.chat([Message("user", "x")], [])
    assert set(seen) == {"a"}


def test_the_trace_takes_the_model_that_answered():
    from app.agent.loop import _notice
    from app.agent.trace import AgentTrace

    transport, _ = per_model({"a": 429, "b": 200, "c": 200})
    dahl = client(transport)
    dahl.chat([Message("user", "x")], [])
    trace = AgentTrace("dahl", "a", 6)
    events = list(_notice(dahl, trace, 1))
    assert [e.type for e in events] == ["notice"] and events[0].data["code"] == "model_switched"
    assert trace.model == "b" and trace.to_dict()["model"] == "b"
    assert trace.steps[-1]["type"] == "notice"
