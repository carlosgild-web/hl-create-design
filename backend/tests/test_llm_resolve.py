"""Which model answers: probes, 429 classification, `auto`, and `llm-check` (decision 0016)."""

import json
from pathlib import Path

import httpx
import pytest

from app import cli
from app.agent.service import probe_turn
from app.core.config import Settings
from app.llm import ollama as ollama_mod
from app.llm.base import LLMError, QuotaExhausted
from app.llm.factory import make_client, reset_shared
from app.llm.fake import FakeClient, say
from app.llm.fallback import SwitchingClient
from app.llm.groq import GroqClient, GroqProbe
from app.llm.ollama import OllamaClient, OllamaProbe
from app.llm.resolve import (
    ProviderStatus,
    check_providers,
    current_resolution,
    reset_auto,
    resolve_auto,
)

MODEL = "qwen-test"

TPM = (
    "Rate limit reached for model `m` in organization `org_x` service tier `on_demand` on "
    "tokens per minute (TPM): Limit 8000, Used 6500, Requested 2400. Please try again in 6.9s."
)
TPD = (
    "Rate limit reached for model `m` in organization `org_x` service tier `on_demand` on "
    "tokens per day (TPD): Limit 200000, Used 199500, Requested 2400. "
    "Please try again in 3h10m5.5s."
)
RPD = "Rate limit reached ... on requests per day (RPD): Limit 1000, Used 1000, Requested 1."


@pytest.fixture(autouse=True)
def fresh_cache():
    reset_auto()
    reset_shared()
    yield
    reset_auto()
    reset_shared()


@pytest.fixture(autouse=True)
def no_local_ollama(monkeypatch):
    """Tests decide whether Ollama is "installed"; the real machine never leaks in."""
    monkeypatch.setattr(ollama_mod, "find_ollama", lambda: None)


def settings(**kw) -> Settings:
    return Settings(
        _env_file=None, llm_provider=kw.pop("llm_provider", "auto"), ollama_model=MODEL, **kw
    )


def groq_says(status: int, **kw) -> httpx.MockTransport:
    return httpx.MockTransport(lambda r: httpx.Response(status, **kw))


def limited(message: str, **kw) -> httpx.MockTransport:
    return groq_says(429, json={"error": {"message": message}}, **kw)


OK_BODY = {"choices": [{"message": {"content": "p"}}]}


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


# --- Groq: realistic probe and 429 classification --------------------------------------


def groq_client(transport, sleep=lambda s: None) -> GroqClient:
    return GroqClient("gsk_t", "m", transport=transport, sleep=sleep)


def test_groq_probe_sends_a_real_first_turn():
    seen = {}

    def answer(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=OK_BODY)

    probe = groq_client(httpx.MockTransport(answer)).probe(*probe_turn())

    assert probe == GroqProbe("ok", "quota available (m)") and probe.usable
    assert seen["messages"][0]["role"] == "system" and len(seen["messages"][0]["content"]) > 1000
    assert {t["function"]["name"] for t in seen["tools"]} >= {"request_create_design"}
    # room for a whole turn is asked for (refused if the daily quota lacks it), under 8k TPM
    assert 2000 <= seen["max_tokens"] <= 5000


def test_per_minute_limit_is_usable_and_says_so():
    probe = groq_client(limited(TPM)).probe()
    assert probe.state == "per_minute" and probe.usable
    assert "per-minute tokens limit" in probe.detail and "7 s" in probe.detail


def test_daily_token_limit_reports_usage_and_reset():
    probe = groq_client(limited(TPD)).probe()
    assert probe.state == "daily" and not probe.usable
    assert "daily token quota used up" in probe.detail
    assert "used 199,500 of 200,000" in probe.detail and "3 h 10 min" in probe.detail


def test_daily_request_limit():
    probe = groq_client(limited(RPD, headers={"retry-after": "600"})).probe()
    assert probe.state == "daily" and "daily request quota" in probe.detail


def test_header_only_429_is_judged_by_the_wait():
    assert groq_client(groq_says(429, headers={"retry-after": "3"}, json={})).probe().usable
    long_wait = groq_client(groq_says(429, headers={"retry-after": "7260"}, json={})).probe()
    assert long_wait.state == "daily" and "2 h 1 min" in long_wait.detail


