"""The LLM layer: FakeClient, OllamaClient's translation (over a mocked HTTP API), factory."""

import json

import httpx
import pytest

from app.core.config import Settings
from app.llm.base import LLMError, Message, ToolCall, ToolSpec
from app.llm.factory import make_client
from app.llm.fake import DEMO_NOTICE, FakeClient, FakeScriptExhausted, call, say
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
    with pytest.raises(LLMError, match="Phase 7"):
        make_client(Settings(_env_file=None, llm_provider="anthropic"))


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
