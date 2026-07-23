# `check_offsets.py` — check a run's offsets

Script: `scripts/check_offsets.py`

## What it does

Checks the one rule every run must follow, against the **frozen** dataset bytes:

```
doc[start:end] == text        for every located span
```

If a run's offsets are right, agreement/F1 between runs is just arithmetic. So
this check is the gate a run must pass before you trust or compare it. Standard
library only (no deps). It exits non-zero on any hard problem, so it fits in CI or
a pre-compare step.

## Usage

```
uv run python scripts/check_offsets.py RUN [--dataset DIR] [--verbose]
```

- `RUN` — a run dir (`runs/<model>/`) or a direct `predictions.jsonl` path.
- `--dataset` — the frozen dataset to check against (default `datasets/mtsamples-ner-v1`).
- `--verbose` — print every problem span, not just the per-doc count.

## What it checks

| Check | Meaning | Hard fail? |
| --- | --- | --- |
| **text match** | `doc[start:end] == text` | **yes** (`MISMATCH`) |
| **bounds** | `0 <= start <= end <= len(doc)`, ints, half-open | **yes** |
| **modifies** | points at a real, different span index in the doc | **yes** |
| **doc identity** | every predicted `doc_id` is in the dataset | **yes** |
| **sha256** | the doc bytes still match `manifest.jsonl` (frozen) | **yes** |
| **unlocated** | `start`/`end` null + `located: false` | no (reported) |
| **label** | the label is in the CLEF schema set | reported |

**Unlocated spans are not failures.** They are an expected, tracked outcome: the
model gave a span whose exact text could not be found in the note. A `MISMATCH` is
different — an offset points at the *wrong* text, which means a resolver bug or
changed dataset bytes.

## Examples

### A clean run

```
$ uv run python scripts/check_offsets.py runs/anthropic-claude-sonnet-5 --verbose
run: runs/anthropic-claude-sonnet-5   dataset: mtsamples-ner-v1
  0001   72 spans   71 verified  1 unlocated
  0002  100 spans  100 verified
  0003   61 spans   61 verified

summary: 233 spans across the run  |  232 located & verified  |  1 unlocated  |  0 problems  |  0 failed docs
RESULT: OK — all located spans match the frozen text
```

Exit code `0`.

### A run with bad spans (`--verbose`)

```
  0001    4 spans    1 verified  4 PROBLEM(S)
        - MISMATCH: i=1 'Condition' 'WRONGTEXT': doc[0:9]='SPECIMENS'
        - out-of-bounds: i=2 'Result' 'x': [99999,100000) vs len 2439
        - bad-modifies: i=3 'Laterality' '.,1.': modifies=7 has no such span
...
RESULT: FAIL
```

Exit code `1`.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Clean — all located spans checked (unlocated spans are allowed). |
| `1` | At least one hard problem (mismatch / bounds / modifies / unknown doc / sha drift). |
| `2` | Usage error (no `predictions.jsonl` found). |

## How it fits the pipeline

`annotate.py` finds offsets by searching for each verbatim span in the frozen
doc, and reports its own `n_unlocated_spans`. `check_offsets.py` is the
**independent** checker — run it after any annotation, and before you feed runs to
`compare.py` (`specs/compare.md`), so a comparison never runs on bad offsets.
