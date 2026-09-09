"""Command-line entry point: ``guardrail ask "..."``."""

from __future__ import annotations

import argparse
import sys

from guardrail_agent.agent import GuardrailAgent
from guardrail_agent.schema import AgentTrace


def _print_trace(trace: AgentTrace) -> None:
    print(f"Q: {trace.question}\n")

    if trace.decomposition:
        print("Sub-questions:")
        for s in trace.decomposition.subquestions:
            hint = f"  ->{s.connectors}" if s.connectors else ""
            print(f"  - {s.question}{hint}")
        print()

    if trace.tool_errors:
        print("Tool errors:")
        for e in trace.tool_errors:
            print(f"  ! {e}")
        print()

    print("Answer:")
    print(trace.final_text() or "(empty)")

    if trace.answer and trace.answer.evidence:
        print("\nSources:")
        for i, e in enumerate(trace.answer.evidence, start=1):
            print(f"  [{i}] ({e.source}) {e.title} {e.url}".rstrip())

    print(
        f"\nlatency={trace.latency_s}s  tokens={trace.total_tokens} "
        f"(in={trace.input_tokens} out={trace.output_tokens})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="guardrail")
    sub = parser.add_subparsers(dest="command", required=True)
    ask = sub.add_parser("ask", help="ask the agent a question")
    ask.add_argument("question")

    args = parser.parse_args(argv)
    if args.command == "ask":
        trace = GuardrailAgent().run(args.question)
        _print_trace(trace)
        return 1 if trace.refused else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
