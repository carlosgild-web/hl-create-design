"""Command line: `python -m app.cli create-design|chat|confirm|cancel ...`.

- `create-design`: the generator without the assistant (developer tool, offline).
- `chat "message"`: one turn with the assistant on LLM_PROVIDER; prints the tool calls
  and the confirmation cards it opens.
- `confirm <action_id>`: the user's click on a card (the same code as
  `POST /api/actions/{id}/confirm`); `cancel <action_id>` dismisses it.

Exit codes: 0 done, 1 refused by a rule, SAP, the file system or the model,
2 bad arguments, 3 kicad-cli made no PDF (the project was kept without it; decision 0023).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import urlparse

from app.actions import ActionNotFound, ActionNotPending, cancel_action, confirm_action
from app.agent.service import AgentDeps, chat_turn, probe_turn
from app.core.config import MANUAL_DIR, Settings, get_settings
from app.db.session import get_engine
from app.designs import DesignValidationError, create_design
from app.kicad.renderer import DesignFolderExistsError
from app.llm.base import LLMClient, LLMError, Message
from app.llm.factory import make_client
from app.llm.ollama import OllamaProbe, find_ollama, start_ollama
from app.llm.resolve import ProviderStatus, check_ollama, check_providers
from app.sap.client import SapClient
from app.standards.manual_search import ManualIndex
from app.standards.validators import DesignRequest, Issue, UnsafePathError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser(
        "create-design", help="Create a KiCad project from the company template"
    )
    create.add_argument("--dept", required=True, help="Department code: HW, PWR, EMB or TFX")
    create.add_argument("--number", required=True, help="Design number, e.g. HL-HW-26-0042")
    create.add_argument("--rev", required=True, help="Revision letter, e.g. A")
    create.add_argument("--name", required=True, help="Design name, e.g. 'Bead Drill Controller'")
    create.add_argument(
        "--designer", required=True, help="Initial and surname, e.g. 'C. Velazquez'"
    )
    create.add_argument("--material", default="", help="SAP material number (offline use)")
    create.add_argument("--project", default="", help="WBS element, e.g. P-26-0108 (offline use)")
    create.add_argument("--date", default="", help="Issue date YYYY-MM-DD (default: today)")
    create.add_argument(
        "--description", default="", help="Optional one line under the title (max 60)"
    )
    create.add_argument(
        "--no-export", action="store_true", help="Skip the kicad-cli PDF/SVG export"
    )

    chat = commands.add_parser("chat", help="Send one message to the assistant (LLM_PROVIDER)")
    chat.add_argument("message", help="What you would type in the chat")
    chat.add_argument("--conversation", default=None, help="Continue this conversation id")
    chat.add_argument("--lang", choices=("en", "es"), default="en", help="Answer language")
    chat.add_argument(
        "--form", action="append", default=[], metavar="FIELD=VALUE", help="Current form value"
    )
    chat.add_argument("--trace", action="store_true", help="Print tool results too")

    confirm = commands.add_parser(
        "confirm", help="Confirm a pending action, like clicking Confirm on its card"
    )
    confirm.add_argument("action_id")
    confirm.add_argument("--no-export", action="store_true", help="Skip the PDF/SVG export")

    cancel = commands.add_parser("cancel", help="Cancel a pending action")
    cancel.add_argument("action_id")

    clean = commands.add_parser("cleanup", help="Delete generated designs older than N hours")
    clean.add_argument(
        "--older-than", type=float, default=None, metavar="HOURS", help="default: DESIGNS_TTL_HOURS"
    )

    check = commands.add_parser(
        "llm-check",
        help="Check Groq and Ollama, suggest a model, ask which to use, and print it",
    )
    check.add_argument("--out", type=Path, metavar="FILE", help="Also write the choice here")

    ev = commands.add_parser("agent-eval", help="Run the agent scenario suite (PLAN Phase 6)")
    which = ev.add_mutually_exclusive_group(required=True)
    which.add_argument("--fake", action="store_true", help="Scripted model (CI, no LLM needed)")
    which.add_argument("--provider", choices=("ollama", "groq"), help="Real provider")
    ev.add_argument("--only", action="append", default=[], metavar="ID", help="Run these scenarios")
    ev.add_argument("--json", type=Path, metavar="FILE", help="Write the results as JSON")
    ev.add_argument("--markdown", type=Path, metavar="FILE", help="Write a Markdown report")
    ev.add_argument(
        "--allow-failures", action="store_true", help="Exit 0 even if scenarios fail (real runs)"
    )
    ev.add_argument(
        "--preretrieval",
        choices=("auto", "on", "off"),
        default="auto",
        help="The backend's own manual search before the first model call (decision 0024)",
    )
    return parser


# --- llm-check: which model answers (run by start.cmd / start.sh) --------------------

# ask(question, yes_letter) -> True/False, or None when there is no terminal to ask on
Ask = Callable[[str, str], "bool | None"]
OLLAMA_START_WAIT_S = 30


def _say(text: str = "") -> None:
    print(text, file=sys.stderr, flush=True)


def ask_terminal(
    question: str,
    yes_letter: str,
    *,
    reader: Callable[[], str] = input,
    interactive: Callable[[], bool] = lambda: sys.stdin.isatty(),
) -> bool | None:
    """Ask the person at the terminal and wait for their answer: there is no time limit,
    nothing is chosen until they press Enter. Enter alone takes the suggestion (the capital
    letter). None when there is no terminal at all (CI, Docker)."""
    if not interactive():
        return None
    sys.stderr.write(question)
    sys.stderr.flush()
    try:
        answer = reader()
    except EOFError:  # e.g. `start.cmd < nul`: Windows reports NUL as a terminal
        sys.stderr.write("\n")
        return None
    answer = answer.strip().lower()
    return answer == "" or answer.startswith(yes_letter)


def _is_local(url: str) -> bool:
    return urlparse(url).hostname in ("localhost", "127.0.0.1", "::1")


def start_and_wait(
    settings: Settings,
    *,
    find: Callable[[], Path | None] = find_ollama,
    start: Callable[[Path], None] = start_ollama,
    check: Callable[[Settings], OllamaProbe] = check_ollama,
    sleep: Callable[[float], None] = time.sleep,
    wait_s: int = OLLAMA_START_WAIT_S,
) -> OllamaProbe:
    """Start `ollama serve` and wait until it answers (at most `wait_s` seconds)."""
    executable = find()
    if executable is None:
        return OllamaProbe("not_installed", "not installed")
    _say("  Starting Ollama ...")
    try:
        start(executable)
    except OSError as exc:
        return OllamaProbe("not_running", f"could not be started ({exc})")
    for _ in range(wait_s):
        probe = check(settings)
        if probe.state != "not_running":
            return probe
        sleep(1)
    return OllamaProbe("not_running", f"did not answer within {wait_s} s of starting")


def choose_provider(
    status: ProviderStatus,
    settings: Settings,
    ask: Ask,
    start: Callable[[Settings], OllamaProbe],
) -> str:
    """Suggest the best provider and let the person pick. Without a terminal (`ask` returns
    None) the suggestion is taken, and Ollama is never started."""
    groq, ollama = status.groq, status.ollama
    if groq and groq.usable and ask("Use Groq? [Y/n] ", "y") is not False:
        return "groq"
    if ollama is None:
        return "fake"
    if ollama.state == "not_running" and _is_local(settings.ollama_base_url):
        if ask("Ollama is installed but not running. Start it now? [Y/n] ", "y"):
            ollama = start(settings)
            _say(f"  Ollama    {ollama.detail}")
            if ollama.usable:
                return "ollama"
        return "fake"
    if ollama.usable:
        question = (
            "Use [O]llama (local, slower, needs ~3.5 GB free RAM) or the [D]emo model? [O/d] "
        )
        return "ollama" if ask(question, "o") is not False else "fake"
    return "fake"


def run_llm_check(
    settings: Settings,
    out: Path | None = None,
    *,
    check: Callable[[Settings], ProviderStatus] | None = None,
    ask: Ask = ask_terminal,
    start: Callable[[Settings], OllamaProbe] = start_and_wait,
) -> int:
    """Show each provider's status, suggest one and ask (when there is a terminal). The
    questions and status go to stderr; the chosen name goes to stdout and to `out`, so the
    start scripts can run the app with `LLM_PROVIDER=<name>`."""
    configured = settings.llm_provider
    if configured == "fake":
        _say("Assistant: the scripted demo model (LLM_PROVIDER=fake).")
        provider = "fake"
    else:
        _say("Checking the assistant's model ...")
        status = (check or (lambda s: check_providers(s, turn=probe_turn())))(settings)
        if status.groq:
            _say(f"  Groq      {status.groq.detail}")
        if status.ollama:
            _say(f"  Ollama    {status.ollama.detail}")
        provider = choose_provider(status, settings, ask, start)
        names = {
            "groq": f"Groq ({settings.groq_model})",
            "ollama": f"Ollama ({settings.ollama_model})",
            "fake": "the demo model (scripted, no real AI)",
        }
        _say(f"Using {names[provider]}.")
    if out:
        out.write_text(provider, encoding="utf-8")
    print(provider)
    return 0


def _issue_line(kind: str, issue: Issue) -> str:
    return f"{kind} [{issue.field}] {issue.message} (manual: {issue.ref})"


def run_create_design(args: argparse.Namespace, settings: Settings) -> int:
    request = DesignRequest(
        department=args.dept,
        design_number=args.number,
        revision=args.rev,
        name=args.name,
        designer=args.designer,
        sap_material=args.material,
        project=args.project,
        issue_date=args.date,
        description=args.description,
    )
    try:
        created = create_design(request, settings=settings, export=not args.no_export)
    except DesignValidationError as exc:
        for issue in exc.report.errors:
            print(_issue_line("error", issue), file=sys.stderr)
        return 1
    except UnsafePathError as exc:
        print(_issue_line("error", exc.issue), file=sys.stderr)
        return 1
    except DesignFolderExistsError as exc:
        print(f"error {exc} (manual: 04-folder-structure#revision-folders)", file=sys.stderr)
        return 1
    req = created.request
    print(f"Created {req.design_number} rev {req.revision}: {req.name}")
    print(f"  folder:    {created.project.folder}")
    print(f"  project:   {created.project.project_file.name}")
    print(f"  schematic: {created.project.schematic_file.name}")
    if created.export:
        print(f"  pdf:       {created.export.pdf}")
    for warning in created.warnings:
        print(_issue_line("warning", warning))
    print(f"  audit id:  {created.audit_id}")
    if any(w.code == "pdf_not_exported" for w in created.warnings):
        print("No PDF: fix KICAD_CLI, or use --no-export.", file=sys.stderr)
        return 3
    return 0


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    settings = settings or get_settings()
    if args.command == "create-design":
        return run_create_design(args, settings)
    if args.command == "chat":
        return run_chat(args, settings)
    if args.command == "confirm":
        return run_confirm(args, settings)
    if args.command == "cancel":
        return run_cancel(args, settings)
    if args.command == "cleanup":
        return run_cleanup(args, settings)
    if args.command == "llm-check":
        return run_llm_check(settings, args.out)
    if args.command == "agent-eval":
        return run_agent_eval(args, settings)
    return 2  # pragma: no cover - argparse rejects unknown commands


# --- assistant -----------------------------------------------------------------------


def _sap(settings: Settings) -> SapClient:
    return SapClient(
        settings.sap_base_url, settings.sap_user, settings.sap_password.get_secret_value()
    )


def _short(data: object, limit: int = 300) -> str:
    text = json.dumps(data, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"


def run_chat(
    args: argparse.Namespace,
    settings: Settings,
    client: LLMClient | None = None,
    sap: SapClient | None = None,
) -> int:
    form = dict(item.split("=", 1) for item in args.form if "=" in item)
    try:
        client = client or make_client(settings)
    except LLMError as exc:
        print(f"error {exc}", file=sys.stderr)
        return 1
    sap = sap or _sap(settings)
    deps = AgentDeps(
        settings=settings,
        engine=get_engine(settings.data_dir),
        client=client,
        sap=sap,
        manual=ManualIndex(MANUAL_DIR),
    )
    status = "error"
    with sap:
        for event in chat_turn(
            deps,
            text=args.message,
            conversation_id=args.conversation,
            form=form,
            language=args.lang,
        ):
            d = event.data
            if event.type == "conversation":
                print(f"conversation {d['id']}  ({client.provider}: {client.model})")
            elif event.type == "tool_call":
                print(f"  → {d['name']} {_short(d['arguments'], 200)}")
            elif event.type == "tool_result" and args.trace:
                print(f"    ← {_short(d['result'])}")
            elif event.type == "form_proposal":
                print(f"  [form] {_short(d['fields'])}")
            elif event.type == "pending_action":
                action = d["action"]
                print(f"  [card] {action['kind']} {_short(action['payload'])}")
                print(f"         confirm: python -m app.cli confirm {action['id']}")
            elif event.type == "message":
                print(f"\n{d['content']}\n")
            elif event.type == "notice":
                print(f"  [notice] now on {d['to']} ({d['model']}): {d['reason']}")
            elif event.type == "error":
                print(f"error {d['message']}", file=sys.stderr)
            elif event.type == "done":
                status = d["status"]
                print(
                    f"run {d['run_id']} {status}; "
                    f"continue with --conversation {d['conversation_id']}"
                )
    return 0 if status in ("answered", "limit") else 1


def run_confirm(args: argparse.Namespace, settings: Settings, sap: SapClient | None = None) -> int:
    engine = get_engine(settings.data_dir)
    try:
        with sap or _sap(settings) as client:
            outcome = confirm_action(
                args.action_id,
                settings=settings,
                engine=engine,
                sap=client,
                export=not args.no_export,
            )
    except ActionNotFound:
        print(f"error no action {args.action_id}", file=sys.stderr)
        return 1
    except ActionNotPending as exc:
        print(f"error action {args.action_id} is {exc.reason}", file=sys.stderr)
        return 1
    result = outcome.action.result
    print(f"{outcome.action.kind}: {outcome.action.status}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if outcome.ok else 1


def run_cancel(args: argparse.Namespace, settings: Settings) -> int:
    try:
        action = cancel_action(args.action_id, engine=get_engine(settings.data_dir))
    except (ActionNotFound, ActionNotPending) as exc:
        print(f"error {exc}", file=sys.stderr)
        return 1
    print(f"{action.kind}: {action.status}")
    return 0


def run_cleanup(args: argparse.Namespace, settings: Settings) -> int:
    from app.cleanup import cleanup_designs

    hours = args.older_than if args.older_than is not None else settings.designs_ttl_hours
    if hours <= 0:
        print("error give --older-than HOURS or set DESIGNS_TTL_HOURS", file=sys.stderr)
        return 2
    removed = cleanup_designs(
        settings.designs_root, get_engine(settings.data_dir), older_than_hours=hours
    )
    for item in removed:
        print(f"removed {item.department}/{item.design_number}/{item.revision}")
    print(f"{len(removed)} revision folder(s) removed")
    return 0


def run_agent_eval(args: argparse.Namespace, settings: Settings) -> int:
    from app.evals import harness, report
    from app.evals.scenarios import SCENARIOS

    scenarios = [s for s in SCENARIOS if not args.only or s.id in args.only]
    unknown = set(args.only) - {s.id for s in SCENARIOS}
    if unknown:
        print(f"error unknown scenario(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    if args.fake:
        client_for, provider, model = harness.scripted(), "fake", "scripted"
    else:
        scenarios = [s for s in scenarios if "fake-only" not in s.tags]
        try:
            client = make_client(
                settings.model_copy(update={"llm_provider": args.provider}), fallback=False
            )
        except LLMError as exc:
            print(f"error {exc}", file=sys.stderr)
            return 1
        try:  # fail fast on a wrong model name or a stopped server, not 27 times
            client.chat([Message("user", "Reply with the word ok.")], [])
        except LLMError as exc:
            print(f"error the model is not reachable: {exc}", file=sys.stderr)
            return 1
        client_for, provider, model = harness.real(client), client.provider, client.model
        print(f"{provider}: {model}; {len(scenarios)} scenarios (fake-only ones skipped)")
    results = harness.run_all(
        scenarios, client_for, provider=provider, model=model, preretrieval=args.preretrieval
    )
    print(report.console(results))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(report.to_json(results), encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(report.to_markdown(results), encoding="utf-8")
    passed, total = report.score(results)
    return 0 if passed == total or args.allow_failures else 1


if __name__ == "__main__":
    sys.exit(main())
