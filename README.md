# clinical-annotation-tools

Tools for a clinical NLP prototype. The end goal: type a question in plain
language, get back the clinical notes that match. This repo builds the first,
hardest part of that pipeline — a clean, fixed dataset for named-entity
recognition (NER), the scripts that make it, and the model runs that annotate it.

There is **no UI yet** — you run everything from the command line. We put the UI
off on purpose (see `devlog.md`). First prove the hard part — clean data and NER
that different models can be compared on — then build the interface.

Companion research repo: `../semantic-annotation-of-clinical-text` — reading
notes, source papers, and the sampling/schema method this tooling follows.

## Layout

```
scripts/
  build_dataset.py       clean + stratified-sample MTSamples into a frozen dataset
  openrouter_client.py   small helper: (model, text) -> reply (+ cost) via OpenRouter
  annotate.py            run any OpenRouter model as the NER annotator -> runs/<model>/
  resolve_run.py         turn offline (agent/human) annotations into a run
  check_offsets.py       check a run's offsets against the frozen text
guideline.md             how to annotate the notes (humans + LLMs) — the CLEF method
manual/                  how-to page per command (real commands + real output)
specs/                   plans for commands not built yet (e.g. compare.py)
datasets/                frozen, versioned datasets (the input; committed to git)
  mtsamples-ner-v1/      80-note stratified NER sample
    DATASET_CARD.md        source, cleaning, stratification, manifest fields
    SCHEMA.md              the label set (CLEF: 6 entities + 3 modifiers)
    docs/NNNN.txt          one cleaned note — THE GROUND TRUTH FOR CHARACTER OFFSETS
    manifest.jsonl         one row per note: ids, both axes, split, char_len, sha256
    sampling.json          how it was drawn: seed, N, per-axis target vs achieved
runs/                    each model's predictions on a dataset (made when you annotate)
  <model>/                 predictions.jsonl + run.json, one dir per model
devlog.md                the decision log (the *why* behind each choice)
```

## The dataset: `mtsamples-ner-v1`

80 de-identified clinical notes, drawn from **MTSamples** (4,999 public
transcribed notes). It is the baseline for clinical NER and for comparing models.
Full detail in [`datasets/mtsamples-ner-v1/DATASET_CARD.md`](datasets/mtsamples-ner-v1/DATASET_CARD.md).

- **The frozen text is the source of truth.** Every model annotates the exact
  same bytes in `docs/*.txt`. So character offsets — and the agreement/F1 between
  any two runs — are just arithmetic. `manifest.jsonl` pins each note by SHA-256.
- **Cleaned before sampling** (4,922 notes of 4,999 kept): drop empty/`nan` notes
  and stubs under 100 characters, and strip the `keywords` tail that most
  MTSamples notes glue onto the end. That tail is metadata, not prose; it would
  make NER too easy and inflate the scores.
- **Two-axis stratified draw** (CLEF marginal-matching, Roberts et al. 2008): set
  a target count per group first, then draw at random and check **both** axis
  counts on every pick. Draw the rarest cells first so the draw does not stall.
  - Axis 1 — **specialty** (given in the data). Keep a specialty as its own group
    if it is ≥2% of notes → 12 groups + one "Other".
  - Axis 2 — **note-type** (derived from section headers, `header-rules-v1`), 7
    types, at least 1 each. *This label is a guess, not gold — a sampling axis only.*
  - `split` (train/test) is kept in the manifest but is **not** a draw axis.
- Repeatable: `N=80`, `seed=20260723`. Re-running makes the exact same bytes.

### Entity schema

The labels are the **CLEF** set (Roberts et al. 2008), used as-is so runs stay
comparable. Full definitions and boundary rules are in
[`SCHEMA.md`](datasets/mtsamples-ner-v1/SCHEMA.md).

- **6 entities**: `Condition`, `Intervention`, `Investigation`, `Result`,
  `Drug_or_device`, `Locus`.
- **3 modifiers** (a span with a `modifies` pointer): `Negation`, `Laterality`,
  `Sub_location`.
- CLEF **relations** are out of scope for v1 (a separate task → future `mtsamples-re-v1`).

To learn *how* to apply the labels — the steps, the judgment calls, the hard
cases, and a full worked example, for humans and LLMs — read
[`guideline.md`](guideline.md).

## Run format

A model's predictions live **outside** the dataset dir, one sibling dir per
model, all the same shape. So a new model drops in without touching the frozen
input:

```
runs/<model>/predictions.jsonl   {"doc_id","entities":[{i,start,end,text,label,modifies?}]}
runs/<model>/run.json            {model, date, dataset:"mtsamples-ner-v1", schema_ver, prompt_ver}
```

`start`/`end` are half-open character offsets into `docs/<doc_id>.txt`.

## Rebuild the dataset

```
python3 scripts/build_dataset.py               # repeatable (fixed seed)
python3 scripts/build_dataset.py --report-only # print the counts, write nothing
```

The script reads `mtsamples.csv` from the companion repo (path is in
`build_dataset.py`). This pipeline uses the Python standard library only. Full
usage, options, and example output: [`manual/build_dataset.md`](manual/build_dataset.md).

## Environment

Managed with [`uv`](https://docs.astral.sh/uv/). One runtime dependency —
`openrouter`, used for annotation. The data pipeline stays standard-library-only.

```
uv sync                                     # make the venv from uv.lock
uv run python scripts/<script>.py ...       # run anything in the venv
```

## Annotate

Any OpenRouter model can annotate the frozen dataset. Runs land in
`runs/<model>/` in the shared format above. See [`manual/annotate.md`](manual/annotate.md).

```
export OPENROUTER_API_KEY=sk-or-...
uv run python scripts/annotate.py --model anthropic/claude-sonnet-5 --limit 5   # pilot first
```

The small `(model, text) → reply` helper is `scripts/openrouter_client.py`
([`manual/openrouter_client.md`](manual/openrouter_client.md)).

You can also annotate with a Claude Code **Opus agent** instead of the API — good
for a strong reference set. See [`manual/agent-annotation.md`](manual/agent-annotation.md).

Always check a run's offsets against the frozen text (`doc[start:end] == text`)
before you trust or compare it:

```
uv run python scripts/check_offsets.py runs/<model>          # non-zero exit on any mismatch
```

See [`manual/check_offsets.md`](manual/check_offsets.md).

## Status

- **Done**: `mtsamples-ner-v1` built and frozen; the sampler is repeatable.
  OpenRouter annotator + helper client; the Opus-agent annotation path; the
  offset validator; the `guideline.md`.
- **Runs so far**: `runs/opus-agent-r1/` — an 80-note Opus reference set (a
  *silver* standard, made by 8 parallel agents), all offsets checked;
  `runs/anthropic-claude-sonnet-5/` — a 3-note Sonnet pilot.
- **Next**: run a full candidate model (e.g. Sonnet on all 80), then build
  `compare.py` to score self-consistency (same model ×3) and run-vs-run agreement.
- **Deferred** (tracked in `devlog.md`): the `compare.py` harness (planned in
  [`specs/compare.md`](specs/compare.md)); a human gold set; CLEF relations; the
  query→retrieval stages; the UI.
