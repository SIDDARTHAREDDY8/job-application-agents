"""End-to-end tests with a fake LLM: no API keys, no network, no browser.

Run:  pip install -r requirements-dev.txt && python -m pytest tests/ -q
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm.base import LLMClient, LLMConfig
from src.agents import (
    SourcerAgent, TailorAgent, OutreachAgent, ApplyAgent, Coordinator,
)
from src.boards import get_adapter, list_boards
from src.connectors.gmail import GmailSender
import src.llm.factory as factory

CANDIDATE = {
    "name": "Test User",
    "email": "test@example.com",
    "phone": "+1-555-000-0000",
    "linkedin": "https://linkedin.com/in/test",
    "target_roles": ["AI Engineer"],
    "skills": ["Python"],
    "form_answers": {"work_authorization": "Authorized"},
}

JOBS_REPLY = {
    "jobs": [
        {
            "company": "Acme", "role": "AI Engineer", "location": "Remote",
            "role_type": "full-time", "jd_text": "build robots with python",
            "contact_name": "Jane", "contact_title": "CTO",
            "contact_email": "jane@acme.example", "email_source": "verbatim",
            "source_url": "", "why_hidden": "x post", "fit_note": "fits",
        },
        {
            "company": "Beta", "role": "ML Engineer", "location": "Remote",
            "role_type": "full-time", "jd_text": "ml platform",
            "contact_name": "", "contact_title": "", "contact_email": "",
            "email_source": "", "source_url": "https://boards.greenhouse.io/beta/jobs/1",
            "apply_url": "https://boards.greenhouse.io/beta/jobs/1",
            "board": "greenhouse", "why_hidden": "", "fit_note": "fits",
        },
    ],
    "skipped": [{"company": "Old", "role": "X", "reason": "citizenship"}],
}


class FakeLLM(LLMClient):
    """Routes on the system prompt, like the real agents expect."""

    def chat(self, messages, **kwargs):
        s = messages[0]["content"].lower()
        if "job sourcer" in s:
            return json.dumps(JOBS_REPLY)
        if "resume tailor" in s:
            return json.dumps({"tailored_bullets": [], "skills_line": "Python",
                               "summary_line": "s", "notes": ""})
        if "map an application form" in s:
            return json.dumps({"mappings": []})
        return json.dumps({"subject": "AI Engineer, robotics",
                           "body": "Hi Jane, you build warehouse robots. "
                                   "I shipped a vision pipeline handling 10k picks/day. "
                                   "You get someone who owns perception end to end. "
                                   "Resume attached. Worth a 20-min chat this week? "
                                   "Test 555 linkedin"})


@pytest.fixture
def llm():
    return FakeLLM(LLMConfig(provider="fake", model="fake"))


class FakeGmail:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body, attachments=None, cc=None):
        self.sent.append({"to": to, "subject": subject,
                          "attachments": attachments})
        return {"message_id": "fake-123", "mode": "smtp"}


# ------------------------------------------------------------------ llm factory
def test_factory_lists_providers():
    providers = factory.list_providers()
    for p in ("openai", "anthropic", "gemini", "ollama", "custom"):
        assert p in providers


def test_factory_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        factory.create(provider="nope")


# ------------------------------------------------------------------ gmail
def test_gmail_rejects_bad_recipient():
    g = GmailSender(mode="smtp", address="a@b.com", app_password="x")
    with pytest.raises(ValueError, match="bad recipient"):
        g.send(to="not-an-email", subject="s", body="b")


def test_gmail_bad_mode_raises():
    with pytest.raises(ValueError, match="smtp.*api"):
        GmailSender(mode="carrier-pigeon")


# ------------------------------------------------------------------ boards
def test_registry_routes_all_boards():
    cases = {
        "https://boards.greenhouse.io/acme/jobs/1": "greenhouse",
        "https://job-boards.greenhouse.io/acme/jobs/1": "greenhouse",
        "https://jobs.lever.co/acme/abc": "lever",
        "https://jobs.ashbyhq.com/acme/abc": "ashby",
        "https://acme.workable.com/j/abc": "workable",
        "https://www.linkedin.com/jobs/view/1": "linkedin",
        "https://www.indeed.com/viewjob?jk=1": "indeed",
        "https://www.dice.com/job-detail/1": "dice",
        "https://www.ziprecruiter.com/jobs/1": "ziprecruiter",
        "https://www.glassdoor.com/job/1": "glassdoor",
    }
    for url, name in cases.items():
        adapter = get_adapter(url)
        assert adapter is not None and adapter.name == name, url
    assert get_adapter("https://example.com/whatever") is None
    assert get_adapter("") is None
    assert set(list_boards()) == set(cases.values())


# ------------------------------------------------------------------ agents
def test_sourcer_extract_and_dedupe(llm):
    out = SourcerAgent(llm, CANDIDATE).extract("some raw text")
    assert len(out["jobs"]) == 2
    assert len(out["skipped"]) == 1
    seen = set()
    fresh = SourcerAgent.dedupe(out["jobs"], seen)
    assert len(fresh) == 2
    # second pass: same jobs are dropped
    assert SourcerAgent.dedupe(out["jobs"], seen) == []


def test_tailor_returns_json(llm):
    out = TailorAgent(llm, CANDIDATE).tailor("jd text here")
    assert "skills_line" in out


def test_outreach_draft_shape(llm):
    out = OutreachAgent(llm, CANDIDATE).draft(JOBS_REPLY["jobs"][0], None)
    assert out["subject"] and out["body"]
    assert "—" not in out["body"]  # no em-dashes per style rules


def test_outreach_tolerates_malformed_llm_json():
    class BrokenLLM(LLMClient):
        def chat(self, messages, **kwargs):
            return '{"nope": 1}'  # valid JSON, missing keys

    out = OutreachAgent(BrokenLLM(LLMConfig(provider="x", model="x")),
                        CANDIDATE).draft(JOBS_REPLY["jobs"][0])
    assert out["subject"] == "" and out["body"] == ""


# ------------------------------------------------------------------ apply routing
def _stub_board(monkeypatch, result):
    adapter = get_adapter("https://boards.greenhouse.io/beta/jobs/1")
    monkeypatch.setattr(
        adapter, "apply",
        lambda driver, job, cand, resume, llm: result,
    )
    return adapter


def test_apply_email_route_live(llm):
    gmail = FakeGmail()
    agent = ApplyAgent(llm, CANDIDATE, gmail=gmail)
    job = JOBS_REPLY["jobs"][0]
    out = agent.apply(job, None, resume_path="resume.pdf", dry_run=False)
    assert out["route"] == "email" and out["applied"] and out["status"] == "applied"
    assert gmail.sent[0]["to"] == "jane@acme.example"
    assert gmail.sent[0]["attachments"] == ["resume.pdf"]


def test_apply_email_route_blocked_without_gmail(llm):
    agent = ApplyAgent(llm, CANDIDATE, gmail=None)
    out = agent.apply(JOBS_REPLY["jobs"][0], None, dry_run=False)
    assert out["applied"] is False and out["status"] == "blocked"


def test_apply_board_route_live(llm, monkeypatch):
    _stub_board(monkeypatch, {"applied": True, "confirmation": "application received",
                              "note": "ok"})
    agent = ApplyAgent(llm, CANDIDATE, driver=object())
    out = agent.apply(JOBS_REPLY["jobs"][1], None, dry_run=False)
    assert out["route"] == "board" and out["applied"]
    assert out["confirmation"] == "application received"


def test_apply_board_route_unconfirmed(llm, monkeypatch):
    _stub_board(monkeypatch, {"applied": False, "confirmation": "",
                              "note": "submitted but no confirmation marker"})
    agent = ApplyAgent(llm, CANDIDATE, driver=object())
    out = agent.apply(JOBS_REPLY["jobs"][1], None, dry_run=False)
    assert out["applied"] is False and out["status"] == "failed"


def test_apply_board_route_blocked_without_driver(llm):
    agent = ApplyAgent(llm, CANDIDATE, driver=None)
    out = agent.apply(JOBS_REPLY["jobs"][1], None, dry_run=False)
    assert out["applied"] is False and out["status"] == "blocked"


def test_apply_dry_run_writes_nothing(llm, tmp_path):
    state = str(tmp_path / "apps.json")
    coord = Coordinator(llm, CANDIDATE, state_path=state,
                        driver=object(), gmail=FakeGmail())
    out = coord.run([{"text": "x", "source_url": ""}], dry_run=True)
    assert out["applied"] == 0 and out["dry_run"] is True
    assert all(r["status"] == "drafted" for r in out["results"])
    assert not os.path.exists(state)


def test_coordinator_live_then_dedupe(llm, tmp_path, monkeypatch):
    _stub_board(monkeypatch, {"applied": True, "confirmation": "application received",
                              "note": "ok"})
    state = str(tmp_path / "apps.json")
    gmail = FakeGmail()
    coord = Coordinator(llm, CANDIDATE, state_path=state,
                        driver=object(), gmail=gmail)

    out = coord.run([{"text": "x", "source_url": ""}], dry_run=False,
                    resume_path="resume.pdf")
    assert out["applied"] == 2
    assert os.path.exists(state)
    saved = json.load(open(state))
    assert len(saved) == 2

    # second run: both already seen -> nothing fresh
    out2 = coord.run([{"text": "x", "source_url": ""}], dry_run=False,
                     resume_path="resume.pdf")
    assert out2["fresh"] == 0 and out2["applied"] == 0
    assert len(json.load(open(state))) == 2  # unchanged
