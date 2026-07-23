# Dataset: mtsamples-ner-v1

A frozen, stratified 80-note sample of MTSamples clinical narratives, for a
clinical **NER** baseline and cross-model comparison (Claude now; GPT / local
later). The cleaned text in `docs/` is the **source of truth for character
offsets** — every model annotates these exact bytes so runs are comparable.

Regenerate deterministically: `python3 scripts/build_dataset.py` (fixed seed).

## Source

- MTSamples (`data/mtsamples/mtsamples.csv` in the `semantic-annotation-of-clinical-text`
  repo): 4,999 de-identified transcribed clinical notes, public. Columns:
  `id, text, label, split`.
- `label` is an integer code (0–39) for **medical specialty**; decoded to names
  from note content (see `scripts/build_dataset.py::SPECIALTY`).
- **MIMIC-IV is deliberately excluded** (restricted license — never commit).

## Cleaning (applied before sampling)

Sampling universe = 4,922 of 4,999 after:
1. Drop empty texts and `nan` stubs.
2. **Strip the appended keyword tail.** Most MTSamples notes have the original
   `keywords` column glued onto the end of the narrative with no separator
   (a lowercase, comma-separated list). It is metadata, not clinical prose, and
   would inflate/trivialize NER — so it is removed (3,473 notes stripped).
3. Drop notes under 100 characters after stripping (removes keyword-dominated
   stubs left with no real narrative).

## Stratification — two axes, CLEF marginal-matching

Draw method follows Roberts et al. (2008) as distilled in the project notes
`stratified-sampling-balance-two-axes` / `-guard-both-counters`: set a **target
count per group first** (the marginals), then draw at random and **guard both
axis counters on every draw**, rejecting a draw when either of its groups is
full. Rarest cells are considered first to avoid an endgame stall. Fixed seed →
reproducible. Exact targets/achieved counts in `sampling.json`.

- **Axis 1 — specialty** (given). Frequency-thresholded like CLEF's rare-category
  filter (`diagnosis-frequency-filter-five-percent`): specialties with ≥2% share
  are their own stratum (12 of them); the 28 rarer specialties pool into one
  **"Other"** bucket → 13 buckets, none empty.
- **Axis 2 — note-type** (derived). 7 types classified from section headers
  (`note_type_method: header-rules-v1`): Operative/Procedure, Consult/H&P,
  Other/Letter, Diagnostic report, Discharge summary, SOAP/Progress,
  Pathology/Autopsy. Floor of 1 so Pathology/Autopsy (0.5%) is present.
  **`note_type` is a heuristic label, not gold** — treat as a sampling axis
  only, not ground truth.

`split` (train/test) is carried through in the manifest but is **not** a
sampling axis.

## Layout

```
DATASET_CARD.md      this file
SCHEMA.md            entity label set (CLEF 6 entities + 3 modifiers)
docs/NNNN.txt        cleaned narrative, 1 per note — OFFSET GROUND TRUTH
manifest.jsonl       1 row/note: ids, both axes, split, char_len, sha256
sampling.json        provenance: seed, N, per-axis marginals & achieved counts
```

Model predictions live **outside** this dir, one sibling per model, identical
shape, so a later run drops in without touching the dataset:

```
runs/<model>/predictions.jsonl   {"doc_id","entities":[{i,start,end,text,label,modifies?}]}
runs/<model>/run.json            {model, date, dataset:"mtsamples-ner-v1", schema_ver, prompt_ver}
```

## Manifest fields

| field | meaning |
| --- | --- |
| `doc_id` | dataset-local id, `0001`… (matches `docs/<doc_id>.txt`) |
| `source_id` | original `mtsamples.csv` `id` |
| `specialty` / `specialty_code` | decoded specialty name / original code |
| `specialty_bucket` | axis-1 value (specialty name or "Other …") |
| `note_type` / `note_type_method` | axis-2 value (derived) / classifier version |
| `split` | original train/test (carried, not an axis) |
| `char_len` / `orig_char_len` | cleaned length / pre-clean length |
| `keyword_tail_stripped` | whether a keyword tail was removed |
| `text_sha256` | pins the exact cleaned bytes models must annotate |

## Version

`v1` — N=80, seed=20260723, schema=CLEF entities. Bump the version (new dir)
for any change to cleaning, axes, N, or schema; never mutate a frozen dataset
that has runs against it.
