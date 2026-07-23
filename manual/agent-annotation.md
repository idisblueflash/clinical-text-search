---
reviewed: No
reviewed_by:
---

# Workflow: annotate with one Opus agent (no API)

How to make a run using a **Claude Code agent (Opus)** as the annotator — the
harness's own Opus, not the OpenRouter API. This is the offline path: the agent
gives verbatim `text`+`label` per doc, and `resolve_run.py` finds the offsets and
writes the same `runs/<name>/` format everything else reads.

## When to use this vs. `annotate.py`

| | This workflow (agent) | `annotate.py` (OpenRouter API) |
| --- | --- | --- |
| Model | Harness Opus, via a spawned agent | **Any** OpenRouter model (Claude/GPT/local) |
| Cost | No API charge | Charged ($ per token) |
| Best for | A strong **reference / silver standard** | Candidates, local models, self-consistency ×N |
| Repeatable? | No (each round is its own run) | No (save the temperature; see `specs/compare.md`) |
| Offsets | Model never gives them — found after | Same — found after |

Both paths write the same run format, so `check_offsets.py` and (later)
`compare.py` treat an agent run and an API run the same.

> **Silver, not gold.** An Opus reference is a *silver* standard — a draft for
> ranking and for humans to fix, not proven truth. Scoring a same-family candidate
> (like Sonnet) against an Opus reference reads high (shared bias). See the
> reasoning in `devlog.md`.

## The workflow

### 1. Make the run dir

```
mkdir -p runs/<name>/raw          # e.g. runs/opus-agent-r1/raw
```

Name each round with a tag: `opus-agent-r1`, `-r2`, … (agent output is not
repeatable, so each round is its own run).

### 2. Spawn ONE Opus agent with the annotation spec

Use the Agent tool with `model: opus` (subagent type `general-purpose`). The
prompt must say: read the rules first, then write one raw JSON file per doc.
Template (the paths are absolute on purpose):

```
You are producing reference NER annotations (silver standard) for a clinical NLP
dataset, following the project's annotation guideline.

STEP 1 — read first:
  - <repo>/guideline.md               (process, decision cues, worked example)
  - <repo>/datasets/mtsamples-ner-v1/SCHEMA.md   (label definitions)
Labels: Condition, Intervention, Investigation, Result, Drug_or_device, Locus;
modifiers Negation, Laterality, Sub_location.

STEP 2 — annotate docs 0001.txt … 0080.txt in
<repo>/datasets/mtsamples-ner-v1/docs/ . For each NNNN.txt:
  read it, extract entities per the guideline, and WRITE
  <repo>/runs/<name>/raw/NNNN.json as one JSON object:
    {"doc_id":"NNNN","entities":[
      {"text":"melanoma","label":"Condition"},
      {"text":"right","label":"Laterality","modifies":"groin"},
      {"text":"groin","label":"Locus"}]}

CRITICAL:
- `text` = exact VERBATIM substring of the note (same case/punctuation; no
  paraphrase). Offsets are found later by locating your text, so a paraphrase
  is a lost span.
- Do NOT output character offsets. Only text, label, and (modifiers only)
  `modifies` = verbatim text of the entity it belongs to.
- Guideline conventions: longest span; "myocardial infarction" = one Condition;
  "groin dissection" = groin (Locus) + dissection (Intervention). Mark every
  mention. Annotate planned/hypothetical. Skip bare section headers.
- Write each file right away (so progress is safe). Do all 80; skip none. Valid
  JSON per file.
CONSTRAINTS: only write under runs/<name>/raw/ ; never modify datasets/ or scripts.
When done: report how many of 80 written + any docs that were hard to label.
```

For a **small** set, one agent can loop through all docs. For a **large** set,
**don't** — split it into parallel batches (next section). One agent doing 80 docs
gets worse as it goes.

### 2b. For a large set: parallel batches (recommended)

One agent doing many docs **builds up context** — every doc it reads and every
file it writes stays in its window. Two problems follow:

1. **Cost and time grow** — later docs are done through an ever-bigger context.
2. **Drift** — by doc 40 the agent is in a noisier state than at doc 1, so the
   quality is *uneven* across the set.

Fix: **split the docs into small batches (~10 each) and spawn one fresh Opus agent
per batch, in parallel.** Each agent gets the *same* spec (only its doc-id list
changes). You get: small, even context per doc; fast wall-clock; and a stalled
batch is a small re-run.

**Does this hurt reference consistency?** No — it often *helps*. The consistency
that matters comes from the **guideline + schema + prompt + same model (Opus)**,
not from it being one process. Fresh agents remove the drift a single long run
has, so a batched set is usually *more* consistent, not less. The one risk is that
different agents settle a truly unclear case in different ways — the guideline's
hard-case rules keep that small, and when it shows up it tells you which rule to
make clearer. (This is *planned, even splitting*, not the ad-hoc "second agent
guesses the rest" that the resume note below warns against.)

The merge is free: every agent writes to the same `runs/<name>/raw/`, and
`resolve_run.py` reads all `raw/*.json` no matter which agent wrote each one.

Batch size ~8–12: small enough to stay light, big enough that re-reading the rules
is worth it. Example split for 80 docs → 8 agents: `0001–0010`, `0011–0020`, …
`0071–0080`.

### 3. Resolve offsets → a run

```
uv run python scripts/resolve_run.py runs/<name> \
    --model claude-opus-4-8 --annotator "claude-code agent (Opus, not OpenRouter)" \
    --run-tag r1 --role reference
```

Reads `runs/<name>/raw/*.json`, finds each verbatim span in the frozen doc, and
writes `runs/<name>/predictions.jsonl` + `run.json`. It reports any **missing**
(un-annotated) or **malformed** docs and exits non-zero if there are any. See
[resolve_run.md](resolve_run.md).

### 4. Check the offsets

```
uv run python scripts/check_offsets.py runs/<name> --verbose
```

Must end with `RESULT: OK`. See [check_offsets.md](check_offsets.md).

## Resuming a partial run

Nothing is lost when an agent stops — each doc is its own file, and
`resolve_run.py` lists exactly which `doc_id`s are missing. To fill them in:

- **Batched (parallel) runs:** just spawn a fresh agent for the missing batch with
  the same spec — that stays consistent by design (same guideline/schema/prompt/
  model). This is the normal case.
- **Single-agent runs:** continue the *same* agent (SendMessage with its id) for
  the missing docs. Don't let a *differently-worded* agent guess the rest — that
  ad-hoc mismatch is the thing to avoid (it is not the same as an even split, §2b).

## Output

```
runs/<name>/raw/NNNN.json     agent's verbatim annotations (input to resolve)
runs/<name>/predictions.jsonl resolved spans with offsets (standard run format)
runs/<name>/run.json          model, annotator, role, dataset, schema_ver, counts
```

`run.json.role` = `reference` marks this as the silver standard; candidate runs
(from `annotate.py`) are compared against it.
