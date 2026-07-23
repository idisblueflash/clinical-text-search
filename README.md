# clinical-annotation-tools

Tooling for a clinical NLP prototype: **natural-language query → clinical
narratives**. This repo holds the pipeline (CLI-driven, no UI yet), the frozen
evaluation datasets, and per-model annotation runs.

Companion research notebook: `../semantic-annotation-of-clinical-text`
(reading notes, papers, the sampling/schema methodology this tooling follows).

## Layout

```
scripts/            pipeline scripts
  build_dataset.py  clean + stratified-sample MTSamples into a frozen dataset
datasets/           frozen, versioned evaluation datasets (input, committed)
  mtsamples-ner-v1/ 80-note stratified NER sample — see its DATASET_CARD.md
runs/               per-model predictions against a dataset (created when annotating)
  <model>/          predictions.jsonl + run.json, one dir per model
```

## Current status

- **Dataset**: `mtsamples-ner-v1` — 80 clinical narratives, stratified on
  specialty × note-type (CLEF marginal-matching), cleaned (keyword tails
  stripped). Entity schema = CLEF 6 entities + 3 modifiers (`SCHEMA.md`).
- **Baseline**: Claude as the proof-of-concept NER annotator (next step) —
  output saved to `runs/claude-<model>/` in a model-agnostic format so GPT /
  local models can be compared against the same frozen bytes later.

## Rebuild the dataset

```
python3 scripts/build_dataset.py            # deterministic (fixed seed)
python3 scripts/build_dataset.py --report-only   # show marginals, write nothing
```
