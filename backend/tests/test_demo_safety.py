"""Cloud demo safety: rate limit per IP, daily token cap, DESIGNS_ROOT cleanup."""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from app import cli
from app.api import deps
from app.cleanup import cleanup_designs
from app.core import limits
from app.core.limits import RateLimiter, client_ip
from app.db import store
from app.db.session import audit_rows
from app.llm.fake import FakeClient, say
from app.main import app
from tests.test_scripted_conversation import chat, of


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


# --- rate limiter ---------------------------------------------------------------------


def test_limiter_allows_the_limit_then_says_when_to_retry():
    clock = Clock()
    limiter = RateLimiter(3, clock=clock)
    assert [limiter.hit("a") for _ in range(3)] == [None, None, None]
    wait = limiter.hit("a")
    assert wait is not None and 1 <= wait <= 61
    assert limiter.hit("b") is None  # another IP has its own budget
    clock.now = 61
    assert limiter.hit("a") is None


def test_limiter_forgets_idle_ips():
    clock = Clock()
    limiter = RateLimiter(1, clock=clock)
    for i in range(limits.MAX_KEYS + 5):
        limiter.hit(f"ip{i}")
    clock.now = 120
    limiter.hit("fresh")
    assert len(limiter._hits) < 10


def test_client_ip_trusts_the_proxy_header_only_when_told_to():
    assert client_ip("1.1.1.1", "9.9.9.9, 2.2.2.2", trust_forwarded=False) == "1.1.1.1"
    assert client_ip("1.1.1.1", "9.9.9.9, 2.2.2.2", trust_forwarded=True) == "2.2.2.2"
    assert client_ip(None, None, trust_forwarded=True) == "unknown"


@pytest.fixture
def api(settings, fake_sap):
    holder = {"settings": settings}
    app.dependency_overrides[deps.settings_dep] = lambda: holder["settings"]
    app.dependency_overrides[deps.sap_factory_dep] = lambda: fake_sap.client
    app.dependency_overrides[deps.llm_factory_dep] = lambda: lambda: FakeClient([say("hi")] * 20)
    limits.get_limiter.cache_clear()
    client = TestClient(app)
    client.holder = holder
    yield client
    app.dependency_overrides.clear()
    limits.get_limiter.cache_clear()


