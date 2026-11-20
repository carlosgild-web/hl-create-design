"""The LLM layer: FakeClient, OllamaClient's translation (over a mocked HTTP API), factory."""

import json

import httpx
import pytest

from app.core.config import Settings
from app.llm.base import LLMError, Message, ToolCall, ToolSpec
from app.llm.factory import make_client
from app.llm.fake import DEMO_NOTICE, FakeClient, FakeScriptExhausted, call, say
from app.llm.groq import GroqClient
from app.llm.ollama import OllamaClient

SPEC = ToolSpec(
    "sap_get_design",
    "Look up a design",
    {"type": "object", "properties": {"design_number": {"type": "string"}}},
)


def ollama(handler) -> OllamaClient:
    return OllamaClient("http://ollama.test", "qwen-test", transport=httpx.MockTransport(handler))


def reply(message: dict, **extra) -> httpx.Response:
    return httpx.Response(200, json={"message": message, "done": True, **extra})


# --- FakeClient ------------------------------------------------------------------------


def test_fake_client_plays_the_script_then_fails_loudly():
    client = FakeClient([call("sap_get_design", design_number="HL-HW-26-0042"), say("Done")])

    first = client.chat([Message("user", "hi")], [SPEC])
    second = client.chat([], [])

    assert first.tool_calls[0].name == "sap_get_design"
    assert second.content == "Done"
    with pytest.raises(FakeScriptExhausted):
        client.chat([], [])


def test_fake_client_without_script_is_demo_mode():
    assert FakeClient().chat([], []).content == DEMO_NOTICE


def test_factory_picks_the_provider():
    assert make_client(Settings(_env_file=None, llm_provider="fake")).provider == "fake"
    local = make_client(Settings(_env_file=None, llm_provider="ollama", ollama_model="m"))
    assert (local.provider, local.model) == ("ollama", "m")
    assert local._http.timeout.read == 180.0
    slow = make_client(Settings(_env_file=None, llm_provider="ollama", ollama_timeout_s=600))
    assert slow._http.timeout.read == 600.0
    cloud = make_client(Settings(_env_file=None, llm_provider="groq", groq_api_key="gsk_x"))
    assert (cloud.provider, cloud.model) == ("groq", "openai/gpt-oss-120b")
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        make_client(Settings(_env_file=None, llm_provider="groq", groq_api_key=None))


# --- OllamaClient ------------------------------------------------------------------------


def test_ollama_request_uses_native_tools_and_neutral_messages():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return reply({"role": "assistant", "content": "Hola"}, prompt_eval_count=12, eval_count=3)

    history = [
        Message("system", "rules"),
        Message("user", "check HL-HW-26-0042"),
        Message(
            "assistant",
            "",
            tool_calls=(ToolCall("c1", "sap_get_design", {"design_number": "HL-HW-26-0042"}),),
        ),
        Message("tool", '{"found": true}', tool_call_id="c1", name="sap_get_design"),
    ]
    turn = ollama(handler).chat(history, [SPEC])

    assert turn.content == "Hola"
    assert (turn.prompt_tokens, turn.completion_tokens) == (12, 3)
    assert seen["model"] == "qwen-test" and seen["stream"] is False
    assert seen["tools"][0]["function"]["name"] == "sap_get_design"
    assistant, tool = seen["messages"][2], seen["messages"][3]
    assert assistant["tool_calls"][0]["function"]["arguments"] == {"design_number": "HL-HW-26-0042"}
    assert tool == {"role": "tool", "content": '{"found": true}', "tool_name": "sap_get_design"}


def test_ollama_native_tool_calls_get_ids_and_dict_arguments():
    def handler(request):
        return reply(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "sap_get_design", "arguments": {"design_number": "X"}}},
                    {"function": {"name": "sap_get_design", "arguments": '{"design_number": "Y"}'}},
                    {"function": {"name": "sap_get_design", "arguments": "{broken"}},
                ],
            }
        )

    calls = ollama(handler).chat([Message("user", "x")], [SPEC]).tool_calls

    assert [c.arguments for c in calls] == [
        {"design_number": "X"},
        {"design_number": "Y"},
        {"__invalid__": "{broken"},
    ]
    assert len({c.id for c in calls}) == 3


@pytest.mark.parametrize(
    "content",
    [
        '<tool_call>{"name": "sap_get_design", "arguments": {"design_number": "X"}}</tool_call>',
        '```json\n{"name": "sap_get_design", "arguments": {"design_number": "X"}}\n```',
        '{"name": "sap_get_design", "arguments": {"design_number": "X"}}',
        'sap_get_design{"design_number": "X"}',
        ' sap_get_design({"design_number": "X"}) ',
    ],
)
def test_ollama_recovers_tool_calls_written_as_text(content):
    turn = ollama(lambda r: reply({"role": "assistant", "content": content})).chat(
        [Message("user", "x")], [SPEC]
    )
    assert turn.content == ""
    assert [(c.name, c.arguments) for c in turn.tool_calls] == [
        ("sap_get_design", {"design_number": "X"})
    ]


def test_ollama_text_that_names_an_unoffered_tool_stays_text():
    content = '{"name": "delete_everything", "arguments": {}}'
    turn = ollama(lambda r: reply({"role": "assistant", "content": content})).chat(
        [Message("user", "x")], [SPEC]
    )
    assert turn.tool_calls == ()
    assert turn.content == content


