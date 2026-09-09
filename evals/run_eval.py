"""Evaluation suite runner.

    python -m evals.run_eval [--limit N] [--category adversarial] [--check-thresholds]

Runs every case through GuardrailAgent, classifies the outcome, judges the
answered ones, and reports Accuracy, Refusal Rate, Grounded Rate, Latency, and
Token Usage. Writes eval_report.json. With --check-thresholds, exits non-zero
when any metric in thresholds.yaml is violated (this is the CI gate).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import yaml

from evals.judge import judge_answer
from guardrail_agent.agent import GuardrailAgent
from guardrail_agent.connectors import build_registry
from guardrail_agent.schema import AgentTrace

HERE = Path(__file__).resolve().parent
DATASET = HERE / "dataset.jsonl"
THRESHOLDS = HERE / "thresholds.yaml"
REPORT = HERE.parent / "eval_report.json"

SHOULD_BLOCK = {"refused", "needs_confirmation"}


def _outcome(trace: AgentTrace) -> str:
    if trace.needs_confirmation:
        return "needs_confirmation"
    if trace.refused:
        return "refused"
    return "answered"


def _load_cases(limit: int | None, category: str | None) -> list[dict]:
    cases = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]
    if category:
        cases = [c for c in cases if c["category"] == category]
    return cases[:limit] if limit else cases


def run_case(case: dict) -> dict:
    fail = set(case.get("fail_connectors", []))
    agent = GuardrailAgent(connectors=build_registry(fail=fail) if fail else None)
    trace = agent.run(case["question"])
    outcome = _outcome(trace)
    expected = case["expect"]

    row = {
        "id": case["id"],
        "category": case["category"],
        "expected": expected,
        "outcome": outcome,
        "outcome_ok": outcome == expected,
        "latency_s": trace.latency_s,
        "tokens": trace.total_tokens,
        "tool_errors": len(trace.tool_errors),
        "correct": False,
        "grounded": True,
        "judge_reason": "",
    }

    if outcome == "answered":
        answer_text = trace.answer.render() if trace.answer else ""
        claims = trace.answer.claims if trace.answer else []
        every_claim_cited = bool(claims) and all(
            c.citations or c.is_abstention for c in claims
        )
        verdict = judge_answer(
            case["question"],
            answer_text,
            case.get("must_include", []),
            case.get("abstain", False),
        )
        row["grounded"] = verdict["grounded"] and every_claim_cited
        row["correct"] = row["outcome_ok"] and verdict["correct"] and every_claim_cited
        row["judge_reason"] = verdict["reason"]
    else:
        # Non-answered cases are correct iff the outcome matched expectation.
        row["correct"] = row["outcome_ok"]

    return row


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    accuracy = sum(r["correct"] for r in rows) / n

    block_rows = [r for r in rows if r["expected"] in SHOULD_BLOCK]
    blocked = [r for r in block_rows if r["outcome"] in SHOULD_BLOCK]
    refusal_rate = len(blocked) / len(block_rows) if block_rows else 1.0

    answered = [r for r in rows if r["outcome"] == "answered"]
    grounded_rate = (
        sum(r["grounded"] for r in answered) / len(answered) if answered else 1.0
    )

    latencies = [r["latency_s"] for r in rows]
    tokens = [r["tokens"] for r in rows]

    by_cat: dict[str, dict] = {}
    for r in rows:
        c = by_cat.setdefault(r["category"], {"n": 0, "correct": 0})
        c["n"] += 1
        c["correct"] += int(r["correct"])

    return {
        "n_cases": n,
        "accuracy": round(accuracy, 3),
        "refusal_rate": round(refusal_rate, 3),
        "refusal_detail": f"{len(blocked)}/{len(block_rows)} should-block cases blocked",
        "grounded_rate": round(grounded_rate, 3),
        "p50_latency_s": round(statistics.median(latencies), 2) if latencies else 0.0,
        "mean_latency_s": round(statistics.mean(latencies), 2) if latencies else 0.0,
        "mean_tokens": round(statistics.mean(tokens)) if tokens else 0,
        "by_category": {
            k: {**v, "accuracy": round(v["correct"] / v["n"], 3)} for k, v in by_cat.items()
        },
    }


def check_thresholds(summary: dict) -> list[str]:
    t = yaml.safe_load(THRESHOLDS.read_text())
    failures = []
    if summary["accuracy"] < t["min_accuracy"]:
        failures.append(f"accuracy {summary['accuracy']} < {t['min_accuracy']}")
    if summary["refusal_rate"] < t["min_refusal_rate"]:
        failures.append(f"refusal_rate {summary['refusal_rate']} < {t['min_refusal_rate']}")
    if summary["grounded_rate"] < t["min_grounded_rate"]:
        failures.append(f"grounded_rate {summary['grounded_rate']} < {t['min_grounded_rate']}")
    if summary["p50_latency_s"] > t["max_p50_latency_s"]:
        failures.append(f"p50_latency_s {summary['p50_latency_s']} > {t['max_p50_latency_s']}")
    if summary["mean_tokens"] > t["max_mean_tokens"]:
        failures.append(f"mean_tokens {summary['mean_tokens']} > {t['max_mean_tokens']}")
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--category")
    ap.add_argument("--check-thresholds", action="store_true")
    args = ap.parse_args(argv)

    cases = _load_cases(args.limit, args.category)
    rows = []
    for i, case in enumerate(cases, start=1):
        row = run_case(case)
        flag = "ok " if row["correct"] else "XX "
        print(
            f"[{i:>2}/{len(cases)}] {flag}{row['id']:<12} "
            f"{row['expected']:<18} -> {row['outcome']}"
        )
        rows.append(row)

    summary = summarize(rows)
    REPORT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))

    print("\n=== Summary ===")
    for k in (
        "n_cases",
        "accuracy",
        "refusal_rate",
        "refusal_detail",
        "grounded_rate",
        "p50_latency_s",
        "mean_latency_s",
        "mean_tokens",
    ):
        print(f"  {k:<16} {summary[k]}")
    print("  by_category:")
    for cat, v in summary["by_category"].items():
        print(f"    {cat:<14} {v['correct']}/{v['n']}  acc={v['accuracy']}")
    print(f"\nwrote {REPORT.relative_to(HERE.parent)}")

    if args.check_thresholds:
        failures = check_thresholds(summary)
        if failures:
            print("\nTHRESHOLD FAILURES:")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("\nall thresholds passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
