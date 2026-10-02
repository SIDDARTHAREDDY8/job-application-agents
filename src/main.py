"""CLI: run the job-application agents with any LLM, on any computer.

Setup:
    pip install -r requirements.txt
    playwright install chromium        # only if you use --apply on boards
    cp .env.example .env               # then edit .env (LLM provider, Gmail, ...)
    cp config/candidate.example.yaml config/candidate.yaml   # your details

Examples:
    # Draft only (safe): source -> tailor -> draft outreach, writes nothing
    python -m src.main --input examples/sample_signal.txt --dry-run

    # Actually apply: email route sends via Gmail, board route drives Playwright
    python -m src.main --input examples/sample_signal.txt --max-jobs 5 --resume resume.pdf

    # Search a board directly (needs login session for most boards)
    python -m src.main --search-board linkedin --query "AI Engineer" --location "Remote" --headed
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


def build_llm():
    from src.llm import from_env
    llm = from_env()
    print(f"LLM: provider={llm.config.provider} model={llm.model_name}")
    return llm


def cmd_run(args, candidate, llm):
    from src.agents import Coordinator

    gmail = driver = None
    if not args.dry_run:
        if os.getenv("GMAIL_ADDRESS"):
            from src.connectors.gmail import from_env as gmail_from_env
            gmail = gmail_from_env()
            print(f"Gmail: mode={gmail.mode} address={gmail.address}")
        if args.board_apply or args.search_board:
            from src.browser import PlaywrightManager
            driver = PlaywrightManager(headless=not args.headed)
            driver.start()
            print(f"Browser: {'headed' if args.headed else 'headless'} "
                  f"(profile: {driver.profile_dir})")

    try:
        coord = Coordinator(llm, candidate, state_path=args.state,
                            driver=driver, gmail=gmail)
        with open(args.input) as f:
            raw = f.read()
        out = coord.run(
            [{"text": raw, "source_url": args.source_url}],
            max_jobs=args.max_jobs,
            dry_run=args.dry_run,
            resume_path=args.resume,
        )
    finally:
        if driver:
            driver.close()

    print(f"Sourced: {out['sourced']} | fresh: {out['fresh']} | "
          f"applied: {out['applied']} | dry_run={out['dry_run']}")
    for r in out["results"]:
        print("=" * 60)
        print(f"{r['role']} @ {r['company']}  [{r.get('route')}] -> {r.get('status')}")
        if r.get("subject"):
            print(f"Subject: {r['subject']}")
        if r.get("note"):
            print(f"Note: {r['note']}")
    if out["skipped"]:
        print(f"\nSkipped: {len(out['skipped'])}")


def cmd_search_board(args, candidate, llm):
    from src.browser import PlaywrightManager
    from src.boards import get_adapter, list_boards

    adapter = get_adapter(args.search_board)
    if adapter is None:
        print(f"Unknown board '{args.search_board}'. Available: {list_boards()}")
        sys.exit(1)
    login = getattr(adapter, "LOGIN_URL", "")
    with PlaywrightManager(headless=not args.headed) as driver:
        if login and args.headed:
            print(f"If not logged in, log in at {login} in the opened browser, "
                  f"then press Enter here.")
            input()
        jobs = adapter.search_jobs(driver, args.query, args.location or "")
    print(f"Found {len(jobs)} jobs on {adapter.name}:")
    for j in jobs:
        print(f"- {j['role']} @ {j['company']}  {j['source_url']}")


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Job-application agents (any LLM, any computer).")
    ap.add_argument("--input", default="examples/sample_signal.txt",
                    help="Text file with raw hiring signals")
    ap.add_argument("--source-url", default="")
    ap.add_argument("--candidate", default="config/candidate.yaml")
    ap.add_argument("--max-jobs", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true",
                    help="Draft only; send nothing, submit nothing, write no state.")
    ap.add_argument("--resume", default=None, help="Path to resume PDF to attach/upload")
    ap.add_argument("--state", default="state/applications.json")
    ap.add_argument("--headed", action="store_true",
                    help="Show the browser (use once to log in to boards)")
    ap.add_argument("--board-apply", action="store_true",
                    help="Enable the Playwright board route (starts a browser on real applies)")
    ap.add_argument("--search-board", default=None,
                    help="Search a board directly: linkedin|indeed|dice|ziprecruiter|glassdoor")
    ap.add_argument("--query", default="AI Engineer")
    ap.add_argument("--location", default="Remote")
    args = ap.parse_args()

    llm = build_llm()
    candidate = load_candidate(args.candidate)

    if args.search_board:
        cmd_search_board(args, candidate, llm)
    else:
        if not args.dry_run and not args.resume:
            print("Note: no --resume given; email sends will go without attachment "
                  "and board uploads will be skipped.")
        cmd_run(args, candidate, llm)


if __name__ == "__main__":
    main()
