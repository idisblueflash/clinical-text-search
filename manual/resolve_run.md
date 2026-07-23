# `resolve_run.py` — offline annotations → a run

Script: `scripts/resolve_run.py`

## What it does

Turns **offline annotations** — made by a Claude Code agent or a human, not the
OpenRouter API — into the standard `runs/<name>/` format. The annotator gives
verbatim entity `text`+`label` per doc (never offsets). This script finds each
substring in the frozen doc to get `[start, end)`, using the **same** `resolve()`
code as `annotate.py`. So an agent/human run and an API run have the exact same
shape and both work with `check_offsets.py` and `compare.py`.

This is the resolve step of the [agent annotation workflow](agent-annotation.md).
It works the same way for human-made annotations.

## Input / output

```
<out>/raw/NNNN.json        one per doc: {"entities":[{text,label,modifies?}]}  (or a bare [ … ] list)
   ↓
<out>/predictions.jsonl    resolved spans with offsets
<out>/run.json             model, annotator, role, dataset, schema_ver, counts
```

Each `raw/NNNN.json` must use **verbatim** span text (an exact substring of the
note) — a reworded span can't be found and becomes an unlocated span. `modifies`
(modifiers only) is the exact text of the entity it belongs to.

## Usage

```
uv run python scripts/resolve_run.py OUT --model ID [options]
```

| Option | Default | Meaning |
| --- | --- | --- |
| `OUT` | *(required)* | Run dir; expects `OUT/raw/`, writes `predictions.jsonl` + `run.json`. |
| `--model ID` | *(required)* | Model/annotator id saved in `run.json`, e.g. `claude-opus-4-8`. |
| `--annotator STR` | = `--model` | A readable description of the annotator. |
| `--run-tag TAG` | — | e.g. `r1`. |
| `--role STR` | `candidate` | `reference` (silver standard) or `candidate`. |
| `--dataset DIR` | `datasets/mtsamples-ner-v1` | The frozen dataset to resolve against. |
| `--entities-only` | off | Ignore the 3 modifiers. |

## Example

```
$ uv run python scripts/resolve_run.py runs/opus-agent-r1 \
    --model claude-opus-4-8 --annotator "claude-code agent (Opus, 8 parallel cold-start batches)" \
    --run-tag r1 --role reference
resolved 80/80 docs → runs/opus-agent-r1  (1 unlocated spans)
```

If a doc is missing or malformed, it says so and exits non-zero:

```
resolved 78/80 docs → runs/opus-agent-r1  (11 unlocated spans)
  MISSING (2): 0047, 0071
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All dataset docs resolved (some spans may be unlocated — reported). |
| `1` | Missing or malformed docs, or dataset sha drift. |
| `2` | Usage error (no `raw/` dir). |

## Notes

- **Missing docs don't lose the data already resolved** — `predictions.jsonl` is
  written for whatever resolved. The non-zero exit + `MISSING` list tells you what
  to fill in (continue the same agent, then run it again). See the workflow page.
- Check the run with `check_offsets.py` after resolving, before you compare.
