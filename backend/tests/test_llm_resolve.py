"""`LLM_PROVIDER=auto`: probes and the order groq -> ollama -> fake (decision 0016)."""

import httpx
import pytest

from app.core.config import Settings
from app.llm.factory import make_client
from app.llm.groq import GroqClient
from app.llm.ollama import OllamaClient
from app.llm.resolve import current_resolution, reset_auto, resolve_auto

MODEL = "qwen-test"


@pytest.fixture(autouse=True)
def fresh_cache():
    reset_auto()
    yield
    reset_auto()


def settings(**kw) -> Settings:
    return Settings(_env_file=None, llm_provider="auto", ollama_model=MODEL, **kw)


def groq_says(status: int, **kw) -> httpx.MockTransport:
    return httpx.MockTransport(lambda r: httpx.Response(status, **kw))


def ollama_has(*models: str) -> httpx.MockTransport:
    body = {"models": [{"name": m} for m in models]}
    return httpx.MockTransport(lambda r: httpx.Response(200, json=body))


def nothing_listening() -> httpx.MockTransport:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    return httpx.MockTransport(refuse)


def never_called() -> httpx.MockTransport:
    def fail(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request to {request.url}")

    return httpx.MockTransport(fail)


# --- probes ----------------------------------------------------------------------------


def groq_client(transport) -> GroqClient:
    return GroqClient("gsk_t", "m", transport=transport)


def test_groq_probe_ok():
    ok_body = {"choices": [{"message": {"content": "p"}}]}
    assert groq_client(groq_says(200, json=ok_body)).probe() == (True, "ok")


def test_groq_probe_short_rate_limit_is_still_usable():
    ok, note = groq_client(groq_says(429, headers={"retry-after": "3"}, json={})).probe()
    assert ok and "retry" in note


def test_groq_probe_daily_quota_says_when_it_resets():
    ok, note = groq_client(groq_says(429, headers={"retry-after": "7260"}, json={})).probe()
    assert not ok
    assert "daily quota" in note and "2 h 1 min" in note


def test_groq_probe_bad_key_and_unreachable():
    ok, note = groq_client(groq_says(401, json={"error": {"message": "bad"}})).probe()
    assert not ok and "GROQ_API_KEY" in note
    ok, note = groq_client(nothing_listening()).probe()
    assert not ok and "not reachable" in note


def ollama_client(transport) -> OllamaClient:
    return OllamaClient("http://ollama.test", MODEL, transport=transport)


def test_ollama_probe_needs_the_model():
    assert ollama_client(ollama_has(MODEL)).probe() == (True, "ok")
    assert ollama_client(ollama_has(f"{MODEL}:latest")).probe()[0]
    ok, note = ollama_client(ollama_has("other")).probe()
    assert not ok and f"ollama pull {MODEL}" in note


def test_ollama_probe_not_running():
    ok, note = ollama_client(nothing_listening()).probe()
    assert not ok and "not reachable" in note


# --- resolution order ------------------------------------------------------------------


def test_groq_wins_when_it_has_quota():
    ok_body = {"choices": [{"message": {"content": "p"}}]}
    res = resolve_auto(
        settings(groq_api_key="gsk_t"),
        groq_transport=groq_says(200, json=ok_body),
        ollama_transport=never_called(),
    )
    assert res.provider == "groq" and res.skipped == ()


def test_ollama_when_groq_quota_is_used_up():
    res = resolve_auto(
        settings(groq_api_key="gsk_t"),
        groq_transport=groq_says(429, headers={"retry-after": "3600"}, json={}),
        ollama_transport=ollama_has(MODEL),
    )
    assert res.provider == "ollama"
    assert len(res.skipped) == 1 and res.skipped[0].startswith("groq: Groq daily quota")


def test_no_key_skips_groq_without_calling_it():
    res = resolve_auto(
        settings(groq_api_key=None),
        groq_transport=never_called(),
        ollama_transport=ollama_has(MODEL),
    )
    assert res.provider == "ollama"
    assert res.skipped == ("groq: no GROQ_API_KEY",)


def test_scripted_demo_when_nothing_else_works():
    res = resolve_auto(
        settings(groq_api_key=None),
        groq_transport=never_called(),
        ollama_transport=nothing_listening(),
    )
    assert res.provider == "fake"
    assert [s.split(":")[0] for s in res.skipped] == ["groq", "ollama"]
    assert "skipped" in res.describe()


def test_resolution_is_cached_and_used_by_the_factory():
    first = resolve_auto(
        settings(groq_api_key=None),
        groq_transport=never_called(),
        ollama_transport=nothing_listening(),
    )
    # a second call (different transports would fail the test if it probed again)
    again = resolve_auto(
        settings(groq_api_key="gsk_t"),
        groq_transport=never_called(),
        ollama_transport=never_called(),
    )

    assert again is first is current_resolution()
    assert make_client(settings()) is first.client


# --- resolve_from (the start scripts' check) and `llm-check` -----------------------------

from app import cli  # noqa: E402
from app.llm.resolve import resolve_from  # noqa: E402


def test_explicit_groq_falls_back_when_the_quota_is_gone():
    res = resolve_from(
        settings(groq_api_key="gsk_t"),
        "groq",
        groq_transport=groq_says(429, headers={"retry-after": "3600"}, json={}),
        ollama_transport=ollama_has(MODEL),
    )
    assert res.provider == "ollama" and "daily quota" in res.skipped[0]


def test_explicit_ollama_never_tries_groq():
    res = resolve_from(
        settings(groq_api_key="gsk_t"),
        "ollama",
        groq_transport=never_called(),
        ollama_transport=nothing_listening(),
    )
    assert res.provider == "fake"
    assert [s.split(":")[0] for s in res.skipped] == ["ollama"]


def test_explicit_fake_probes_nothing():
    res = resolve_from(
        settings(), "fake", groq_transport=never_called(), ollama_transport=never_called()
    )
    assert res.provider == "fake" and res.skipped == ()


def test_llm_check_prints_only_the_provider_on_stdout(capsys):
    stub = lambda s: resolve_from(  # noqa: E731
        s, groq_transport=never_called(), ollama_transport=ollama_has(MODEL)
    )

    assert cli.run_llm_check(settings(groq_api_key=None), stub) == 0

    out = capsys.readouterr()
    assert out.out.strip() == "ollama"
    assert "not available - groq: no GROQ_API_KEY" in out.err
    assert "Using ollama" in out.err and "instead" in out.err


def test_llm_check_explains_the_demo_fallback(capsys):
    stub = lambda s: resolve_from(  # noqa: E731
        s, groq_transport=never_called(), ollama_transport=nothing_listening()
    )

    cli.run_llm_check(settings(groq_api_key=None), stub)

    out = capsys.readouterr()
    assert out.out.strip() == "fake"
    assert "scripted demo model" in out.err and "not available - ollama" in out.err


def test_llm_check_with_fake_configured_is_instant(capsys):
    cli.run_llm_check(Settings(_env_file=None, llm_provider="fake"), resolver=None)
    assert capsys.readouterr().out.strip() == "fake"
