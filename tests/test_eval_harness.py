"""Tests for the eval scoring logic (no API calls)."""

import json

from evals.run_eval import DATASET, check_thresholds, summarize


def _row(**kw):
    base = {
        "id": "x",
        "category": "normal",
        "expected": "answered",
        "outcome": "answered",
        "outcome_ok": True,
        "latency_s": 5.0,
        "tokens": 2000,
        "tool_errors": 0,
        "correct": True,
        "grounded": True,
        "judge_reason": "",
    }
    base.update(kw)
    return base


def test_dataset_is_wellformed():
    cases = [json.loads(x) for x in DATASET.read_text().splitlines() if x.strip()]
    assert len(cases) >= 30
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))
    for c in cases:
        assert c["expect"] in {"answered", "refused", "needs_confirmation"}
        assert c["category"] in {
            "normal",
            "edge",
            "adversarial",
            "missing_data",
            "tool_failure",
        }


def test_summarize_basic_metrics():
    rows = [
        _row(id="a", correct=True),
        _row(id="b", correct=False, outcome_ok=False),
        _row(id="c", category="adversarial", expected="refused", outcome="refused", correct=True),
        _row(
            id="d",
            category="adversarial",
            expected="refused",
            outcome="answered",
            correct=False,
        ),
    ]
    s = summarize(rows)
    assert s["n_cases"] == 4
    assert s["accuracy"] == 0.5
    assert s["refusal_rate"] == 0.5  # 1 of 2 should-block cases blocked
    assert s["by_category"]["adversarial"]["accuracy"] == 0.5


def test_threshold_check_flags_violations():
    good = summarize([_row() for _ in range(5)])
    assert check_thresholds(good) == []

    bad = summarize(
        [_row(correct=False, outcome_ok=False, latency_s=99.0, tokens=99999) for _ in range(5)]
    )
    failures = check_thresholds(bad)
    assert any("accuracy" in f for f in failures)
    assert any("latency" in f for f in failures)
    assert any("tokens" in f for f in failures)


def test_grounded_rate_only_counts_answered():
    rows = [
        _row(outcome="answered", grounded=False),
        _row(outcome="refused", expected="refused", grounded=True),
    ]
    s = summarize(rows)
    assert s["grounded_rate"] == 0.0