def test_groq_probe_bad_key_and_unreachable():
    assert (
        groq_client(groq_says(401, json={"error": {"message": "bad"}})).probe().state == "bad_key"
    )
    probe = groq_client(nothing_listening()).probe()
    assert probe.state == "unreachable" and "not reachable" in probe.detail


def test_chat_waits_out_a_per_minute_limit_of_up_to_a_minute():
    replies = iter(
        [
            httpx.Response(429, json={"error": {"message": TPM}}, headers={"retry-after": "50"}),
            httpx.Response(200, json=OK_BODY),
        ]
    )
    waits: list[float] = []
    client = groq_client(httpx.MockTransport(lambda r: next(replies)), sleep=waits.append)

    assert client.chat([], []).content == "p"
    assert waits == [50.5]


def test_chat_never_waits_for_a_daily_limit():
    waits: list[float] = []
    client = groq_client(limited(TPD, headers={"retry-after": "30"}), sleep=waits.append)

    with pytest.raises(Exception, match="daily token quota used up") as err:
        client.chat([], [])

    assert waits == []
    assert "start.cmd" in str(err.value)


def test_chat_error_after_retries_names_the_per_minute_limit():
    client = groq_client(limited(TPM))
    with pytest.raises(Exception, match="per-minute tokens limit"):
        client.chat([], [])


# --- Ollama probe ------------------------------------------------------------------------


def ollama_client(transport) -> OllamaClient:
    return OllamaClient("http://ollama.test", MODEL, transport=transport)


def test_ollama_probe_needs_the_model():
    assert ollama_client(ollama_has(MODEL)).probe().state == "ready"
    assert ollama_client(ollama_has(f"{MODEL}:latest")).probe().usable
    probe = ollama_client(ollama_has("other")).probe()
    assert probe.state == "no_model" and f"ollama pull {MODEL}" in probe.detail


def test_ollama_not_running_vs_not_installed(monkeypatch):
    assert ollama_client(nothing_listening()).probe().state == "not_installed"
    monkeypatch.setattr(ollama_mod, "find_ollama", lambda: Path("ollama"))
    assert ollama_client(nothing_listening()).probe().state == "not_running"


