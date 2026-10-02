"""CLI: run the job-application agents with any LLM.

Usage:
    pip install -r requirements.txt
    cp .env.example .env            # then edit .env
    cp config/candidate.example.yaml config/candidate.yaml   # then edit it

    # Dry run on your collected hiring signals:
    python -m src.main --input examples/sample_signal.txt --dry-run

    # Real run (saves drafts to state/applications.json):
    python -m src.main --input examples/sample_signal.txt --max-jobs 5
"""
from __future__ import annotations
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import yaml


def load_candidate(path: str) -> dict:
    if not os.path.exists(path):
        print(f"Candidate file not found: {path}")
        print("Copy config/candidate.example.yaml -> config/candidate.yaml and fill it in.")
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Job-application agents (any LLM).")
    ap.add_argument("--input", required=True, help="Text file with raw hiring signals (posting text, HN/X excerpts, ...)")
    ap.add_argument("--source-url", default="", help="Where the input text came from")
    ap.add_argument("--candidate", default="config/candidate.yaml")
    ap.add_argument("--max-jobs", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true", help="Draft only; do not write state.")
    ap.add_argument("--state", default="state/applications.json")
    args = ap.parse_args()

    from src.llm import from_env
    from src.agents import Coordinator

    llm = from_env()
    print(f"LLM: provider={llm.config.provider} model={llm.model_name}")

    candidate = load_candidate(args.candidate)
    with open(args.input) as f:
        raw = f.read()

    coord = Coordinator(llm, candidate, state_path=args.state)
    out = coord.run(
        [{"text": raw, "source_url": args.source_url}],
        max_jobs=args.max_jobs,
        dry_run=args.dry_run,
    )
    print(f"Sourced: {out['sourced']} | fresh: {out['fresh']} | dry_run={out['dry_run']}")
    for r in out["results"]:
        print("=" * 60)
        print(f"{r['role']} @ {r['company']}  ({r.get('contact_email') or 'no email'})")
        print(f"Subject: {r['subject']}")
        print(r["body"][:600])
    if out["skipped"]:
        print(f"\nSkipped: {len(out['skipped'])}")


if __name__ == "__main__":
    main()
