"""Render an eval report JSON into a single self-contained HTML page.

    python -m evals.report_html [report.json] [-o out.html]

Defaults to evals/baseline_report.json -> eval_report.html. Used by CI to publish
a viewable dashboard as a build artifact.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_IN = HERE / "baseline_report.json"
DEFAULT_OUT = HERE.parent / "eval_report.html"

_CSS = """
:root{--bg:#0f1117;--panel:#161b22;--line:#2a313c;--txt:#e6edf3;--muted:#8b949e;
--brand:#2dd4bf;--pass:#22c55e;--block:#ef4444;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;padding:32px;max-width:960px;margin:auto}
h1{font-size:1.4rem;margin:0 0 4px}.sub{color:var(--muted);font-family:ui-monospace,monospace;
font-size:.82rem;margin-bottom:24px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:28px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.tile b{display:block;font-size:1.7rem;font-family:ui-monospace,monospace}
.tile span{color:var(--muted);font-size:.8rem}
h2{font-size:.85rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
margin:24px 0 10px}
.bar{display:flex;align-items:center;gap:10px;margin:6px 0;font-family:ui-monospace,monospace;font-size:.82rem}
.bar .name{width:110px;color:var(--muted)}
.bar .track{flex:1;background:#0c0f14;border:1px solid var(--line);border-radius:6px;height:16px;overflow:hidden}
.bar .fill{height:100%;background:var(--brand)}
table{width:100%;border-collapse:collapse;font-size:.83rem;font-family:ui-monospace,monospace}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:500}
.ok{color:var(--pass)}.bad{color:var(--block)}
td.reason{color:var(--muted);max-width:340px;white-space:normal}
"""


def _tile(value: str, label: str) -> str:
    return f'<div class="tile"><b>{html.escape(value)}</b><span>{html.escape(label)}</span></div>'


def _bar(name: str, frac: float, extra: str) -> str:
    pct = max(0, min(100, round(frac * 100)))
    return (
        f'<div class="bar"><span class="name">{html.escape(name)}</span>'
        f'<span class="track"><span class="fill" style="width:{pct}%"></span></span>'
        f"<span>{extra}</span></div>"
    )


def build(report: dict) -> str:
    s = report["summary"]
    rows = report.get("rows", [])

    tiles = "".join(
        [
            _tile(f"{s['accuracy'] * 100:.0f}%", "accuracy"),
            _tile(s["refusal_detail"].split(" ")[0], "should-block cases blocked"),
            _tile(f"{s['grounded_rate'] * 100:.0f}%", "grounded rate"),
            _tile(f"{s['p50_latency_s']}s", "p50 latency"),
            _tile(f"{s['mean_tokens']:,}", "mean tokens / case"),
            _tile(str(s["n_cases"]), "cases"),
        ]
    )

    bars = "".join(
        _bar(cat, v["accuracy"], f"{v['correct']}/{v['n']}")
        for cat, v in s.get("by_category", {}).items()
    )

    tr = []
    for r in rows:
        cls = "ok" if r["correct"] else "bad"
        mark = "pass" if r["correct"] else "FAIL"
        tr.append(
            f'<tr><td>{html.escape(r["id"])}</td><td>{html.escape(r["category"])}</td>'
            f'<td>{html.escape(r["expected"])}</td><td>{html.escape(r["outcome"])}</td>'
            f'<td class="{cls}">{mark}</td>'
            f'<td class="reason">{html.escape(r.get("judge_reason", ""))}</td></tr>'
        )
    table = (
        "<table><tr><th>id</th><th>category</th><th>expected</th><th>outcome</th>"
        "<th>result</th><th>note</th></tr>" + "".join(tr) + "</table>"
        if tr
        else "<p class='sub'>No per-case rows in this report.</p>"
    )

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>guardrail-agent eval report</title><style>{_CSS}</style></head><body>
<h1>guardrail-agent &mdash; evaluation report</h1>
<div class="sub">{s['n_cases']} cases &middot; agent + guard/judge models &middot; generated from report JSON</div>
<div class="tiles">{tiles}</div>
<h2>accuracy by category</h2>{bars}
<h2>cases</h2>{table}
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report", nargs="?", default=str(DEFAULT_IN))
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    report = json.loads(Path(args.report).read_text())
    Path(args.out).write_text(build(report))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
