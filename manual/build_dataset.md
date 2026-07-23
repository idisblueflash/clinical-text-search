---
reviewed: No
reviewed_by:
---

# `build_dataset.py` — build the frozen NER dataset

Script: `scripts/build_dataset.py`

## What it does

Turns the raw MTSamples CSV into the frozen, versioned `mtsamples-ner-v1`
dataset. The steps:

1. **Load** the MTSamples CSV.
2. **Clean** — drop empty/`nan` notes and stubs under 100 characters; strip the
   `keywords` tail most notes glue onto the end.
3. **Find the note-type** from section headers (`header-rules-v1`).
4. **Stratified draw** on two axes (specialty × note-type), CLEF marginal-matching,
   checking both axis counts on every pick (Roberts et al. 2008).
5. **Write** `docs/*.txt` + `manifest.jsonl` + `sampling.json`.

Repeatable (`SEED = 20260723`): re-running makes the exact same dataset, byte for
byte. Python standard library only — no install step.

## Usage

```
python3 scripts/build_dataset.py [--csv PATH] [--out DIR] [--report-only]
```

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `--csv PATH` | `…/semantic-annotation-of-clinical-text/data/mtsamples/mtsamples.csv` | Source MTSamples CSV (columns `id, text, label, split`). |
| `--out DIR` | `datasets/mtsamples-ner-v1` | Where to write the dataset. |
| `--report-only` | off | Print the counts and stop — **writes nothing.** Use it to preview before a rebuild. |

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

**How to read it:** each axis row shows `target / got`. They must be equal on
every row, and the last line must say `selected: 80 / 80`. If `got < target`
anywhere (or `selected < 80`), the draw stalled — that is a bug; see Gotchas.

### Build the dataset

```
$ python3 scripts/build_dataset.py
… (same report as above) …
wrote 80 docs + manifest.jsonl + sampling.json to datasets/mtsamples-ner-v1
```

This clears any old `docs/*.txt` and writes the three outputs again.

### Build from a different source or into a different dir

```
$ python3 scripts/build_dataset.py --csv /path/to/mtsamples.csv --out /tmp/ds-test
```

Handy for a test run into a throwaway dir, without touching the committed dataset.

## Output files (in `--out`)

| File | What it is |
| --- | --- |
| `docs/NNNN.txt` | One cleaned note per file. **The ground truth for character offsets** every model annotates. |
| `manifest.jsonl` | One row per note: `doc_id`, `source_id`, both axis values, `split`, `char_len`, `text_sha256`, … |
| `sampling.json` | How it was drawn: seed, N, clean-universe size, per-axis `target` vs `achieved`. |

## Gotchas

- **This overwrites the frozen dataset.** `docs/*.txt` is cleared and rewritten.
  Never edit those files by hand — change the script and rebuild. See `CLAUDE.md`.
- **A stall means don't use it.** If `selected < 80`, the sample is incomplete (a
  rare cell ran out). The draw does rare cells first to avoid this; find out why
  rather than lowering `N`. Background in `devlog.md`.
- **It must stay repeatable.** Same CSV + same code ⇒ same bytes. If a change
  makes the output vary between runs, that is a bug.
- **Settings live at the top of the script** (`N`, `SEED`, `SPECIALTY_THRESHOLD`,
  `NOTE_TYPE_FLOOR`, `MIN_CHARS`). Changing any of them means a **new dataset
  version** (`-v2`), not a change to `v1`.
- **`note_type` is a guess**, not gold — a sampling axis only.
