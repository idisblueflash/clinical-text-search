# clinical-annotation-tools

Tooling for a clinical NLP prototype whose end goal is **natural-language query →
matching clinical narratives**. This repo holds the upstream, domain-specific
part of that pipeline: a cleaned, frozen NER evaluation dataset and the scripts
that build it, plus per-model annotation runs against it.

The prototype is **CLI-driven — there is no UI yet** (deliberately deferred; see
`devlog.md`). The strategy is to prove the hard part — clean data and comparable
named-entity recognition (NER) — before building an interface.

Companion research repo: `../semantic-annotation-of-clinical-text` — reading
notes, source papers, and the sampling/schema methodology this tooling follows.

## Layout

```
scripts/
  build_dataset.py       clean + stratified-sample MTSamples into a frozen dataset
  openrouter_client.py   reusable primitive: (model, text) -> response (+ cost) via OpenRouter
  annotate.py            run any OpenRouter model as the NER annotator -> runs/<model>/
guideline.md             how to annotate the narratives (humans + LLMs) — the CLEF process
manual/                  human-readable usage docs, one .md per CLI (real commands + output)
specs/                   design intent for CLIs not built yet (e.g. compare.py)
datasets/                frozen, versioned evaluation datasets (committed input)
  mtsamples-ner-v1/      80-note stratified NER sample
    DATASET_CARD.md        source, cleaning, stratification, manifest fields
    SCHEMA.md              entity label set (CLEF 6 entities + 3 modifiers)
    docs/NNNN.txt          cleaned narrative, 1 per note — CHARACTER-OFFSET GROUND TRUTH
    manifest.jsonl         1 row/note: ids, both axes, split, char_len, sha256
    sampling.json          provenance: seed, N, per-axis marginals & achieved counts
runs/                    per-model predictions against a dataset (created when annotating)
  <model>/                 predictions.jsonl + run.json, one dir per model
devlog.md                engineering decision log (the *why* behind each choice)
```

## The dataset: `mtsamples-ner-v1`

80 de-identified clinical narratives sampled from **MTSamples** (4,999 public
transcribed notes), for a clinical NER baseline and cross-model comparison. Full
detail in [`datasets/mtsamples-ner-v1/DATASET_CARD.md`](datasets/mtsamples-ner-v1/DATASET_CARD.md).

- **Frozen bytes are the source of truth.** Every model annotates the exact text
  in `docs/*.txt`, so character offsets — and therefore agreement/F1 between any
  two runs — are mechanical. `manifest.jsonl` SHA-256-pins each note.
- **Cleaned before sampling** (universe 4,922 of 4,999): drop empty/`nan` and
  sub-100-char stubs, and strip the appended `keywords` tail that most MTSamples
  notes glue onto the narrative (metadata that would trivialize NER).
- **Two-axis stratified draw, CLEF marginal-matching** (Roberts et al. 2008): set
  target counts per group first, draw at random, and guard **both** axis counters
  on every draw; rarest cells drawn first to avoid an endgame stall.
  - Axis 1 — **specialty** (given), ≥2% threshold → 12 strata + one "Other".
  - Axis 2 — **note-type** (derived from section headers, `header-rules-v1`), 7
    types, floor 1. *Heuristic label — a sampling axis, not gold.*
  - `split` (train/test) is carried in the manifest but is **not** an axis.
- Deterministic: `N=80`, `seed=20260723`. Re-running reproduces identical bytes.

### Entity schema

The label set is the **CLEF** scheme (Roberts et al. 2008), adopted verbatim so
runs are comparable — full definitions and boundary rules in
[`SCHEMA.md`](datasets/mtsamples-ner-v1/SCHEMA.md).

- **6 entities**: `Condition`, `Intervention`, `Investigation`, `Result`,
  `Drug_or_device`, `Locus`.
- **3 modifiers** (span with a `modifies` pointer): `Negation`, `Laterality`,
  `Sub_location`.
- CLEF **relations** are out of scope for v1 (a separate task → future `mtsamples-re-v1`).

How to actually apply the labels — the annotation process, decision cues, hard
cases, and a fully worked example, for humans and LLMs alike — is
[`guideline.md`](guideline.md).

## Run format

Model predictions live **outside** the dataset dir, one sibling per model with
identical shape, so a later model drops in without touching the frozen input:

```
runs/<model>/predictions.jsonl   {"doc_id","entities":[{i,start,end,text,label,modifies?}]}
runs/<model>/run.json            {model, date, dataset:"mtsamples-ner-v1", schema_ver, prompt_ver}
```

`start`/`end` are half-open character offsets into `docs/<doc_id>.txt`.

## Rebuild the dataset

```
python3 scripts/build_dataset.py               # deterministic (fixed seed)
python3 scripts/build_dataset.py --report-only # print marginals, write nothing
```

The script reads `mtsamples.csv` from the companion repo (path in
`build_dataset.py`); the pipeline is Python stdlib only. Full usage, options, and
example output: [`manual/build_dataset.md`](manual/build_dataset.md).

## Environment

Managed with [`uv`](https://docs.astral.sh/uv/). One runtime dependency —
`openrouter` — for annotation; the data pipeline stays stdlib-only.

```
uv sync                                     # create the venv from uv.lock
uv run python scripts/<script>.py ...       # run anything in the venv
```

## Annotate

Any OpenRouter model can annotate the frozen dataset; runs land in `runs/<model>/`
in the comparable format above. See [`manual/annotate.md`](manual/annotate.md).

```
export OPENROUTER_API_KEY=sk-or-...
uv run python scripts/annotate.py --model anthropic/claude-opus-4 --limit 5   # pilot
```

The low-level `(model, text) → response` primitive is `scripts/openrouter_client.py`
([`manual/openrouter_client.md`](manual/openrouter_client.md)).

Validate a run's offsets against the frozen bytes (`doc[start:end] == text`)
before trusting or comparing it:

```
uv run python scripts/check_offsets.py runs/<model>          # exits non-zero on any mismatch
```

See [`manual/check_offsets.md`](manual/check_offsets.md).

## Status

- **Done**: `mtsamples-ner-v1` built and frozen; sampler reproducible. OpenRouter
  annotation runner + reusable client; annotation `guideline.md`.
- **Next**: the baseline NER run → `runs/<model>/` (5-doc pilot, then 80), then
  **self-consistency** (same model ×3) via `compare.py`.
- **Deferred** (tracked in `devlog.md`): evaluation harness — `compare.py`, specced
  in [`specs/compare.md`](specs/compare.md) (self-consistency / inter-run F1) — a
  gold standard + inter-annotator agreement, relation extraction, the downstream
  query→retrieval stages, and the UI.
