"""Command line: seed, demo, eval, serve, states."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import REPO_ROOT, load_settings


def _demo() -> int:
    from .agent import InquiryAgent
    from .providers import make_provider
    from .seed import seed
    from .store import Store

    settings = load_settings()
    store = Store(":memory:")  # the demo never touches the server database
    seed(store)
    agent = InquiryAgent(store, make_provider(settings), settings)
    print(f"Provider: {agent.provider.name} | prompt {agent.provider.prompt_version} | synthetic data only\n")
    print(f"{'inquiry':9} {'intent':31} {'state':24} {'next step':26} flags")
    last = None
    for org in ("ORG-A", "ORG-B"):
        for inquiry in store.list_inquiries(org):
            out = agent.process(org, inquiry.inquiry_id)
            intent = out.intent.value if out.intent else "-"
            print(f"{inquiry.inquiry_id:9} {intent:31} {out.workflow_state.value:24} {out.next_best_action:26} "
                  f"{', '.join(out.risk_flags) or '-'}")
            if inquiry.inquiry_id == "INQ-002":
                last = out
    if last is not None:
        print("\nExample structured output (INQ-002, contract agent_output.v1):")
        print(json.dumps(last.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def _seed() -> int:
    from .seed import seed
    from .store import Store

    settings = load_settings()
    store = Store(settings.db_path)
    seed(store)
    print(f"Seeded synthetic data into {settings.db_path}")
    return 0


def _serve(host: str, port: int) -> int:
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app(), host=host, port=port)
    return 0


def _states() -> int:
    from .state_machine import to_markdown_table, to_mermaid

    print("```mermaid")
    print(to_mermaid())
    print("```\n")
    print(to_markdown_table())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rental-copilot", description="Munich Rental Copilot (synthetic demo)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="reset the local database with synthetic data")
    sub.add_parser("demo", help="run the agent over all synthetic inquiries and print the results")
    p_eval = sub.add_parser("eval", help="run the evaluation set and write a report")
    p_eval.add_argument("--cases", type=Path, default=REPO_ROOT / "evals" / "cases_v1.json")
    p_eval.add_argument("--out", type=Path, default=REPO_ROOT / "evals" / "reports")
    p_eval.add_argument("--provider", choices=["mock", "anthropic"], default=None,
                        help="override RC_LLM_PROVIDER for this run")
    p_serve = sub.add_parser("serve", help="start the API and the operator console")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("states", help="print the state machine as Mermaid and as a table")
    args = parser.parse_args(argv)

    if args.cmd == "seed":
        return _seed()
    if args.cmd == "demo":
        return _demo()
    if args.cmd == "serve":
        return _serve(args.host, args.port)
    if args.cmd == "states":
        return _states()
    if args.cmd == "eval":
        from .evals import run_cli

        return run_cli(args.cases, args.out, args.provider)
    return 1


if __name__ == "__main__":
    sys.exit(main())
