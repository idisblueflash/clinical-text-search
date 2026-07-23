# `build_dataset.py` — build the frozen NER dataset

Script: `scripts/build_dataset.py`

## What it does

Turns the raw MTSamples CSV into the frozen, versioned `mtsamples-ner-v1`
dataset. Pipeline:

1. **Load** MTSamples CSV.
2. **Clean** — drop empty/`nan` and sub-100-char stubs; strip the appended
   `keywords` tail most notes glue onto the narrative.
3. **Derive note-type** from section headers (`header-rules-v1`).
4. **Stratified draw** on two axes (specialty × note-type), CLEF marginal-matching,
   guarding both axis counters on every draw (Roberts et al. 2008).
5. **Write** `docs/*.txt` + `manifest.jsonl` + `sampling.json`.

Deterministic (`SEED = 20260723`): re-running reproduces the identical dataset,
byte for byte. Python **stdlib only** — no install step.

## Usage

```
python3 scripts/build_dataset.py [--csv PATH] [--out DIR] [--report-only]
```

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `--csv PATH` | `…/semantic-annotation-of-clinical-text/data/mtsamples/mtsamples.csv` | Source MTSamples CSV (columns `id, text, label, split`). |
| `--out DIR` | `datasets/mtsamples-ner-v1` | Dataset output directory. |
| `--report-only` | off | Print the marginals and stop — **writes nothing.** Use to preview before committing to a rebuild. |

## Examples

### Preview the sample without writing (`--report-only`)

```
$ python3 scripts/build_dataset.py --report-only
clean universe: 4922 of 4999
specialty buckets (>= 2%): 12 + Other = 13
keyword-tail stripped: 3473 notes

== specialty axis ==   target / got
  Surgery                            18 / 18
  Other (rare specialties <2%)       17 / 17
  Consult - History and Phy.          8 /  8
  Orthopedic                          6 /  6
  Cardiovascular / Pulmonary          6 /  6
  Gastroenterology                    4 /  4
  General Medicine                    4 /  4
  Radiology                           4 /  4
  Neurology                           4 /  4
  SOAP / Chart / Progress Notes       3 /  3
  Discharge Summary                   2 /  2
  Urology                             2 /  2
  Obstetrics / Gynecology             2 /  2

== note-type axis ==   target / got
  Operative/Procedure    31 / 31
  Other/Letter           16 / 16
  Consult/H&P            16 / 16
  Diagnostic report      10 / 10
  Discharge summary       4 /  4
  SOAP/Progress           2 /  2
  Pathology/Autopsy       1 /  1

selected: 80 / 80
```

**Read it like this:** every axis row shows `target / got`. They must be equal on
every row, and the last line must read `selected: 80 / 80`. If `got < target`
anywhere (or `selected < 80`), the draw stalled — that is a bug; see Gotchas.

### Actually build the dataset

```
$ python3 scripts/build_dataset.py
… (same report as above) …
wrote 80 docs + manifest.jsonl + sampling.json to datasets/mtsamples-ner-v1
```

This clears any prior `docs/*.txt` and rewrites the three outputs.

### Build from a different source or into a different dir

```
$ python3 scripts/build_dataset.py --csv /path/to/mtsamples.csv --out /tmp/ds-test
```

Handy for a dry run into a throwaway dir without touching the committed dataset.

## Output files (in `--out`)

| File | What it is |
| --- | --- |
| `docs/NNNN.txt` | One cleaned narrative per note. **The character-offset ground truth** every model annotates. |
| `manifest.jsonl` | One row per note: `doc_id`, `source_id`, both axis values, `split`, `char_len`, `text_sha256`, … |
| `sampling.json` | Provenance: seed, N, clean-universe size, per-axis marginals (`target` vs `achieved`). |

## Gotchas

- **This overwrites the frozen dataset.** `docs/*.txt` is cleared and regenerated.
  Never edit those files by hand — change the script and rebuild. See `CLAUDE.md`.
- **A stall means don't ship it.** If `selected < 80` the sample is incomplete
  (joint sparsity in a rare cell). The draw is rarity-first specifically to avoid
  this; investigate rather than lowering `N`. Background in `devlog.md`.
- **Determinism must hold.** Same CSV + same code ⇒ identical bytes. If a change
  makes output vary run-to-run, that's a regression.
- **Config lives at the top of the script** (`N`, `SEED`, `SPECIALTY_THRESHOLD`,
  `NOTE_TYPE_FLOOR`, `MIN_CHARS`). Changing any of these means a **new dataset
  version** (`-v2`), not a mutation of `v1`.
- **`note_type` is heuristic**, not gold — a sampling axis only.
