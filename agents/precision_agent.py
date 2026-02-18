from __future__ import annotations

from typing import Any


def _has_valid_citation(finding: dict[str, Any]) -> bool:
    citation = finding.get("citation")
    if not citation:
        return False
    return all(
        key in citation and citation[key] is not None
        for key in ("node_id", "span_start", "span_end")
    )


def run_precision(findings: list[dict[str, Any]]) -> dict[str, Any]:
    cited_findings = [f for f in findings if _has_valid_citation(f)]

    summary_lines = []
    for finding in cited_findings:
        c = finding["citation"]
        summary_lines.append(
            f"{finding['message']} Citation: Node {c['node_id']}, Span {c['span_start']}–{c['span_end']}"
        )

    if not summary_lines:
        summary_lines = [
            "No citation-backed findings available; no assertion generated."
        ]

    return {
        "mode": "precision",
        "findings": cited_findings,
        "answer": "\n".join(summary_lines),
        "citation_enforced": True,
    }
