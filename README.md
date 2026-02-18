# Contract Analyst Agent (Prototype)

A contracts-native analysis demo built around deterministic data flow:

**Bronze → Silver → Orchestrator Decision → DAG Subtree Walk → Evidence Packet → Answer**

This repo is optimized for local prototyping and presentation of the upstream processing model that will later be integrated into AiDa.

---

## 1) Data Flow (Presentation View)

### Step A — Offline document processing

Input contracts are ingested and structurally prepared:

- **Bronze layer (immutable):** raw source + extracted text + metadata
- **Silver layer (structural spine):** headings, clauses, definitions, classified nodes

Artifacts are persisted on disk for reproducibility.

### Step B — Runtime query orchestration

Given a user query + input document, the orchestrator first runs a **mock retrieval stage** and then performs mock agent decisions (regex-based):

1. **Mock RAG Top-1 retrieval (placeholder simulation):**
  - retrieves one document from local corpus for runtime processing
  - currently regex/token-overlap based
  - explicitly a demo placeholder for future real retriever

2. **Mode routing:** `overview` vs `precision`
3. **Doc type routing:** `nda`, `msa`, `credit_agreement`, `loan_agreement`
4. **Conditional DAG routing:** choose subtree profile
  - `classification_only`
  - `obligation_probe`
  - `playbook_diff`

### Step C — Targeted DAG execution

A template DAG is loaded for the selected doc type and only the selected subtree is executed.

### Step D — Evidence packet assembly

The pipeline emits a structured evidence packet containing:

- citation-bearing findings
- span references (`node_id`, `span_start`, `span_end`)
- obligations
- high-confidence classified nodes
- DAG execution trace metadata

### Step E — Answer stage (prototype)

The precision agent produces citation-enforced outputs from findings.
In production, this evidence packet is intended to be injected into AiDa prompt templates.

---

## 2) What Is Implemented Right Now

### Bronze extraction

File: `tools/bronze_extractor.py`

- Supports `.txt`, `.pdf`, `.docx`
- Persists artifacts to `docs/bronze/<doc>.bronze.json`

### Silver structural processing

Files:

- `tools/spine_builder.py`
- `tools/clause_classifier.py`
- `tools/obligation_extractor.py`
- `tools/playbook_compare.py`

Persists artifacts to:

- `docs/silver/<doc>.<doc_type>.<mode>.silver.json`

### Template DAG execution

File: `tools/dag_runner.py`

- Loads YAML template by doc type
- Executes dependency-aware DAG steps
- Supports runtime subtree override (`requested_steps`)
- Emits deterministic trace

### Mock orchestrator decision logic (regex)

File: `tools/mock_router.py`

- Auto-selects mode/doc type from query + document text
- Selects subtree profile
- Outputs reasons + confidence + selected steps

### Orchestrator + agents

Files:

- `agents/orchestrator.py`
- `agents/overview_agent.py`
- `agents/precision_agent.py`

Orchestrator now supports:

- `--mode auto|overview|precision`
- `--doc-type auto|nda|msa|credit_agreement|loan_agreement`
- `--query "..."`

### End-to-end demo runner

File: `scripts/demo_e2e.py`

Runs pre-written query+doc scenarios and writes final evidence packets to:

- `docs/cache/demo_outputs/*.evidence_packet.json`

---

## 3) Supported Templates and Baselines

### Templates (`templates/`)

- `nda.yml`
- `msa.yml`
- `credit_agreement.yml`
- `loan_agreement.yml`

### Baselines (`precedent_store/`)

- `nda_baseline.json`
- `msa_baseline.json`
- `credit_agreement_baseline.json`
- `loan_agreement_baseline.json`

---

## 4) Runtime Output Contract

Each orchestrator run returns JSON including:

- `document`, `doc_type`, `mode`, `query`
- `orchestrator_decision`
  - keyword scores
  - selected mode/doc type/profile
  - selected DAG steps
  - reasoning
- `dag_execution`
  - template route steps vs selected steps
  - actual executed steps
  - step trace
- `evidence_packet`
- `result` (overview or precision output)
- `artifacts` (Bronze/Silver paths)

---

## 5) Demo Commands (End-to-End)

### A) Auto-routed direct orchestrator runs

```bash
python agents/orchestrator.py --doc docs/cache/sample_nda.txt --mode auto --doc-type auto --query "give me a high level summary"
python agents/orchestrator.py --doc docs/cache/sample_credit_agreement.txt --mode auto --doc-type auto --query "quote events of default and compare to baseline"
```

### B) Scenario runner (query + doc → evidence packet file)

```bash
python scripts/demo_e2e.py --scenario nda_overview
python scripts/demo_e2e.py --scenario credit_precision
```

Presentation/runtime options:

```bash
python scripts/demo_e2e.py --scenario credit_precision --speed 1.2
python scripts/demo_e2e.py --scenario credit_precision --no-sim-delay
python scripts/demo_e2e.py --scenario credit_precision --quiet
```

- `--speed`: latency multiplier for simulated online step timing (`<1` faster, `>1` slower)
- `--no-sim-delay`: keep formatted logs but remove artificial waiting
- `--quiet`: suppress formatted step logs and print only final JSON summary

Generated artifacts:

- `docs/cache/demo_outputs/nda_overview.evidence_packet.json`
- `docs/cache/demo_outputs/credit_precision.evidence_packet.json`

---

## 6) Why This Is Demo-Ready

- Full data flow from query+doc to evidence packet is wired
- Auto orchestration decisions are visible and reproducible
- DAG subtree routing is conditional and inspectable
- Precision path remains citation-first
- Outputs are persisted as concrete artifacts for review

---

## 7) Current Boundaries

- Retriever / top-k multi-document RAG is not implemented in this mock
- Router is regex-based (placeholder for future LLM policy/router agent)
- Extraction/classification are heuristic (good for prototype demos, not production-grade legal QA)

---

## 8) Next Integration Step Toward AiDa

Swap the mock regex router with an LLM orchestrator policy layer while keeping:

- same Bronze/Silver contracts
- same template DAG execution interface
- same evidence packet schema

That preserves the architecture while upgrading decision intelligence.
