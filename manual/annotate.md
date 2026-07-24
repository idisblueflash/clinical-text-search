---
reviewed: No
reviewed_by:
---

# `annotate.py` — run a model as the NER annotator

Script: `scripts/annotate.py`

## What it does

Runs a CLEF-schema NER prompt (see `datasets/mtsamples-ner-v1/SCHEMA.md`) over
every note in a frozen dataset and writes a run in a model-neutral format. Two
backends, **same prompt and same offset logic**, chosen with `--provider`:

- `openrouter` (default) — any OpenRouter model (paid API).
- `lmstudio` — a **local** model served by LM Studio (e.g. on the Mac Mini). No
  API key, no cost. Open the SSH tunnel first (see
  [`lmstudio_client.md`](lmstudio_client.md)).

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

For `--provider openrouter`:

```
export OPENROUTER_API_KEY=sk-or-...
```

For `--provider lmstudio` no key is needed — just make the local server reachable
(SSH tunnel to the Mini):

```
ssh -f -N -L 1234:localhost:1234 macmini
```

## Usage

```
uv run python scripts/annotate.py --model MODEL [options]
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--model` | *(required)* | Model id. OpenRouter: `anthropic/claude-sonnet-5`. LM Studio: an id from `lmstudio_client.py --list`, e.g. `qwen/qwen3-1.7b`. |
| `--provider` | `openrouter` | `openrouter` (paid API) or `lmstudio` (local, no cost). |
| `--base-url URL` | `http://localhost:1234/v1` | LM Studio server (or `LMSTUDIO_BASE_URL`). Only for `--provider lmstudio`. |
| `--no-think` | off | Append `/no_think` to each prompt — the LM Studio equivalent of `--reasoning none` for Qwen models. |
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

### Local model via LM Studio (no cost)

Open the tunnel first, confirm the model is loaded, then run with
`--provider lmstudio`:

```
$ ssh -f -N -L 1234:localhost:1234 macmini
$ uv run python scripts/lmstudio_client.py --list          # confirm the id is there
$ uv run python scripts/annotate.py --provider lmstudio --model qwen/qwen3-1.7b \
    --no-think --max-tokens 8000
  [1/80] 0001  11 spans  $0.0000
  …
  [80/80] 0080  13 spans  $0.0000  (1 unlocated)
wrote 80 predictions + run.json to runs/qwen-qwen3-1-7b  (cost $0.0000, 3 failed, 95 unlocated spans)
```

*(Real run. `qwen/qwen3-1.7b` under-annotates heavily — 606 spans vs a frontier
model's ~6,000 — and scored 0.075 exact-F1 vs the Opus silver. It works, but a
small local model is a weak annotator; see `devlog.md`. `qwen3-0.6b-mlx` is weaker
still — unusable here.)*

### Local model via Ollama (no cost)

Ollama on this Mac needs no tunnel; a remote Ollama (e.g. on the Mini) uses one
plus `--base-url`. `--num-predict` is set from `--max-tokens`; `--no-think`
disables a thinking model's reasoning pass. This example is a self-consistency
run (temp 0.7, `--run-tag`) against the Mini's Ollama:

```
$ uv run python scripts/annotate.py --provider ollama --base-url http://localhost:11435 \
    --model gemma4:e2b --no-think --temperature 0.7 --max-tokens 8000 --timeout 300 --run-tag r1
  [1/80] 0001  25 spans  $0.0000  (2 unlocated)
  …
wrote 80 predictions + run.json to runs/gemma4-e2b-r1  (cost $0.0000, 11 failed, 27 unlocated spans)
```

*(Real run. Repeat with `--run-tag r2`/`r3`, then `compare.py` the three for
self-consistency — gemma4 scored 0.732 mean pairwise F1. Use a **non-zero
temperature** for self-consistency, or the score is a trivial ~1.0; see
[`compare.md`](compare.md).)*

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
- **Cost is real money** (OpenRouter). Always pilot with `--limit` first; the run
  prints a running dollar total and the final cost. LM Studio runs cost `$0.0000`.
- **Local (`lmstudio`): use `--no-think` for Qwen models.** Qwen3 emits a hidden
  `<think>` block that eats `--max-tokens`; `--no-think` skips it, the same reason
  OpenRouter reasoning models need `--reasoning none`.
- **Tiny models can't do this task.** `qwen3-0.6b-mlx` returned the literal word
  `"ENTITIES"` as every label (0 valid spans) and broke JSON on long notes. Use a
  bigger local model (`qwen/qwen3-1.7b` works). Pilot with `--limit 3` and read the
  raw output before scaling.
- **Provider = part of the path; compare like with like.** An `lmstudio`/
  `openrouter` run uses this distilled prompt, *not* the agent path
  ([`agent-annotation.md`](agent-annotation.md)). The annotation path moves the
  score more than the model does (see `devlog.md`), so score same-path runs
  together, or note the path when you don't.
