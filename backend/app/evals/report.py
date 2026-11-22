"""Eval results as a console table, JSON and a Markdown report for `docs/eval/`."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date

from app.evals.harness import ScenarioResult


def score(results: list[ScenarioResult]) -> tuple[int, int]:
    return sum(r.passed for r in results), len(results)


def console(results: list[ScenarioResult]) -> str:
    lines = []
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        lines.append(f"{mark}  {r.id:<28} {r.seconds:5.1f}s  {r.title}")
        for check in r.failures:
            lines.append(f"      - {check.name}: {check.detail}")
        if r.error:
            lines.append(f"      ! {r.error}")
    passed, total = score(results)
    lines.append(f"\n{passed}/{total} scenarios passed")
    return "\n".join(lines)


def to_json(results: list[ScenarioResult]) -> str:
    passed, total = score(results)
    payload = {
        "date": date.today().isoformat(),
        "provider": results[0].provider if results else "",
        "model": results[0].model if results else "",
        "passed": passed,
        "total": total,
        "scenarios": [r.to_dict() for r in results],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def to_markdown(results: list[ScenarioResult]) -> str:
    passed, total = score(results)
    first = results[0] if results else None
    out = [
        f"# Agent eval: {first.provider if first else '-'} / {first.model if first else '-'}",
        "",
        f"Run on {date.today().isoformat()}. **{passed}/{total}** scenarios passed.",
        "",
    ]
    prompt = sum(r.prompt_tokens for r in results)
    completion = sum(r.completion_tokens for r in results)
    if prompt or completion:
        calls = sum(r.model_calls for r in results)
        out += [
            f"Model calls: {calls}. Tokens: {prompt:,} prompt + {completion:,} completion.",
            "",
        ]
    failing = Counter(c.name for r in results for c in r.failures)
    if failing:
        out += ["Failed checks: " + ", ".join(f"`{n}` ×{k}" for n, k in failing.most_common()), ""]
    out += [
        "| Scenario | Result | Tools called | Time | Tokens |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        tools = ", ".join(r.tool_calls) or "-"
        tokens = f"{r.prompt_tokens + r.completion_tokens:,}" if r.model_calls else "-"
        mark = "✅" if r.passed else "❌"
        out.append(f"| `{r.id}` {r.title} | {mark} | {tools} | {r.seconds:.1f}s | {tokens} |")
    bad = [r for r in results if not r.passed]
    if bad:
        out += ["", "## Failures", ""]
        for r in bad:
            out.append(f"### `{r.id}`")
            for c in r.failures:
                out.append(f"- **{c.name}**: {c.detail}")
            if r.error:
                out.append(f"- **error**: {r.error}")
            if r.answer:
                out.append(f"- answer: {r.answer[:300]!r}")
            out.append("")
    return "\n".join(out) + "\n"
