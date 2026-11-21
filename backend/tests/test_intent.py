"""The question detector that decides the backend's own manual search (decision 0024)."""

import json

import pytest

from app.agent.intent import classify
from app.core.config import REPO_ROOT
from app.evals.scenarios import SCENARIOS

BANK = json.loads(
    (REPO_ROOT / "backend" / "app" / "evals" / "faq_questions.json").read_text(encoding="utf-8")
)


def test_recall_on_the_faq_bank_is_at_least_95_percent():
    texts = [t for e in BANK for t in (e["question"], *e["paraphrases"])]
    found = sum(classify(t) == "rule_question" for t in texts)
    assert found / len(texts) >= 0.95, f"{found}/{len(texts)}"


def test_no_form_fill_of_the_eval_scenarios_is_taken_for_a_question():
    questions = {"loop-is-bounded", "manual-question", "departments-list"}
    questions |= {s.id for s in SCENARIOS if "preretrieval" in s.tags}
    fills = [t.text for s in SCENARIOS if s.id not in questions for t in s.turns]
    flagged = [t for t in fills if classify(t) == "rule_question"]
    assert flagged == []


@pytest.mark.parametrize(
    "text",
    [
        "Can I choose my own design number?",
        "¿Por qué se rechazó la revisión I?",
        "como le hago para sacar otra revision",
        "Open in KiCad didn't work.",
        "No hay PDF ni vista previa.",
        "my design is blocked in SAP",
        "the number belongs to another department, why",
    ],
)
def test_questions_and_problem_reports(text):
    assert classify(text) == "rule_question"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Create HL-HW-26-0042 revision C, Bead Drill Controller, designer C. Velazquez.",
        "Crea la revisión C de HL-HW-26-0042, Bead Drill Controller.",
        # a question that names a number AND a revision: the model validates it
        "¿Por qué no puedo usar la revisión I en HL-HW-26-0042?",
        "New controller board for the drilling machine, Hardware.",
        "No, use HW.",
        "Ya, crea la revisión.",
        "Not that one, the kiln board.",
    ],
)
def test_form_fills_and_replies_are_not_questions(text):
    assert classify(text) == "other"
