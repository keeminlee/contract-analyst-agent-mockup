from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.orchestrator import run_pipeline
from tools.bronze_extractor import extract_bronze
from tools.dag_runner import load_template
from tools.mock_router import choose_subtree_steps, decide_mock_flow


SCENARIOS: dict[str, dict[str, str]] = {
    "nda_overview": {
        "doc": "docs/cache/sample_nda.txt",
        "query": "Give me a high-level summary and classify the major clauses.",
    },
    "credit_precision": {
        "doc": "docs/cache/sample_credit_agreement.txt",
        "query": "Quote events of default and compare against baseline risk requirements.",
    },
}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(title: str, detail: str) -> None:
    print(f"[{_now()}] {title}")
    print(f"         {detail}")


def _wait(seconds: float, enabled: bool) -> None:
    if enabled and seconds > 0:
        time.sleep(seconds)


def _step_delay(step_id: str, speed: float) -> float:
    base = {
        "detect_headings": 0.20,
        "detect_numbered_clauses": 0.25,
        "extract_definitions": 0.22,
        "clause_classifier": 0.30,
        "obligation_extractor": 0.45,
        "playbook_compare": 0.65,
    }.get(step_id, 0.20)
    return max(0.05, base * max(0.1, speed))


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def _mock_rag_top1(query: str, preferred_doc: Path | None = None) -> dict[str, Any]:
    corpus_dir = ROOT / "docs" / "cache"
    candidates = sorted(path for path in corpus_dir.glob("*.txt") if path.is_file())
    if not candidates:
        raise FileNotFoundError("No .txt documents found in docs/cache for mock RAG retrieval")

    query_tokens = _tokenize(query)
    finance_tokens = {
        "credit",
        "loan",
        "borrower",
        "lender",
        "default",
        "covenant",
        "collateral",
        "interest",
        "principal",
    }
    nda_tokens = {"nda", "confidential", "confidentiality", "disclosure"}

    ranking: list[dict[str, Any]] = []
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="ignore")
        tokens = _tokenize(text)
        overlap = len(query_tokens & tokens)
        score = float(overlap)

        if query_tokens & finance_tokens and ("credit" in path.name.lower() or "loan" in path.name.lower()):
            score += 2.0
        if query_tokens & nda_tokens and "nda" in path.name.lower():
            score += 2.0
        if preferred_doc and path.resolve() == preferred_doc.resolve():
            score += 0.5

        ranking.append({"doc": path, "score": round(score, 3), "overlap": overlap})

    ranking.sort(key=lambda item: item["score"], reverse=True)
    top = ranking[0]
    return {
        "strategy": "mock_top1_regex_overlap",
        "placeholder": True,
        "corpus_size": len(candidates),
        "top_k": 1,
        "top_1": {
            "doc": str(top["doc"]),
            "score": top["score"],
            "token_overlap": top["overlap"],
        },
        "ranked": [
            {
                "doc": str(item["doc"]),
                "score": item["score"],
                "token_overlap": item["overlap"],
            }
            for item in ranking
        ],
    }


def _print_decision_summary(
    decision: dict[str, Any],
    rag_result: dict[str, Any],
    selected_steps: list[str],
) -> None:
    rows = [
        ("Retrieved Doc (Top-1)", Path(rag_result["top_1"]["doc"]).name),
        ("Mode", str(decision.get("mode", ""))),
        ("Doc Type", str(decision.get("doc_type", ""))),
        ("Subtree Profile", str(decision.get("subtree_profile", ""))),
        ("Confidence", str(decision.get("confidence", ""))),
        ("Selected Steps", " -> ".join(selected_steps) if selected_steps else "(none)"),
    ]
    key_width = max(len(key) for key, _ in rows)
    print("         +" + "-" * (key_width + 2) + "+" + "-" * 72 + "+")
    for key, value in rows:
        clipped_value = value[:72]
        print(f"         | {key.ljust(key_width)} | {clipped_value.ljust(72)}|")
    print("         +" + "-" * (key_width + 2) + "+" + "-" * 72 + "+")


