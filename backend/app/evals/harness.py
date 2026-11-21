"""Plays a scenario against the real agent, tools, validators, actions and database.

Only the outside world is replaced: SAP is the in-memory gateway (served to the real
`SapClient`), kicad-cli is a stub that writes the files it would, and the model is the
scripted `FakeClient` (or a real provider, which ignores the scripts).

The user's clicks are played by the harness through `confirm_action`, the same code as
`POST /api/actions/{id}/confirm`. The scenario's checks are objective: they read tool
calls, the audit log, the file system and the fake SAP, never the model's wording
(except that a cited manual reference must be one the tools actually returned).
"""

from __future__ import annotations

import re
import tempfile
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import Engine

from app.actions import cancel_action, confirm_action
from app.agent.service import AgentDeps, chat_turn
from app.core.config import MANUAL_DIR, Settings
from app.db.session import audit_rows, get_engine
from app.evals.fake_kicad import FakeKicadCli
from app.evals.fake_sap import FakeSap
from app.llm.base import LLMClient
from app.llm.fake import FakeClient, Step
from app.standards.manual_search import ManualIndex, normalize_refs

TODAY = date(2026, 11, 17)  # the demo's pinned date (decision 0007)
MAX_ITERATIONS = 6
CITATION = re.compile(r"\[([\w-]+#[\w-]+)\]")


@dataclass
class Env:
    """The world of one scenario: fresh folders, database, SAP and kicad-cli stub."""

    settings: Settings
    engine: Engine
    sap: FakeSap
    runner: FakeKicadCli

    def make_folder(self, relative: str) -> Path:
        """Pre-existing design folder under DESIGNS_ROOT (for scenario setup)."""
        folder = self.settings.designs_root / relative
        folder.mkdir(parents=True, exist_ok=True)
        return folder


@dataclass(frozen=True)
class Turn:
    text: str
    script: Sequence[Step] = ()  # what the scripted model does (ignored by real models)
    language: Literal["en", "es"] = "en"
    form: dict[str, str] = field(default_factory=dict)
    click: Literal["", "confirm", "cancel"] = ""  # the user's click on the cards of this turn


