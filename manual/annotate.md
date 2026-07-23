---
reviewed: No
reviewed_by:
---

# `annotate.py` — run a model as the NER annotator

Script: `scripts/annotate.py`

## What it does

Runs a CLEF-schema NER prompt (see `datasets/mtsamples-ner-v1/SCHEMA.md`) over
every note in a frozen dataset, using **any OpenRouter model**, and writes a run
in a model-neutral format:

```
runs/<model-slug>[-<tag>]/predictions.jsonl   one line per doc: {doc_id, entities:[…]}
runs/<model-slug>[-<tag>]/run.json            model, date, temperature, cost, counts, …
```

Every model annotates the **same frozen bytes** in `docs/*.txt`, so runs compare
directly — repeat one model for **self-consistency**, or run different models for
**run-vs-run agreement** (both via `specs/compare.md`).

### How offsets work (important)

LLMs can't give reliable character offsets. So the model returns **verbatim entity
substrings + labels**, and the script finds each substring in the frozen text to
get `[start, end)`. If a span's text can't be found, it is kept with `start`/`end`
= `null` and `"located": false` — **shown, never dropped**. `run.json` reports
`n_unlocated_spans`; watch it in the pilot.

## Auth

```
export OPENROUTER_API_KEY=sk-or-...
```

## Usage

```
uv run python scripts/annotate.py --model MODEL [options]
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--model` | *(required)* | OpenRouter model id, e.g. `anthropic/claude-sonnet-5`. |
| `--dataset DIR` | `datasets/mtsamples-ner-v1` | Dataset to annotate. |
| `--out DIR` | `runs/<model-slug>[-<tag>]` | Where to write the run. |
| `--run-tag TAG` | — | Suffix for repeat runs, e.g. `r1`/`r2`/`r3` (self-consistency). |
| `--limit N` | — | Only the first N docs (**pilot**). |
| `--docs IDS` | — | Comma-separated `doc_id`s, e.g. `0001,0002`. |
| `--temperature T` | `0.0` | Sampling temperature. **Save it** — see gotchas. |
| `--reasoning LEVEL` | `none` | Thinking budget for reasoning models (`none`…`max`). Keep `none` — see gotchas. |
| `--max-tokens N` | `4000` | Cap on output tokens per note. |
| `--timeout SEC` | `120` | Timeout per call. |
| `--entities-only` | off | Skip the 3 modifiers (`Negation`/`Laterality`/`Sub_location`). |
| `--dry-run` | off | Print the prompt for the first doc and exit — **no API call, no key needed**. |

## Examples

### See the prompt without calling the API (`--dry-run`)

```
$ uv run python scripts/annotate.py --model anthropic/claude-opus-4 --limit 1 --dry-run
# DRY RUN — 0001 (2439 chars), model=anthropic/claude-opus-4, temp=0.0, entities_only=False

=== system ===
You are a clinical NLP annotator. Extract named entities …
…
=== user ===
SPECIMENS:,1.  Pelvis-right pelvic obturator node.,2.  Pelvis-left pelvic …
```

Use this to check the prompt and confirm the doc loads before you spend tokens.

### Pilot on 5 docs, then scale up

```
$ uv run python scripts/annotate.py --model anthropic/claude-opus-4 --limit 5
  [1/5] 0001  23 spans  $0.0142
  [2/5] 0002  17 spans  $0.0261  (1 unlocated)
  …
wrote 5 predictions + run.json to runs/anthropic-claude-opus-4  (cost $0.07, 0 failed, 1 unlocated spans)
```

*(Live output — needs a funded key; span counts and cost vary by model and note.)*

### Self-consistency: same model, 3 runs

```
uv run python scripts/annotate.py --model MODEL --run-tag r1
uv run python scripts/annotate.py --model MODEL --run-tag r2
uv run python scripts/annotate.py --model MODEL --run-tag r3
# → runs/<slug>-r1, -r2, -r3, then compare (specs/compare.md)
```

## Output format

`predictions.jsonl`, one line per doc:

```json
{"doc_id": "0001",
 "entities": [
   {"i": 0, "start": 150, "end": 158, "text": "prostate", "label": "Locus"},
   {"i": 1, "start": 22, "end": 27, "text": "right", "label": "Laterality", "modifies": 0}
 ]}
```

`start`/`end` are half-open offsets into `docs/<doc_id>.txt`. `modifies` (modifiers
only) points at the `i` of the entity it belongs to. A failed doc is
`{"doc_id", "entities": [], "error": "…"}` — kept in place, not skipped.

## Gotchas

- **Save the temperature — it defines the run.** `run.json` stores it. For a
  self-consistency test, run at the temperature you will really use. At `temp=0`
  most models barely vary, so the score is trivially ~1.0 (see `specs/compare.md`).
- **Watch `n_unlocated_spans`.** A high count means the model is rewording instead
  of copying word for word, so those offsets are lost. Fix the prompt
  (`PROMPT_VER`) if the pilot shows many.
- **`PROMPT_VER` / `SCHEMA_VER` are the comparability keys.** If you change the
  prompt or the label set, runs from before and after are no longer comparable —
  bump the version constant in the script and note it.
- **Reasoning models must have thinking off** (the default). Claude Sonnet 5 and
  other reasoning models will otherwise use the whole `--max-tokens` budget
  thinking and return **empty content** (`finish_reason: length`, all tokens in
  `reasoning_details`) — then every doc fails to parse. The first live Sonnet-5 run
  failed this way until `--reasoning none`. Only raise it if you want to study
  thinking on purpose (and then set `--max-tokens` well above the thinking budget).
- **Cost is real money.** Always pilot with `--limit` first; the run prints a
  running dollar total and the final cost.