def run_scenario(
    name: str,
    persist: bool = True,
    verbose_flow: bool = True,
    simulate_latency: bool = True,
    speed_multiplier: float = 1.0,
) -> dict[str, Any]:
    if name not in SCENARIOS:
        valid = ", ".join(sorted(SCENARIOS.keys()))
        raise ValueError(f"Unknown scenario '{name}'. Valid scenarios: {valid}")

    scenario = SCENARIOS[name]
    requested_doc_path = ROOT / scenario["doc"]
    query = scenario["query"]

    if verbose_flow:
        print("\n=== CONTRACT ANALYST AGENT • ONLINE FLOW DEMO ===")
        _log("1) Query Intake", f"Scenario='{name}' | RequestedDoc='{scenario['doc']}'")
        _log("   User Query", query)
        _wait(0.25 * speed_multiplier, simulate_latency)

        _log(
            "2) Mock RAG Retrieval (Placeholder)",
            "Simulation only: selecting Top-1 document from local corpus for runtime",
        )

    rag_result = _mock_rag_top1(query=query, preferred_doc=requested_doc_path)
    retrieved_doc_path = Path(rag_result["top_1"]["doc"])

    if verbose_flow:
        _wait(0.35 * speed_multiplier, simulate_latency)
        _log(
            "   RAG Top-1",
            (
                f"doc={retrieved_doc_path.name} | score={rag_result['top_1']['score']} | "
                f"token_overlap={rag_result['top_1']['token_overlap']} | corpus={rag_result['corpus_size']}"
            ),
        )
        _log("3) Load Retrieved Bronze Context", "Reading extracted text of retrieved Top-1 document")

    bronze = extract_bronze(retrieved_doc_path)
    document_text = bronze["extracted_text"]

    if verbose_flow:
        _wait(0.35 * speed_multiplier, simulate_latency)
        _log(
            "4) Orchestrator Decision (Mock Router)",
            "Choosing mode, doc type, and DAG subtree profile via regex policy",
        )

    decision = decide_mock_flow(
        query=query,
        document_text=document_text,
        requested_mode="auto",
        requested_doc_type="auto",
    )
    template = load_template(ROOT / "templates" / f"{decision['doc_type']}.yml")
    available_steps = [node["id"] for node in template.get("nodes", [])]
    selected_steps = choose_subtree_steps(
        profile=decision["subtree_profile"],
        available_step_ids=available_steps,
        mode=decision["mode"],
    )

    if verbose_flow:
        _wait(0.35 * speed_multiplier, simulate_latency)
        _log(
            "   Routing Output",
            f"mode={decision['mode']} | doc_type={decision['doc_type']} | profile={decision['subtree_profile']} | confidence={decision['confidence']}",
        )
        _log("   Decision Summary", "Compact runtime routing table")
        _print_decision_summary(decision, rag_result, selected_steps)

        _log("5) Conditional DAG Plan", "Selected online execution steps:")
        print(f"         {' -> '.join(selected_steps) if selected_steps else '(none)'}")

        for idx, step_id in enumerate(selected_steps, start=1):
            _wait(_step_delay(step_id, speed_multiplier), simulate_latency)
            _log(f"   5.{idx} Executing Step", f"{step_id}")

        _wait(0.30 * speed_multiplier, simulate_latency)
        _log("6) Build Evidence Packet", "Collecting citations, findings, obligations, and trace metadata")

    output = run_pipeline(
        doc_path=retrieved_doc_path,
        mode="auto",
        doc_type="auto",
        persist=persist,
        query=query,
    )

    evidence_packet = output.get("evidence_packet", {})
    evidence_payload = {
        "scenario": name,
        "query": scenario["query"],
        "requested_doc": scenario["doc"],
        "retrieved_doc": str(retrieved_doc_path),
        "retrieval": rag_result,
        "doc_type": output.get("doc_type"),
        "mode": output.get("mode"),
        "orchestrator_decision": output.get("orchestrator_decision", {}),
        "dag_execution": output.get("dag_execution", {}),
        "evidence_packet": evidence_packet,
    }

    out_path = ROOT / "docs" / "cache" / "demo_outputs" / f"{name}.evidence_packet.json"
    _write_json(out_path, evidence_payload)

    if verbose_flow:
        _wait(0.25 * speed_multiplier, simulate_latency)
        _log(
            "7) Runtime Complete",
            (
                f"doc_type={output.get('doc_type')} | mode={output.get('mode')} | "
                f"citations={len(evidence_packet.get('citations', []))} | output={out_path}"
            ),
        )
        print("=== END ONLINE FLOW DEMO ===\n")

    return {
        "scenario": name,
        "output_path": str(out_path),
        "retrieved_doc": str(retrieved_doc_path),
        "doc_type": output.get("doc_type"),
        "mode": output.get("mode"),
        "citations": len(evidence_packet.get("citations", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run demo E2E flow from query+doc to Evidence Packet")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS.keys()), default="credit_precision")
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="Suppress formatted online-flow logging")
    parser.add_argument("--no-sim-delay", action="store_true", help="Disable artificial delay between online flow steps")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Latency multiplier for simulated runtime (e.g., 0.7 faster, 1.4 slower)",
    )
    args = parser.parse_args()

    result = run_scenario(
        args.scenario,
        persist=not args.no_persist,
        verbose_flow=not args.quiet,
        simulate_latency=not args.no_sim_delay,
        speed_multiplier=args.speed,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