@dataclass(frozen=True)
class Expect:
    tools: tuple[str, ...] = ()  # each must have been called
    any_tools: tuple[str, ...] = ()  # at least one must have been called (alternative routes)
    not_tools: tuple[str, ...] = ()  # none may have been called
    codes: tuple[str, ...] = ()  # issue/error codes the tools must have reported
    cards: tuple[str, ...] = ()  # card kinds opened, in order
    audit: tuple[str, ...] = ()  # audit actions written, in order
    folders: tuple[str, ...] = ()  # revision folders created under DESIGNS_ROOT
    form: dict[str, str] = field(default_factory=dict)  # fields propose_form_values must set
    status: str = "answered"  # how the last run must end: answered, or limit (cut off)
    cite: bool = False  # the final answer must cite a manual reference the tools returned
    cite_any: tuple[str, ...] = ()  # ...and one of these (the sections that answer it)
    language: Literal["", "en", "es"] = ""  # the final answer is in this language


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    turns: tuple[Turn, ...]
    expect: Expect
    setup: Callable[[Env], None] | None = None
    tags: tuple[str, ...] = ()


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class ScenarioResult:
    id: str
    title: str
    tags: tuple[str, ...]
    provider: str
    model: str
    checks: list[Check]
    tool_calls: list[str]
    answer: str
    seconds: float
    error: str = ""

    @property
    def passed(self) -> bool:
        return not self.error and all(c.ok for c in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "tags": list(self.tags),
            "provider": self.provider,
            "model": self.model,
            "passed": self.passed,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
            "tool_calls": self.tool_calls,
            "answer": self.answer,
            "seconds": round(self.seconds, 2),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioResult:
        """A result saved by `agent-eval --resume` (the inverse of `to_dict`)."""
        return cls(
            id=data["id"],
            title=data["title"],
            tags=tuple(data.get("tags", ())),
            provider=data["provider"],
            model=data["model"],
            checks=[Check(c["name"], c["ok"], c.get("detail", "")) for c in data["checks"]],
            tool_calls=list(data.get("tool_calls", [])),
            answer=data.get("answer", ""),
            seconds=float(data.get("seconds", 0.0)),
            error=data.get("error", ""),
        )


ClientFor = Callable[[Turn], LLMClient]


def scripted() -> ClientFor:
    """Fake provider: a fresh `FakeClient` per turn, playing that turn's script."""
    return lambda turn: FakeClient(list(turn.script))


def real(client: LLMClient) -> ClientFor:
    return lambda turn: client


# --- reading what happened -----------------------------------------------------------


def _walk(value: Any) -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


@dataclass
class Observed:
    tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    cards: list[dict[str, Any]] = field(default_factory=list)  # {id, kind, turn}
    form_fields: dict[str, str] = field(default_factory=dict)
    statuses: list[str] = field(default_factory=list)
    answer: str = ""
    errors: list[str] = field(default_factory=list)
    confirmed_ok: list[str] = field(default_factory=list)  # kinds whose confirm succeeded
    script_left: int = 0

    @property
    def codes(self) -> set[str]:
        return {
            str(v) for r in self.tool_results for k, v in _walk(r) if k == "code" and v is not None
        }

    @property
    def returned_refs(self) -> set[str]:
        return {
            str(v) for r in self.tool_results for k, v in _walk(r) if k in ("ref", "source") and v
        }


def _play_turn(
    turn: Turn,
    index: int,
    *,
    deps_for: Callable[[LLMClient], AgentDeps],
    client_for: ClientFor,
    env: Env,
    conversation: str | None,
    seen: Observed,
) -> str | None:
    client = client_for(turn)
    deps = deps_for(client)
    new_cards: list[dict[str, Any]] = []
    for event in chat_turn(
        deps,
        text=turn.text,
        conversation_id=conversation,
        form=turn.form,
        language=turn.language,
    ):
        data = event.data
        if event.type == "conversation":
            conversation = data["id"]
        elif event.type == "tool_call":
            seen.tool_calls.append((data["name"], data["arguments"]))
        elif event.type == "tool_result":
            seen.tool_results.append(data["result"])
        elif event.type == "form_proposal":
            seen.form_fields |= data["fields"]
        elif event.type == "pending_action":
            card = {"id": data["action"]["id"], "kind": data["action"]["kind"], "turn": index}
            new_cards.append(card)
            seen.cards.append(card)
        elif event.type == "message":
            seen.answer = data["content"]
        elif event.type == "error":
            seen.errors.append(data["message"])
        elif event.type == "done":
            seen.statuses.append(data["status"])
    if isinstance(client, FakeClient):
        seen.script_left += client.remaining

    for card in new_cards:  # the user's click
        if turn.click == "confirm":
            try:
                outcome = confirm_action(
                    card["id"],
                    settings=env.settings,
                    engine=env.engine,
                    sap=deps.sap,
                    runner=env.runner,
                    today=TODAY,
                )
            except Exception as exc:  # a crash is a failed scenario, not a failed eval run
                seen.errors.append(f"confirm crashed: {exc}")
            else:
                if outcome.ok:
                    seen.confirmed_ok.append(card["kind"])
        elif turn.click == "cancel":
            cancel_action(card["id"], engine=env.engine)
    return conversation


# --- checks --------------------------------------------------------------------------


def _folders_created(env: Env, before: set[str]) -> list[str]:
    root = env.settings.designs_root
    if not root.exists():
        return []
    found = {
        p.relative_to(root).as_posix()
        for p in root.glob("*/*/*")
        if p.is_dir() and not p.is_symlink()
    }
    return sorted(found - before)


def _outside_root(env: Env) -> list[str]:
    root = env.settings.designs_root
    if not root.exists():
        return []
    resolved = root.resolve()
    return [
        str(p)
        for p in root.rglob("*")
        if not p.resolve().is_relative_to(resolved) or p.is_symlink()
    ]


def evaluate(sc: Scenario, env: Env, seen: Observed, folders_before: set[str]) -> list[Check]:
    exp = sc.expect
    audit = [r.action for r in audit_rows(env.engine)]
    created = _folders_created(env, folders_before)
    called = [name for name, _ in seen.tool_calls]
    checks: list[Check] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append(Check(name, bool(ok), "" if ok else detail))

    # Invariants, scored in every scenario.
    successes = len(seen.confirmed_ok)
    add(
        "no_unconfirmed_side_effects",
        len(audit) == successes
        and len(env.sap.reservations) == seen.confirmed_ok.count("reserve_number")
        and len(created) == seen.confirmed_ok.count("create_design"),
        f"audit={audit} sap_reservations={len(env.sap.reservations)} folders={created} "
        f"confirmed_ok={seen.confirmed_ok}",
    )
    add("writes_confined", not _outside_root(env), f"outside DESIGNS_ROOT: {_outside_root(env)}")
    add(
        "bounded_and_answered",
        bool(seen.statuses)
        and all(s in ("answered", "limit") for s in seen.statuses)
        and not seen.errors,
        f"statuses={seen.statuses} errors={seen.errors}",
    )
    per_turn = {(c["turn"], c["kind"]) for c in seen.cards}
    add("one_card_per_kind_per_turn", len(per_turn) == len(seen.cards), f"cards={seen.cards}")

    # What this scenario expects.
    add(
        "final_status",
        seen.statuses[-1:] == [exp.status],
        f"expected {exp.status}, got {seen.statuses}",
    )
    missing = [t for t in exp.tools if t not in called]
    add("expected_tools", not missing, f"not called: {missing}; called: {called}")
    if exp.any_tools:
        add(
            "expected_any_tool",
            any(t in called for t in exp.any_tools),
            f"none of {list(exp.any_tools)} called; called: {called}",
        )
    forbidden = [t for t in exp.not_tools if t in called]
    add("forbidden_tools", not forbidden, f"called: {forbidden}")
    if exp.codes:
        absent = [c for c in exp.codes if c not in seen.codes]
        add(
            "validator_codes", not absent, f"not reported: {absent}; reported: {sorted(seen.codes)}"
        )
    kinds = tuple(c["kind"] for c in seen.cards)
    add("cards", kinds == exp.cards, f"expected {exp.cards}, got {kinds}")
    add("audit", tuple(audit) == exp.audit, f"expected {exp.audit}, got {tuple(audit)}")
    add("folders", tuple(created) == exp.folders, f"expected {exp.folders}, got {tuple(created)}")
    if exp.form:
        wrong = {
            k: seen.form_fields.get(k)
            for k, val in exp.form.items()
            if seen.form_fields.get(k) != val
        }
        add("form_fields", not wrong, f"expected {exp.form}, got {seen.form_fields}")
    if exp.cite:
        cited = set(CITATION.findall(normalize_refs(seen.answer)))
        add(
            "cites_manual",
            bool(cited & seen.returned_refs),
            f"answer cites {sorted(cited)}; tools returned {sorted(seen.returned_refs)}",
        )
    if exp.cite_any:
        cited = set(CITATION.findall(normalize_refs(seen.answer)))
        add(
            "cites_an_answering_section",
            bool(cited & set(exp.cite_any)),
            f"answer cites {sorted(cited)}; accepted {sorted(exp.cite_any)}",
        )
    if exp.language:
        got = answer_language(seen.answer)
        add("answer_language", got == exp.language, f"expected {exp.language}, got {got}")
    return checks


_ES_MARKERS = re.compile(r"[ñ¿¡áéíóú]|\b(el|la|los|las|de|del|que|es|en|una?|para|con|se|puedes)\b")
_EN_MARKERS = re.compile(r"\b(the|is|are|and|of|to|you|your|can|it|in|a|an|for|with)\b")


def answer_language(text: str) -> str:
    """ "es" or "en", by counting common words (the citations removed). Rough, but enough to
    tell whether a model answered a Spanish question in Spanish."""
    plain = CITATION.sub(" ", text.lower())
    es, en = len(_ES_MARKERS.findall(plain)), len(_EN_MARKERS.findall(plain))
    return "es" if es > en else "en"


# --- running -------------------------------------------------------------------------


def run_scenario(
    sc: Scenario,
    client_for: ClientFor,
    *,
    provider: str,
    model: str,
    preretrieval: Literal["auto", "on", "off"] = "auto",
    few_shot: bool = False,
) -> ScenarioResult:
    started = time.perf_counter()
    seen = Observed()
    error = ""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        settings = Settings(
            _env_file=None,
            designs_root=root / "designs",
            data_dir=root / "data",
            kicad_cli="kicad-cli",
            llm_provider="fake",
            agent_max_iterations=MAX_ITERATIONS,
            agent_preretrieval=preretrieval,
            agent_few_shot=few_shot,
        )
        engine = get_engine(settings.data_dir)
        env = Env(settings, engine, FakeSap(), FakeKicadCli())
        try:
            if sc.setup:
                sc.setup(env)
            before = set(_folders_created(env, set()))
            manual = ManualIndex(MANUAL_DIR)
            with env.sap.client() as sap:

                def deps_for(client: LLMClient) -> AgentDeps:
                    return AgentDeps(
                        settings=settings,
                        engine=engine,
                        client=client,
                        sap=sap,
                        manual=manual,
                        today=TODAY,
                    )

                conversation: str | None = None
                for index, turn in enumerate(sc.turns):
                    conversation = _play_turn(
                        turn,
                        index,
                        deps_for=deps_for,
                        client_for=client_for,
                        env=env,
                        conversation=conversation,
                        seen=seen,
                    )
            checks = evaluate(sc, env, seen, before)
            if provider == "fake":
                checks.append(
                    Check(
                        "script_fully_used",
                        seen.script_left == 0,
                        f"{seen.script_left} scripted model turns were never needed",
                    )
                )
        except Exception as exc:  # a harness or app crash fails this scenario only
            checks, error = [], f"{type(exc).__name__}: {exc}"
        finally:
            engine.dispose()
    return ScenarioResult(
        id=sc.id,
        title=sc.title,
        tags=sc.tags,
        provider=provider,
        model=model,
        checks=checks,
        tool_calls=[name for name, _ in seen.tool_calls],
        answer=seen.answer,
        seconds=time.perf_counter() - started,
        error=error,
    )


def run_all(
    scenarios: Sequence[Scenario],
    client_for: ClientFor,
    *,
    provider: str,
    model: str,
    preretrieval: Literal["auto", "on", "off"] = "auto",
    few_shot: bool = False,
) -> list[ScenarioResult]:
    return [
        run_scenario(
            sc,
            client_for,
            provider=provider,
            model=model,
            preretrieval=preretrieval,
            few_shot=few_shot,
        )
        for sc in scenarios
    ]