def test_find_ollama_looks_in_the_windows_install_folder(monkeypatch, tmp_path):
    monkeypatch.undo()  # the real find_ollama
    exe = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setattr(ollama_mod.shutil, "which", lambda name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert ollama_mod.find_ollama() == exe


# --- check_providers and resolve_auto ----------------------------------------------------


def test_check_providers_reports_both():
    status = check_providers(
        settings(groq_api_key="gsk_t"),
        groq_transport=limited(TPD),
        ollama_transport=ollama_has(MODEL),
    )
    assert status.groq.state == "daily" and status.ollama.state == "ready"
    assert status.first_usable() == "ollama"


def test_check_providers_follows_the_configured_chain():
    status = check_providers(
        settings(groq_api_key="gsk_t"),
        "ollama",
        groq_transport=never_called(),
        ollama_transport=ollama_has(MODEL),
    )
    assert status.groq is None and status.ollama.usable


def test_no_key_skips_groq_without_calling_it():
    status = check_providers(
        settings(groq_api_key=None),
        groq_transport=never_called(),
        ollama_transport=nothing_listening(),
    )
    assert status.groq.state == "no_key" and status.first_usable() == "fake"


def test_auto_groq_wins_without_probing_ollama():
    res = resolve_auto(
        settings(groq_api_key="gsk_t"),
        probe_turn(),
        groq_transport=groq_says(200, json=OK_BODY),
        ollama_transport=never_called(),
    )
    assert res.provider == "groq" and res.skipped == ()


def test_auto_ollama_when_groq_quota_is_used_up():
    res = resolve_auto(
        settings(groq_api_key="gsk_t"),
        groq_transport=limited(TPD),
        ollama_transport=ollama_has(MODEL),
    )
    assert res.provider == "ollama"
    assert len(res.skipped) == 1 and res.skipped[0].startswith("groq: daily token quota")


def test_auto_scripted_demo_when_nothing_else_works():
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
    again = resolve_auto(
        settings(groq_api_key="gsk_t"),
        groq_transport=never_called(),
        ollama_transport=never_called(),
    )
    assert again is first is current_resolution()
    assert make_client(settings()) is first.client


# --- llm-check: suggestion and question ---------------------------------------------------

GROQ_OK = GroqProbe("ok", "quota available (m)")
GROQ_DAILY = GroqProbe("daily", "daily token quota used up")
OLLAMA_READY = OllamaProbe("ready", "installed, running, model ready")
OLLAMA_STOPPED = OllamaProbe("not_running", "installed, not running")
OLLAMA_NO_MODEL = OllamaProbe("no_model", "run `ollama pull x`")
OLLAMA_ABSENT = OllamaProbe("not_installed", "not installed")


def answers(*replies):
    """An `ask` that answers in order and records the questions."""
    asked: list[str] = []
    queue = list(replies)

    def ask(question: str, yes_letter: str):
        asked.append(question)
        reply = queue.pop(0)
        return reply if reply is None else (reply == "" or reply.startswith(yes_letter))

    ask.asked = asked
    return ask


def must_not_start(settings):
    raise AssertionError("Ollama must not be started")


def choose(groq, ollama, ask, start=must_not_start, **kw):
    return cli.choose_provider(ProviderStatus(groq, ollama), settings(**kw), ask, start)


def test_groq_ok_is_suggested_and_enter_accepts_it():
    ask = answers("")
    assert choose(GROQ_OK, OLLAMA_READY, ask) == "groq"
    assert ask.asked == ["Use Groq? [Y/n] "]


def test_declining_groq_offers_ollama_or_demo():
    assert choose(GROQ_OK, OLLAMA_READY, answers("n", "")) == "ollama"
    assert choose(GROQ_OK, OLLAMA_READY, answers("n", "d")) == "fake"


def test_groq_used_up_suggests_ollama():
    ask = answers("")
    assert choose(GROQ_DAILY, OLLAMA_READY, ask) == "ollama"
    assert "[O]llama" in ask.asked[0] and "[D]emo" in ask.asked[0]


def test_nothing_available_is_the_demo_without_a_question():
    assert choose(GROQ_DAILY, OLLAMA_ABSENT, answers()) == "fake"
    assert choose(GROQ_DAILY, OLLAMA_NO_MODEL, answers()) == "fake"


def test_offers_to_start_a_stopped_ollama():
    started = []

    def start(s):
        started.append(s)
        return OLLAMA_READY

    assert choose(GROQ_DAILY, OLLAMA_STOPPED, answers(""), start) == "ollama"
    assert started
    assert choose(GROQ_DAILY, OLLAMA_STOPPED, answers("n")) == "fake"
    failed = lambda s: OllamaProbe("not_running", "did not answer within 30 s")  # noqa: E731
    assert choose(GROQ_DAILY, OLLAMA_STOPPED, answers("y"), failed) == "fake"


def test_no_offer_to_start_a_remote_ollama():
    remote = {"ollama_base_url": "http://gpu-box:11434"}
    assert choose(GROQ_DAILY, OLLAMA_STOPPED, answers(), **remote) == "fake"


def test_without_a_terminal_the_suggestion_is_taken_and_nothing_is_started():
    assert choose(GROQ_OK, OLLAMA_READY, answers(None)) == "groq"
    assert choose(GROQ_DAILY, OLLAMA_READY, answers(None)) == "ollama"
    assert choose(GROQ_DAILY, OLLAMA_STOPPED, answers(None)) == "fake"


def test_start_and_wait_polls_until_ollama_answers():
    states = iter([OLLAMA_STOPPED, OLLAMA_STOPPED, OLLAMA_READY])
    started = []
    probe = cli.start_and_wait(
        settings(),
        find=lambda: Path("ollama"),
        start=started.append,
        check=lambda s: next(states),
        sleep=lambda s: None,
    )
    assert probe.usable and started == [Path("ollama")]


def test_start_and_wait_gives_up():
    probe = cli.start_and_wait(
        settings(),
        find=lambda: Path("ollama"),
        start=lambda exe: None,
        check=lambda s: OLLAMA_STOPPED,
        sleep=lambda s: None,
        wait_s=3,
    )
    assert probe.state == "not_running" and "3 s" in probe.detail


def test_llm_check_prints_status_and_writes_the_choice(capsys, tmp_path):
    out = tmp_path / "choice.txt"
    status = ProviderStatus(GROQ_DAILY, OLLAMA_READY)

    assert cli.run_llm_check(settings(), out, check=lambda s: status, ask=answers("d")) == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == "fake" and out.read_text() == "fake"
    assert "Groq      daily token quota used up" in captured.err
    assert "Ollama    installed, running" in captured.err
    assert "Using the demo model" in captured.err


def test_llm_check_with_fake_configured_probes_nothing(capsys):
    def no_check(s):
        raise AssertionError("no probes")

    cli.run_llm_check(settings(llm_provider="fake"), check=no_check, ask=answers())
    assert capsys.readouterr().out.strip() == "fake"


def test_ask_terminal_without_a_tty_returns_none(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False, raising=False)
    assert cli.ask_terminal("Use Groq? [Y/n] ", "y") is None


# --- mid-session switch when Groq's daily quota runs out ---------------------------------


class Scripted(FakeClient):
    def __init__(self, provider, error=None, answer="ok"):
        super().__init__([say(answer)] * 5, model=f"{provider}-model")
        self.provider = provider
        self.error = error
        self.calls_made = 0

    def chat(self, messages, tools):
        self.calls_made += 1
        if self.error:
            raise self.error
        return super().chat(messages, tools)


def test_switches_once_on_a_used_up_quota_and_stays_switched():
    groq = Scripted("groq", QuotaExhausted("daily token quota used up"))
    built = []

    def fallback():
        built.append(1)
        return Scripted("ollama", answer="from ollama")

    client = SwitchingClient(groq, fallback)
    assert client.provider == "groq"

    assert client.chat([], []).content == "from ollama"
    notice = client.take_notice()
    assert notice["from"] == "groq" and notice["to"] == "ollama" and "daily" in notice["reason"]
    assert client.take_notice() is None  # announced once
    assert client.provider == "ollama" and client.model == "ollama-model"

    client.chat([], [])
    assert groq.calls_made == 1 and built == [1]  # Groq is not tried again


def test_other_errors_do_not_switch():
    client = SwitchingClient(Scripted("groq", LLMError("bad key")), lambda: 1 / 0)
    with pytest.raises(LLMError, match="bad key"):
        client.chat([], [])
    assert client.provider == "groq" and client.take_notice() is None


def test_groq_chat_raises_quota_exhausted_only_for_daily_limits():
    with pytest.raises(QuotaExhausted):
        groq_client(limited(TPD)).chat([], [])
    with pytest.raises(LLMError) as err:
        groq_client(limited(TPM)).chat([], [])
    assert not isinstance(err.value, QuotaExhausted)


def test_factory_wraps_groq_once_per_process_and_evals_opt_out():
    s = settings(llm_provider="groq", groq_api_key="gsk_t")
    first = make_client(s)
    assert isinstance(first, SwitchingClient) and make_client(s) is first
    assert isinstance(make_client(s, fallback=False), GroqClient)


def test_fallback_is_ollama_when_ready_else_the_demo(monkeypatch):
    from app.llm import factory

    monkeypatch.setattr(factory, "check_ollama", lambda s: OllamaProbe("ready", ""))
    assert factory.fallback_client(settings()).provider == "ollama"
    monkeypatch.setattr(factory, "check_ollama", lambda s: OllamaProbe("not_running", ""))
    assert factory.fallback_client(settings()).provider == "fake"


# --- the start-script question waits for the person (decision 0017, item 23) -------------


def test_ask_terminal_waits_for_the_answer_and_never_times_out(capsys):
    def ask(reply):
        return cli.ask_terminal("[O/d] ", "o", reader=lambda: reply, interactive=lambda: True)

    assert ask("") is True and ask("O") is True and ask("d") is False
    err = capsys.readouterr().err
    assert "suggestion in" not in err and "No answer" not in err


def test_ask_terminal_on_end_of_input_returns_none():
    def eof():
        raise EOFError

    assert cli.ask_terminal("Use Groq? [Y/n] ", "y", reader=eof, interactive=lambda: True) is None