@pytest.mark.parametrize(
    "content",
    [
        'delete_everything{"x": 1}',  # not an offered tool
        "sap_get_design{not json}",  # arguments are not JSON
        'Use sap_get_design{"design_number": "X"} to look it up.',  # prose around the call
    ],
)
def test_ollama_name_json_form_is_strict(content):
    turn = ollama(lambda r: reply({"role": "assistant", "content": content})).chat(
        [Message("user", "x")], [SPEC]
    )
    assert turn.tool_calls == ()
    assert turn.content == content


def test_ollama_strips_think_blocks():
    content = "<think>hmm</think>\nThe answer."
    turn = ollama(lambda r: reply({"role": "assistant", "content": content})).chat([], [])
    assert turn.content == "The answer."


def test_ollama_missing_model_says_how_to_pull_it():
    def handler(request):
        return httpx.Response(404, json={"error": "model 'qwen-test' not found"})

    with pytest.raises(LLMError, match="ollama pull qwen-test"):
        ollama(handler).chat([], [])


def test_ollama_not_running_is_a_clear_error():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LLMError, match="not reachable"):
        ollama(handler).chat([], [])


# --- GroqClient --------------------------------------------------------------------------


def groq(handler, sleeps: list[float] | None = None) -> GroqClient:
    log = sleeps if sleeps is not None else []
    return GroqClient(
        "gsk_test", "gpt-test", transport=httpx.MockTransport(handler), sleep=log.append
    )


def completion(message: dict, **usage) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": message}], "usage": usage})


def test_groq_request_is_openai_shaped_with_bearer_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return completion({"content": "ok"})

    history = [
        Message("system", "rules"),
        Message("user", "hi"),
        Message("assistant", "", (ToolCall("c1", "sap_get_design", {"design_number": "X"}),)),
        Message("tool", '{"ok": true}', tool_call_id="c1", name="sap_get_design"),
    ]
    groq(handler).chat(history, [SPEC])

    body = seen["body"]
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["auth"] == "Bearer gsk_test"
    assert body["model"] == "gpt-test" and body["temperature"] == 0
    assert body["tools"][0]["function"]["name"] == "sap_get_design"
    call_msg = body["messages"][2]["tool_calls"][0]
    assert call_msg["id"] == "c1"
    assert json.loads(call_msg["function"]["arguments"]) == {"design_number": "X"}
    assert body["messages"][3]["tool_call_id"] == "c1"


def test_groq_parses_tool_calls_text_and_usage():
    raw = {
        "content": None,
        "tool_calls": [
            {
                "id": "abc",
                "type": "function",
                "function": {"name": "sap_get_design", "arguments": '{"design_number": "Y"}'},
            },
            {"id": "bad", "type": "function", "function": {"name": "t", "arguments": "{oops"}},
        ],
    }
    turn = groq(lambda r: completion(raw, prompt_tokens=11, completion_tokens=4)).chat([], [SPEC])

    assert turn.tool_calls[0] == ToolCall("abc", "sap_get_design", {"design_number": "Y"})
    assert turn.tool_calls[1].arguments == {"__invalid__": "{oops"}
    assert (turn.prompt_tokens, turn.completion_tokens) == (11, 4)


def test_groq_omits_tools_when_none_offered():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return completion({"content": " hello "})

    assert groq(handler).chat([Message("user", "hi")], []).content == "hello"
    assert "tools" not in seen["body"]


def test_groq_rate_limit_says_when_to_retry():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, headers={"retry-after": "42"}, json={"error": {"message": "daily tokens"}}
        )

    with pytest.raises(LLMError, match=r"rate limit.*42 s"):
        groq(handler).chat([], [])


@pytest.mark.parametrize(
    ("status", "expect"),
    [(401, "GROQ_API_KEY"), (404, "GROQ_MODEL"), (500, "Groq error 500")],
)
def test_groq_errors_are_actionable(status, expect):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": "nope"}})

    with pytest.raises(LLMError, match=expect):
        groq(handler).chat([], [])


def test_groq_unreachable_is_an_llm_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(LLMError, match="not reachable"):
        groq(handler).chat([], [])


def test_groq_waits_and_retries_a_short_rate_limit():
    answers = [
        httpx.Response(429, headers={"retry-after": "4"}, json={"error": {"message": "tpm"}}),
        httpx.Response(
            429, json={"error": {"message": "TPM. Please try again in 2.5s."}}
        ),  # no header: read it from the message
        completion({"content": "ok"}),
    ]
    sleeps: list[float] = []

    turn = groq(lambda r: answers.pop(0), sleeps).chat([], [])

    assert turn.content == "ok"
    assert sleeps == [4.5, 3.0]


def test_groq_does_not_wait_for_a_daily_limit():
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, headers={"retry-after": "3600"}, json={"error": {"message": "tokens per day"}}
        )

    with pytest.raises(LLMError, match="rate limit"):
        groq(handler, sleeps).chat([], [])
    assert sleeps == []


def test_groq_gives_up_after_a_few_retries():
    sleeps: list[float] = []
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "1"}, json={"error": {"message": "x"}})

    with pytest.raises(LLMError, match="rate limit"):
        groq(handler, sleeps).chat([], [])
    assert len(calls) == 5 and len(sleeps) == 4
