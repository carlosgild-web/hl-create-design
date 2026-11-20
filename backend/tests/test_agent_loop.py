"""The bounded loop and the chat service: limits, traces, history, errors."""

import pytest

from app.agent.prompts import EVENT_PREFIX
from app.agent.service import AgentDeps, chat_turn, model_history
from app.db import store
from app.llm.base import ChatTurn, LLMError
from app.llm.fake import FakeClient, call, say


@pytest.fixture
def deps(settings, engine, sap, manual):
    def make(script, **changes):
        s = settings.model_copy(update=changes)
        return AgentDeps(
            settings=s, engine=engine, client=FakeClient(script), sap=sap, manual=manual
        )

    return make


def events(deps, text="hello", **kw):
    return list(chat_turn(deps, text=text, **kw))


def test_plain_answer_is_one_model_call(deps, engine):
    d = deps([say("Hi! Which department?")])
    out = events(d)

    assert [e.type for e in out] == ["conversation", "run", "message", "done"]
    done = out[-1].data
    assert done["status"] == "answered"
    run = store.get_run(engine, done["run_id"])
    assert run["model_calls"] == 1
    assert run["trace"]["input"][0]["role"] == "system"


def test_tool_results_go_back_to_the_model_and_into_the_trace(deps, engine):
    d = deps([call("sap_get_design", design_number="HL-HW-26-0042"), say("It is IN_WORK.")])
    out = events(d, text="status of HL-HW-26-0042?")

    assert [e.type for e in out] == [
        "conversation",
        "run",
        "tool_call",
        "tool_result",
        "message",
        "done",
    ]
    second_call = d.client.calls[1].messages
    assert second_call[-1].role == "tool"
    assert '"status": "IN_WORK"' in second_call[-1].content

    trace = store.get_run(engine, out[-1].data["run_id"])["trace"]
    [tool_step] = [s for s in trace["steps"] if s["type"] == "tool_call"]
    assert tool_step["name"] == "sap_get_design"
    assert tool_step["arguments"] == {"design_number": "HL-HW-26-0042"}
    assert tool_step["result"] == second_call[-1].content  # exactly what the model saw


def test_the_last_allowed_call_offers_no_tools(deps, engine):
    looping = [call("sap_list_departments") for _ in range(2)] + [
        ChatTurn(content="", tool_calls=call("sap_list_departments").tool_calls)
    ]
    d = deps(looping, agent_max_iterations=3)
    out = events(d)

    assert len(d.client.calls) == 3
    assert d.client.calls[-1].tools == []
    assert out[-1].data["status"] == "limit"
    assert "couldn't finish" in out[-2].data["content"]
    assert store.get_run(engine, out[-1].data["run_id"])["model_calls"] == 3


def test_provider_failure_is_an_error_event_and_a_stored_run(deps, engine):
    def broken(messages, tools):
        raise LLMError("Ollama is not reachable")

    out = events(deps([broken]))

    assert [e.type for e in out] == ["conversation", "run", "error", "done"]
    run = store.get_run(engine, out[-1].data["run_id"])
    assert run["status"] == "error"
    assert run["trace"]["error"] == "Ollama is not reachable"


def test_history_continues_without_old_tool_chatter(deps, engine):
    first = events(deps([call("sap_list_departments"), say("Four departments.")]))
    conversation = first[0].data["id"]
    d = deps([say("Hardware it is.")])
    events(d, text="HW please", conversation_id=conversation)

    seen = d.client.calls[0].messages
    assert [m.role for m in seen] == ["system", "user", "assistant", "user"]
    assert "HW please" in seen[-1].content
    stored = store.get_messages(engine, conversation)
    assert [m["role"] for m in stored].count("tool") == 1  # kept, but not replayed


def test_user_text_and_form_reach_the_model_as_labelled_data(deps):
    d = deps([say("ok")])
    events(d, text="name it X", form={"department": "HW"})

    content = d.client.calls[0].messages[-1].content
    assert '<user_data kind="chat">\nname it X\n</user_data>' in content
    assert 'Current form values: {"department": "HW"}' in content


def test_events_become_user_messages_marked_as_backend(engine):
    history = model_history(
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "name": "x"}]},
            {"role": "tool", "content": "{}"},
            {"role": "assistant", "content": "card opened"},
            {"role": "event", "content": f"{EVENT_PREFIX} {{}}"},
        ]
    )
    assert [m.role for m in history] == ["user", "assistant", "user"]
    assert history[-1].content.startswith(EVENT_PREFIX)


def test_unknown_conversation_starts_a_new_one(deps):
    out = events(deps([say("hi")]), conversation_id="does-not-exist")
    assert out[0].data["id"] != "does-not-exist"


def test_spanish_answers_are_asked_for_in_the_prompt(deps):
    d = deps([say("Hola")])
    events(d, language="es")
    assert "Spanish" in d.client.calls[0].messages[0].content


def test_a_provider_switch_is_announced_and_traced(settings, engine, sap, manual):
    from app.llm.base import QuotaExhausted
    from app.llm.fallback import SwitchingClient

    class UsedUp(FakeClient):
        provider = "groq"

        def chat(self, messages, tools):
            raise QuotaExhausted("daily token quota used up")

    client = SwitchingClient(UsedUp(), lambda: FakeClient([say("Hola.")]))
    d = AgentDeps(settings=settings, engine=engine, client=client, sap=sap, manual=manual)
    out = events(d)

    assert [e.type for e in out] == ["conversation", "run", "notice", "message", "done"]
    assert out[2].data["to"] == "fake" and out[2].data["code"] == "provider_switched"
    trace = store.get_run(engine, out[-1].data["run_id"])["trace"]
    [notice] = [s for s in trace["steps"] if s["type"] == "notice"]
    assert notice["from"] == "groq" and "daily" in notice["reason"]


def test_the_switch_is_announced_even_when_the_fallback_fails(settings, engine, sap, manual):
    from app.llm.base import QuotaExhausted
    from app.llm.fallback import SwitchingClient

    class Raises(FakeClient):
        def __init__(self, provider, error):
            super().__init__([])
            self.provider, self.error = provider, error

        def chat(self, messages, tools):
            raise self.error

    client = SwitchingClient(
        Raises("groq", QuotaExhausted("daily")),
        lambda: Raises("ollama", LLMError("Ollama took too long")),
    )
    d = AgentDeps(settings=settings, engine=engine, client=client, sap=sap, manual=manual)
    out = events(d)

    assert [e.type for e in out] == ["conversation", "run", "notice", "error", "done"]
    assert out[2].data["to"] == "ollama"
