"""CLI test: runs `python -m src.main --dry-run` with a fake LLM (no keys, no network)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.main as main_mod
from src.llm.base import LLMClient, LLMConfig


class FakeLLM(LLMClient):
    def chat(self, messages, **kwargs):
        s = messages[0]["content"].lower()
        if "job sourcer" in s:
            return json.dumps({"jobs": [{
                "company": "Acme", "role": "AI Engineer", "location": "Remote",
                "role_type": "full-time", "jd_text": "build things",
                "contact_name": "Jane", "contact_title": "CTO",
                "contact_email": "jane@acme.example", "email_source": "v",
                "source_url": "", "why_hidden": "", "fit_note": ""}],
                "skipped": []})
        if "resume tailor" in s:
            return json.dumps({"tailored_bullets": [], "skills_line": "",
                               "summary_line": "", "notes": ""})
        return json.dumps({"subject": "AI Engineer", "body": "Hello"})


def test_cli_dry_run(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("src.llm.from_env",
                        lambda: FakeLLM(LLMConfig(provider="fake", model="fake")))
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    state = str(tmp_path / "apps.json")
    monkeypatch.setattr(sys, "argv", [
        "src.main",
        "--input", os.path.join(repo, "examples", "sample_signal.txt"),
        "--candidate", os.path.join(repo, "config", "candidate.example.yaml"),
        "--state", state,
        "--dry-run",
    ])
    main_mod.main()
    out = capsys.readouterr().out
    assert "dry_run=True" in out
    assert "Acme" in out
    assert not os.path.exists(state)


def test_cli_resolves_relative_paths(monkeypatch, tmp_path):
    # run from a different CWD: relative paths must still resolve to the repo
    monkeypatch.chdir(tmp_path)
    assert main_mod._resolve("examples/sample_signal.txt").startswith(
        os.path.dirname(os.path.dirname(os.path.abspath(main_mod.__file__))))
    assert main_mod._resolve("/abs/path") == "/abs/path"
