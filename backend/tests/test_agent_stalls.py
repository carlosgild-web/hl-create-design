"""A turn never hangs silently (decision 0017): rate-limit waits are reported as `status`
events, the whole turn is capped by AGENT_TURN_TIMEOUT_S, Stop cancels it, and the user can
switch to another provider."""

from __future__ import annotations

import logging
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agent import runs
from app.agent.service import AgentDeps, chat_turn
from app.api import deps as api_deps
from app.db import store
from app.llm import factory
from app.llm.groq import GroqClient
from app.llm.ollama import OllamaProbe
from app.main import app

TPM = (
    "Rate limit reached for model `m` on tokens per minute (TPM): Limit 8000, Used 7000, "
    "Requested 2500. Please try again in 2s."
)
OK = {"choices": [{"message": {"content": "Hola."}}], "usage": {"prompt_tokens": 9}}


def tpm_429(wait: str = "2") -> httpx.Response:
    return httpx.Response(429, json={"error": {"message": TPM}}, headers={"retry-after": wait})


def groq(replies, sleep=None) -> GroqClient:
    replies = iter(replies)
    return GroqClient(
        "gsk_t", "m", transport=httpx.MockTransport(lambda r: next(replies)), sleep=sleep
    )


def always_limited(wait: str = "30") -> GroqClient:
    return GroqClient("gsk_t", "m", transport=httpx.MockTransport(lambda r: tpm_429(wait)))


def turn(settings, engine, sap, manual, client, **kw):
    d = AgentDeps(settings=settings, engine=engine, client=client, sap=sap, manual=manual, **kw)
    return chat_turn(d, text="hola")


def test_a_rate_limit_wait_is_reported_as_a_status_event(settings, engine, sap, manual, caplog):
    caplog.set_level(logging.INFO, logger="app.llm")
    client = groq([tpm_429("2"), httpx.Response(200, json=OK)], sleep=lambda s: None)

    out = list(turn(settings, engine, sap, manual, client))

    types = [e.type for e in out]
    assert types == ["conversation", "run", "status", "message", "done"]
    status = out[2].data
    assert status["kind"] == "rate_limited" and status["wait_s"] == 2.0
    assert status["provider"] == "groq" and status["scope"] == "minute"
    assert out[-1].data["status"] == "answered"
    # every call is logged: the 429 with its wait, then the answer
    logged = caplog.text
    assert "groq m: 429 minute limit, wait 2.0 s" in logged and "groq m: HTTP 200" in logged


def test_a_stuck_turn_ends_at_the_timeout_and_offers_a_switch(settings, engine, sap, manual):
    settings = settings.model_copy(update={"agent_turn_timeout_s": 0.5})

    out = list(
        turn(
            settings,
            engine,
            sap,
            manual,
            always_limited(),
            switch_options=lambda: ["ollama", "fake"],
        )
    )

    error = next(e.data for e in out if e.type == "error")
    assert error["code"] == "turn_timeout" and error["can_switch_to"] == ["ollama", "fake"]
    assert any(e.type == "status" for e in out)  # the user saw why it was waiting
    done = out[-1].data
    assert done["status"] == "timeout"
    run = store.get_run(engine, done["run_id"])
    assert run["status"] == "timeout" and "0.5 s" in run["trace"]["error"]


def test_stop_cancels_a_run_that_waits_for_the_model(settings, engine, sap, manual):
    events = turn(settings, engine, sap, manual, always_limited())
    seen = []
    for event in events:
        seen.append(event)
        if event.type == "run":
            run_id = event.data["id"]
        if event.type == "status":  # the user presses Stop while it waits
            assert runs.cancel(run_id)

    assert seen[-1].data["status"] == "cancelled"
    assert store.get_run(engine, run_id)["status"] == "cancelled"
    assert not any(e.type == "error" for e in seen)
    assert not runs.cancel(run_id)  # released once finished


def test_stop_between_tool_calls_opens_no_card(settings, engine, sap, manual):
    from app.llm.fake import FakeClient, call, say

    client = FakeClient(
        [
            call("sap_list_departments"),
            call("request_reserve_number", department="HW", name="X", designer="C. V"),
            say("ok"),
        ]
    )
    out = []
    for event in turn(settings, engine, sap, manual, client):
        out.append(event)
        if event.type == "run":
            run_id = event.data["id"]
        if event.type == "tool_result":
            runs.cancel(run_id)

    assert out[-1].data["status"] == "cancelled"
    assert not any(e.type == "pending_action" for e in out)


# --- HTTP: cancel and switch ------------------------------------------------------------


@pytest.fixture
def api(settings, fake_sap):
    app.dependency_overrides[api_deps.settings_dep] = lambda: settings
    app.dependency_overrides[api_deps.sap_factory_dep] = lambda: fake_sap.client
    factory.reset_shared()
    yield TestClient(app)
    app.dependency_overrides.clear()
    factory.reset_shared()


def test_cancel_unknown_run_is_404(api):
    assert api.post("/api/runs/999999/cancel").status_code == 404


def test_cancel_over_http_while_the_stream_waits(api, settings, monkeypatch):
    app.dependency_overrides[api_deps.llm_factory_dep] = lambda: lambda: always_limited()
    app.dependency_overrides[api_deps.switch_options_dep] = lambda: lambda: []
    result: dict = {}

    def stream():
        with api.stream("POST", "/api/chat", json={"message": "hola"}) as response:
            for line in response.iter_lines():
                if line.startswith("data: ") and '"id"' in line and "run_id" not in line:
                    result.setdefault("ids", []).append(line)
                if line.startswith("event: status"):
                    run_id = int(result["ids"][-1].split('"id": ')[1].rstrip("}"))
                    result["cancel"] = api.post(f"/api/runs/{run_id}/cancel").status_code
                if line.startswith("data: ") and '"status": "cancelled"' in line:
                    result["done"] = True

    worker = threading.Thread(target=stream)
    worker.start()
    worker.join(timeout=20)
    assert result.get("cancel") == 200 and result.get("done")


def test_switch_to_the_demo_model_changes_what_answers(api, settings):
    response = api.post("/api/llm/switch", json={"to": "fake"})
    assert response.status_code == 200 and response.json()["provider"] == "fake"
    assert (
        factory.make_client(settings.model_copy(update={"llm_provider": "groq"})).provider == "fake"
    )
    assert api.get("/api/health").json()["llm_provider"] == "fake"


def test_switch_to_ollama_needs_it_running(api, monkeypatch):
    monkeypatch.setattr(factory, "check_ollama", lambda s: OllamaProbe("not_running", ""))
    assert api.post("/api/llm/switch", json={"to": "ollama"}).status_code == 409
    monkeypatch.setattr(factory, "check_ollama", lambda s: OllamaProbe("ready", ""))
    assert api.post("/api/llm/switch", json={"to": "ollama"}).json()["provider"] == "ollama"
    assert api.post("/api/llm/switch", json={"to": "groq"}).status_code == 422


def test_switch_options_skip_the_current_provider(settings, monkeypatch):
    factory.reset_shared()
    monkeypatch.setattr(factory, "check_ollama", lambda s: OllamaProbe("ready", ""))
    assert factory.switch_options(settings) == ["ollama"]  # settings use the demo model
    monkeypatch.setattr(factory, "check_ollama", lambda s: OllamaProbe("not_running", ""))
    assert factory.switch_options(settings) == []