def test_chat_is_rate_limited_per_ip(api, settings):
    api.holder["settings"] = settings.model_copy(update={"rate_limit_per_min": 2})
    assert api.post("/api/chat", json={"message": "a"}).status_code == 200
    assert api.post("/api/chat", json={"message": "b"}).status_code == 200
    blocked = api.post("/api/chat", json={"message": "c"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1
    # Reads are not limited.
    assert api.get("/api/departments").status_code in (200, 502)
    # A different client address has its own budget (proxy header trusted).
    api.holder["settings"] = settings.model_copy(
        update={"rate_limit_per_min": 2, "trust_forwarded_for": True}
    )
    other = api.post("/api/chat", json={"message": "d"}, headers={"x-forwarded-for": "7.7.7.7"})
    assert other.status_code == 200


def test_confirm_and_cancel_share_the_limit(api, settings):
    api.holder["settings"] = settings.model_copy(update={"rate_limit_per_min": 1})
    assert api.post("/api/actions/x/cancel").status_code == 404  # counted
    assert api.post("/api/actions/x/confirm").status_code == 429


def test_limit_off_by_default(api):
    assert all(api.post("/api/chat", json={"message": "a"}).status_code == 200 for _ in range(5))


# --- daily token cap ------------------------------------------------------------------


def test_tokens_are_counted_per_day(engine):
    store.add_tokens(engine, 120)
    store.add_tokens(engine, 30)
    store.add_tokens(engine, 0)
    store.add_tokens(engine, 500, day="2020-01-01")
    assert store.tokens_today(engine) == 150
    assert store.tokens_today(engine, day="2020-01-01") == 500


def test_a_run_adds_its_tokens_and_the_cap_pauses_the_assistant(api, settings, engine):
    from app.llm.base import ChatTurn

    api.holder["settings"] = settings.model_copy(update={"daily_token_cap": 100})
    app.dependency_overrides[deps.llm_factory_dep] = lambda: (
        lambda: FakeClient([ChatTurn(content="hi", prompt_tokens=80, completion_tokens=30)] * 3)
    )
    first = chat(api, "hello")
    assert of(first, "message")[0]["content"] == "hi"
    assert store.tokens_today(engine) == 110

    second = chat(api, "again")
    assert of(second, "error")[0]["code"] == "daily_cap"
    assert of(second, "message") == []  # the model was not called
    assert store.tokens_today(engine) == 110


def test_cap_off_by_default(api, engine):
    from app.llm.base import ChatTurn

    app.dependency_overrides[deps.llm_factory_dep] = lambda: (
        lambda: FakeClient([ChatTurn(content="hi", prompt_tokens=10**6)] * 3)
    )
    assert of(chat(api, "a"), "message") and of(chat(api, "b"), "message")


# --- cleanup --------------------------------------------------------------------------


def make_revision(root, dept, number, rev, age_hours):
    folder = root / dept / number / rev
    folder.mkdir(parents=True)
    (folder / f"{number}_{rev}.kicad_sch").write_text("x", encoding="utf-8")
    old = time.time() - age_hours * 3600
    for path in (folder / f"{number}_{rev}.kicad_sch", folder):
        os.utime(path, (old, old))
    return folder


def test_cleanup_removes_only_old_revisions_and_audits_them(settings, engine):
    root = settings.designs_root
    old = make_revision(root, "HW", "HL-HW-26-0050", "A", age_hours=30)
    fresh = make_revision(root, "HW", "HL-HW-26-0050", "B", age_hours=1)
    gone = make_revision(root, "PWR", "HL-PWR-26-0007", "A", age_hours=48)

    removed = cleanup_designs(root, engine, older_than_hours=24)

    assert {(r.design_number, r.revision) for r in removed} == {
        ("HL-HW-26-0050", "A"),
        ("HL-PWR-26-0007", "A"),
    }
    assert not old.exists() and fresh.exists()
    assert not gone.parent.exists() and not gone.parent.parent.exists()  # empty parents go too
    assert [(r.action, r.actor) for r in audit_rows(engine)] == [("design_cleaned", "cleanup")] * 2


def test_cleanup_off_and_missing_root_do_nothing(settings, engine):
    assert cleanup_designs(settings.designs_root, engine, older_than_hours=24) == []
    make_revision(settings.designs_root, "HW", "HL-HW-26-0050", "A", age_hours=999)
    assert cleanup_designs(settings.designs_root, engine, older_than_hours=0) == []
    assert (settings.designs_root / "HW").exists()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
def test_cleanup_never_follows_a_symlink_out_of_the_root(settings, engine, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep", encoding="utf-8")
    design = settings.designs_root / "HW" / "HL-HW-26-0050"
    design.mkdir(parents=True)
    try:
        (design / "A").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks need privileges on this machine")

    assert cleanup_designs(settings.designs_root, engine, older_than_hours=0.0001) == []
    assert (outside / "precious.txt").read_text(encoding="utf-8") == "keep"


def test_cli_cleanup(settings, engine, capsys):
    make_revision(settings.designs_root, "HW", "HL-HW-26-0050", "A", age_hours=30)
    assert cli.main(["cleanup"], settings) == 2  # no TTL configured, none given
    assert cli.main(["cleanup", "--older-than", "24"], settings) == 0
    out = capsys.readouterr().out
    assert "removed HW/HL-HW-26-0050/A" in out and "1 revision folder(s) removed" in out


def test_lifespan_runs_the_cleanup_job_only_when_configured(settings, monkeypatch):
    started = []
    monkeypatch.setattr("app.main._cleanup_loop", lambda: started.append(1) or _noop())
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    with TestClient(app):
        assert started == []
    monkeypatch.setattr(
        "app.main.get_settings", lambda: settings.model_copy(update={"designs_ttl_hours": 1})
    )
    with TestClient(app):
        assert started == [1]


async def _noop():
    return None
