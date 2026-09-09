from evals.report_html import build

REPORT = {
    "summary": {
        "n_cases": 2,
        "accuracy": 0.5,
        "refusal_rate": 1.0,
        "refusal_detail": "1/1 should-block cases blocked",
        "grounded_rate": 1.0,
        "p50_latency_s": 3.2,
        "mean_tokens": 1500,
        "by_category": {"normal": {"n": 1, "correct": 1, "accuracy": 1.0},
                        "adversarial": {"n": 1, "correct": 0, "accuracy": 0.0}},
    },
    "rows": [
        {"id": "n1", "category": "normal", "expected": "answered", "outcome": "answered",
         "correct": True, "judge_reason": "ok"},
        {"id": "a1", "category": "adversarial", "expected": "refused", "outcome": "answered",
         "correct": False, "judge_reason": "leaked forbidden text ['OWNED']"},
    ],
}


def test_build_produces_html_with_key_numbers():
    out = build(REPORT)
    assert out.startswith("<!doctype html>")
    assert "50%" in out and "1/1" in out and "1,500" in out
    assert "n1" in out and "a1" in out
    assert "FAIL" in out and "leaked forbidden text" in out


def test_build_handles_no_rows():
    r = {**REPORT, "rows": []}
    out = build(r)
    assert "No per-case rows" in out
