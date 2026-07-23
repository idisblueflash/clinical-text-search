# Dataset: mtsamples-ner-v1

A frozen, stratified 80-note sample of MTSamples clinical notes, for a clinical
**NER** baseline and for comparing models (Claude now; GPT / local later). The
cleaned text in `docs/` is the **source of truth for character offsets** — every
model annotates these exact bytes, so runs are comparable.

Rebuild it the same way every time: `python3 scripts/build_dataset.py` (fixed seed).

## Source

- MTSamples (`data/mtsamples/mtsamples.csv` in the `semantic-annotation-of-clinical-text`
  repo): 4,999 de-identified transcribed clinical notes, public. Columns:
  `id, text, label, split`.
- `label` is an integer code (0–39) for **medical specialty**; we decode it to a
  name from the note content (see `scripts/build_dataset.py::SPECIALTY`).
- **MIMIC-IV is left out on purpose** (restricted license — never commit).

## Cleaning (done before sampling)

Sampling pool = 4,922 of 4,999 after:

1. Drop empty texts and `nan` stubs.
2. **Strip the keyword tail.** Most MTSamples notes have the original `keywords`
   column glued onto the end of the note with no separator (a lowercase,
   comma-separated list). It is metadata, not prose, and would make NER too easy
   and inflate the scores — so it is removed (3,473 notes stripped).
3. Drop notes under 100 characters after stripping (this removes keyword-heavy
   notes that have almost no real text left).

## Stratification — two axes, CLEF marginal-matching

The draw follows Roberts et al. (2008), as distilled in the project notes
`stratified-sampling-balance-two-axes` / `-guard-both-counters`: set a **target
count per group first** (the marginals), then draw at random and **check both
axis counts on every pick**, rejecting a pick when either of its groups is full.
The rarest cells are drawn first so the draw does not stall. Fixed seed → same
result every time. Exact targets and achieved counts are in `sampling.json`.

- **Axis 1 — specialty** (given in the data). Like CLEF's rare-category filter
  (`diagnosis-frequency-filter-five-percent`), a specialty with ≥2% of notes is
  its own group (12 of them); the 28 rarer specialties pool into one **"Other"**
  group → 13 groups, none empty.
- **Axis 2 — note-type** (derived). 7 types set from section headers
  (`note_type_method: header-rules-v1`): Operative/Procedure, Consult/H&P,
  Other/Letter, Diagnostic report, Discharge summary, SOAP/Progress,
  Pathology/Autopsy. At least 1 each, so Pathology/Autopsy (0.5%) shows up.
  **`note_type` is a guessed label, not gold** — a sampling axis only, not truth.

`split` (train/test) is kept in the manifest but is **not** a sampling axis.

## Layout

```
DATASET_CARD.md      this file
SCHEMA.md            the label set (CLEF: 6 entities + 3 modifiers)
docs/NNNN.txt        one cleaned note per file — THE GROUND TRUTH FOR OFFSETS
manifest.jsonl       one row per note: ids, both axes, split, char_len, sha256
sampling.json        how it was drawn: seed, N, per-axis target & achieved counts
```

Model predictions live **outside** this dir, one sibling per model, all the same
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
| `split` | original train/test (kept, not an axis) |
| `char_len` / `orig_char_len` | cleaned length / pre-clean length |
| `keyword_tail_stripped` | whether a keyword tail was removed |
| `text_sha256` | pins the exact cleaned bytes models must annotate |

## Version

`v1` — N=80, seed=20260723, schema=CLEF entities. Bump the version (new dir) for
any change to cleaning, axes, N, or schema; never change a frozen dataset that
already has runs against it.
