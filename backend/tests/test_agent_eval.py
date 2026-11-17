"""The scenario suite passes on the scripted model, and the harness can really fail.

The second half matters as much as the first: an eval that can't fail proves nothing.
"""

from __future__ import annotations

import json

import pytest

from app import cli
from app.agent import tools as agent_tools
from app.evals import harness, report
from app.evals.harness import Expect, Scenario, Turn
from app.evals.scenarios import SCENARIOS, check, request_create
from app.llm.fake import FakeClient, call, say


def run(scenario: Scenario):
    return harness.run_scenario(scenario, harness.scripted(), provider="fake", model="scripted")


def failed(result) -> set[str]:
    return {c.name for c in result.failures}


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_scenario_passes_on_the_scripted_model(scenario):
    result = run(scenario)
    assert result.passed, report.console([result])


def test_the_suite_covers_the_plan():
    assert len(SCENARIOS) >= 25
    tags = {t for s in SCENARIOS for t in s.tags}
    assert {"rules", "sap", "safety", "injection", "es", "fill", "gate"} <= tags


# --- the harness fails when it should -------------------------------------------------

CREATE = (
    "Create C",
    [
        request_create(
            department="HW",
            design_number="HL-HW-26-0042",
            revision="C",
            name="Bead Drill Controller",
            designer="C. Velazquez",
        ),
        say("ok"),
    ],
)


def test_a_wrong_expectation_fails():
    sc = Scenario("t", "t", (Turn(*CREATE[:1], CREATE[1]),), Expect(cards=()))
    assert "cards" in failed(run(sc))


def test_an_uncited_answer_fails_the_citation_check():
    sc = Scenario(
        "t",
        "t",
        (
            Turn(
                "x",
                [
                    check(department="HW", design_number="HL-HW-26-0042", revision="B"),
                    say("Not allowed. [99-invented#ref]"),
                ],
            ),
        ),
        Expect(tools=("validate_design_request",), cite=True),
    )
    assert "cites_manual" in failed(run(sc))


def test_a_script_that_is_not_used_up_fails():
    sc = Scenario("t", "t", (Turn("x", [say("hi"), say("never played")]),), Expect())
    assert "script_fully_used" in failed(run(sc))


def test_a_loop_that_never_ends_must_be_declared_as_limit():
    sc = Scenario("t", "t", (Turn("x", [call("sap_list_departments")] * 6),), Expect())
    assert "final_status" in failed(run(sc))


def test_a_tool_that_writes_inside_the_model_loop_is_caught(monkeypatch):
    """If a tool ever created files without the click (invariant 2), the eval says so."""

    def leaky(args, ctx):
        folder = ctx.settings.designs_root / "HW" / args.design_number / args.revision
        folder.mkdir(parents=True)
        return agent_tools.ToolResult({"ok": True})

    tool = next(t for t in agent_tools.TOOLS if t.name == "request_create_design")
    monkeypatch.setattr(
        agent_tools,
        "TOOLS",
        tuple(
            agent_tools.Tool(t.name, t.description, t.args, leaky) if t is tool else t
            for t in agent_tools.TOOLS
        ),
    )
    monkeypatch.setattr(
        agent_tools.ToolRegistry,
        "__init__",
        lambda self, tools=agent_tools.TOOLS: setattr(self, "_tools", {t.name: t for t in tools}),
    )
    sc = Scenario(
        "t", "t", (Turn(*CREATE[:1], CREATE[1]),), Expect(tools=("request_create_design",))
    )
    assert "no_unconfirmed_side_effects" in failed(run(sc))


def test_a_crash_fails_only_that_scenario():
    def boom(env):
        raise RuntimeError("setup broke")

    sc = Scenario("t", "t", (Turn("x", [say("hi")]),), Expect(), setup=boom)
    result = run(sc)
    assert not result.passed and "setup broke" in result.error


# --- CLI and reports ------------------------------------------------------------------


def test_cli_agent_eval_writes_reports(tmp_path, settings, capsys):
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    code = cli.main(
        [
            "agent-eval",
            "--fake",
            "--only",
            "create-valid",
            "--json",
            str(out_json),
            "--markdown",
            str(out_md),
        ],
        settings,
    )
    assert code == 0
    assert "1/1 scenarios passed" in capsys.readouterr().out
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["passed"] == data["total"] == 1 and data["scenarios"][0]["id"] == "create-valid"
    assert "| `create-valid`" in out_md.read_text(encoding="utf-8")


def test_cli_agent_eval_unknown_scenario(settings, capsys):
    assert cli.main(["agent-eval", "--fake", "--only", "nope"], settings) == 2


def test_cli_agent_eval_provider_not_available(settings, capsys):
    assert cli.main(["agent-eval", "--provider", "anthropic"], settings) == 1
    assert "Phase 7" in capsys.readouterr().err


def test_report_lists_failures():
    sc = Scenario("t", "t", (Turn("x", [say("hi")]),), Expect(cards=("create_design",)))
    text = report.to_markdown([run(sc)])
    assert "## Failures" in text and "**cards**" in text


def test_cli_agent_eval_stops_when_the_model_is_unreachable(settings, monkeypatch, capsys):
    from app.llm.base import LLMError

    class Down(FakeClient):
        def chat(self, messages, tools):
            raise LLMError("Ollama has no model 'x'")

    monkeypatch.setattr(cli, "make_client", lambda s: Down())
    assert cli.main(["agent-eval", "--provider", "ollama"], settings) == 1
    assert "not reachable" in capsys.readouterr().err
