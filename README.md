# Contract Analyst Agent (Prototype)

Deterministic contracts pipeline:

**Bronze → Spine (Silver or Auto) → Dynamic Chunk Retrieval → Router Decision → DAG Steps → Evidence Packet → Answer**

---

## What’s New (Spine + Retrieval)

### 1) Canonical SpineDoc schema

- File: `tools/spine_types.py`
- Defines:
  - `SpineNode`: `node_id`, `kind`, `title`, `text`, `span_start`, `span_end`, `mass`, `meta`
  - `SpineDoc`: `nodes`, `spine_source`, `meta`

### 2) Silver spine loader helpers

- File: `tools/spine_io.py`
- `load_silver_spine(path) -> SpineDoc`
  - Wraps existing Silver JSON (`spine.headings|clauses|definitions`) into `SpineDoc.nodes`
  - Normalizes kinds and masses
- `save_spine(path, spine_doc)`
  - Optional utility for persisted spine artifacts

### 3) Auto spine fallback builder (Bronze text)

- File: `tools/auto_spine_builder.py`
- `build_auto_spine(full_text) -> SpineDoc`
  - Splits blocks by blank lines
  - Heading heuristic regex:
    - `^(SECTION|ARTICLE)\b`
    - `^\d+(\.\d+)*\b`
    - `^[A-Z][A-Z\s]{8,}$`
  - Assigns `kind` = `heading|paragraph`
  - Computes stable `span_start` / `span_end`
  - Computes `mass = 1 + 0.002*num_chars + kind_bonus`

### 4) Spine resolver (Silver preferred, Auto fallback)

- File: `tools/spine_resolver.py`
- `resolve_spine(doc_path, doc_type, mode, bronze_path=None, silver_path=None) -> SpineDoc`
  - If Silver exists at the resolved path, uses `load_silver_spine`
  - Else uses Bronze extracted text and `build_auto_spine`
  - Returns `SpineDoc` with `spine_source = "silver" | "auto"`

### 5) Naive dynamic chunking + ranking

- File: `tools/dynamic_chunker.py`
- `build_chunks(nodes, params) -> ChunkGraph`
  - Neighbor window `W=6`
  - Strength = distance-decayed token overlap
  - Mass-aware merge threshold
- `rank_chunks(chunk_graph, query, k=3) -> List[ChunkHit]`
  - Scores by query token overlap + small mass tie-break
  - Returns chunks with `chunk_id`, `score`, `mass`, `span_start`, `span_end`, `excerpt`

---

## Routing + Retrieval Wiring

### Router shared retrieval helper

- File: `tools/mock_router.py`
- `resolve_dynamic_retrieval(...)`
  - Resolves spine
  - Builds chunk graph
  - Ranks top-k chunks
  - Returns:
    - `spine_source`
    - `retrieval.method = dynamic_chunking_naive_mass_strength`
    - `retrieval.chunks`

### Orchestrator output changes

- File: `agents/orchestrator.py`
- `run_pipeline(...)` now supports hybrid retrieval:
  - if `retrieval_override` is provided, uses it
  - else computes internally via `resolve_dynamic_retrieval(...)`
- Decision JSON includes:
  - `orchestrator_decision.spine_source`
  - `orchestrator_decision.retrieval`
- Evidence packet includes:
  - `evidence_packet.retrieval`
  - each chunk includes `chunk_id`, `score`, `mass`, `span_start`, `span_end`, `excerpt` (plus `node_ids`)

### Precision agent constraint

- File: `agents/precision_agent.py`
- Precision now uses only retrieved chunk excerpts for quote context
- Citations reference chunk IDs and span ranges in answer text

---

## Existing Components

- Bronze extraction: `tools/bronze_extractor.py`
- DAG execution: `tools/dag_runner.py`
- Structural/classification tools:
  - `tools/spine_builder.py`
  - `tools/clause_classifier.py`
  - `tools/obligation_extractor.py`
  - `tools/playbook_compare.py`
- Agents:
  - `agents/orchestrator.py`
  - `agents/overview_agent.py`
  - `agents/precision_agent.py`

Templates in `templates/`; baselines in `precedent_store/`.

---

## Quick Usage

### Orchestrator (auto routing)

```bash
python agents/orchestrator.py --doc docs/cache/sample_nda.txt --mode auto --doc-type auto --query "summarize confidentiality"
```

### Demo runner (delegates retrieval to orchestrator)

```bash
python scripts/demo_e2e.py --scenario nda_overview
python scripts/demo_e2e.py --scenario credit_precision
```

Replay retrieval deterministically from a prior evidence packet:

```bash
python scripts/demo_e2e.py --scenario nda_overview --retrieval-override docs/cache/demo_outputs/nda_overview.evidence_packet.json
```

The demo runner no longer performs its own top-1 retrieval logic; retrieval is sourced from orchestrator runtime (or replay override).

### Expected smoke signals

- `orchestrator_decision.spine_source` should be present (`auto` or `silver`)
- `evidence_packet.retrieval.chunks` should include top chunk hits (`k=3` default)
- Precision answers cite chunk IDs when precision mode is selected

---

## Setup on a New Device

Recommended transfer method is source-only archive plus dependency lockfile.

### 1) Prepare on source machine

```bash
python -m pip freeze > requirements.txt
```

Create an archive that excludes virtual environment, cache, and generated artifacts:

```bash
tar -a -c -f CAA_ultra_lean.zip \
  --exclude=.venv \
  --exclude=.git \
  --exclude=__pycache__ \
  --exclude=docs/cache \
  --exclude=docs/bronze \
  --exclude=docs/silver \
  --exclude=docs/cache/demo_outputs \
  .
```

### 2) Restore on destination machine (Windows PowerShell)

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If script execution is blocked in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 3) Run a quick check

```bash
python scripts/demo_e2e.py --scenario nda_overview
```

---

## Programmatic Examples

### Load Silver spine as SpineDoc

```python
from tools.spine_io import load_silver_spine

spine = load_silver_spine("docs/silver/sample_nda.nda.overview.silver.json")
print(spine.spine_source)          # silver
print(spine.nodes[0].node_id)
```

### Resolve spine with fallback

```python
from tools.spine_resolver import resolve_spine

spine = resolve_spine(
    doc_path="docs/cache/sample_nda.txt",
    doc_type="nda",
    mode="overview",
)
print(spine.spine_source)          # silver or auto
print(len(spine.nodes))
```

---

## Notes

- Retrieval is intentionally minimal/naive for prototype determinism.
- Router policy remains regex-based mock logic.
- This repo is optimized for transparent artifacts and inspectable execution traces.
