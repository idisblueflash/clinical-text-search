# Workflow: annotate with one Opus agent (no API)

How to produce a run using a **single Claude Code agent (Opus)** as the annotator
— the harness's own Opus, not the OpenRouter API. This is the offline annotation
path: the agent emits verbatim `text`+`label` per doc, and `resolve_run.py`
computes offsets into the same `runs/<name>/` format everything else consumes.

## When to use this vs. `annotate.py`

| | This workflow (agent) | `annotate.py` (OpenRouter API) |
| --- | --- | --- |
| Model | Harness Opus, via a spawned agent | **Any** OpenRouter model (Claude/GPT/local) |
| Cost | No API metering | Metered ($ per token) |
| Best for | A strong **reference / silver standard** | Candidates, local models, self-consistency ×N |
| Determinism | No (agent run; each round is its own run) | No (record temperature; see `specs/compare.md`) |
| Offsets | Never emitted by the model — resolved after | Same — resolved after |

Both paths write the identical run format, so `check_offsets.py` and (later)
`compare.py` treat an agent run and an API run the same.

> **Silver, not gold.** An Opus reference is a *silver standard* — a draft for
> ranking and for humans to correct, not validated truth. Comparing a same-family
> candidate (e.g. Sonnet) against an Opus reference reads high (correlated bias).
> See the reasoning in `devlog.md`.

## The workflow

### 1. Prepare the run dir

```
mkdir -p runs/<name>/raw          # e.g. runs/opus-agent-r1/raw
```

Name rounds with a tag: `opus-agent-r1`, `-r2`, … (a fresh agent run per round;
agent output isn't deterministic, so each round is its own run).

### 2. Spawn ONE Opus agent with the annotation spec

Use the Agent tool with `model: opus` (subagent type `general-purpose`). The
prompt must pin: read the rules first, then write one raw JSON file per doc.
Template (paths are absolute on purpose):

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
  paraphrase). Offsets are computed later by locating your text, so a paraphrase
  is a lost span.
- Do NOT output character offsets. Only text, label, and (modifiers only)
  `modifies` = verbatim text of the entity it qualifies.
- Guideline conventions: maximal span; "myocardial infarction" = one Condition;
  "groin dissection" = groin (Locus) + dissection (Intervention). Mark every
  mention. Annotate planned/hypothetical. Skip bare section headers.
- Write each file immediately (durable progress). Do all 80; skip none. Valid
  JSON per file.
CONSTRAINTS: only write under runs/<name>/raw/ ; never modify datasets/ or scripts.
When done: report how many of 80 written + any genuinely ambiguous docs.
```

For a **small** set, one agent can loop through all docs. For a large set,
**don't** — split it into parallel batches (next section); a single agent
annotating 80 docs degrades.

### 2b. For a large set: parallel batches (recommended)

A single agent annotating many docs **accumulates context** — every doc it reads
and every file it writes stays in its window. Two failure modes result:

1. **Cost/latency growth** — later docs are annotated through an ever-larger context.
2. **Context drift** — by doc 40 the agent is in a noisier state than at doc 1, so
   quality is *non-uniform* across the set.

Fix: **partition the docs into small batches (~10 each) and spawn one cold-start
Opus agent per batch, in parallel.** Each agent gets the *identical* spec (only
its doc-id list differs). Benefits: bounded, uniform per-doc context; parallel
wall-clock; fault isolation (a stalled batch is a small re-run).

**Does this break reference consistency?** No — and it often *improves* it. The
consistency that matters lives in the **guideline + schema + prompt + same model
(Opus)**, not in it being one process. Cold-start agents eliminate the context
drift a single long run suffers, so a chunked set is typically *more* internally
consistent, not less. The residual risk is that independent agents resolve a
genuinely ambiguous case differently — mitigated by the guideline's explicit
hard-case conventions, and if it surfaces, that's useful signal to harden the
guideline. (This is *planned uniform partitioning*, not the ad-hoc "second agent
winging the remainder" that the resume note below warns against.)

The merge is free: every agent writes to the same `runs/<name>/raw/`, and
`resolve_run.py` reads all `raw/*.json` regardless of which agent wrote each.

Batch size ~8–12: small enough to stay lean, large enough to amortize each agent
re-reading the rules. Example partition for 80 docs → 8 agents: `0001–0010`,
`0011–0020`, … `0071–0080`.

### 3. Resolve offsets → a run

```
uv run python scripts/resolve_run.py runs/<name> \
    --model claude-opus-4-8 --annotator "claude-code agent (Opus, not OpenRouter)" \
    --run-tag r1 --role reference
```

Reads `runs/<name>/raw/*.json`, locates each verbatim span in the frozen doc, and
writes `runs/<name>/predictions.jsonl` + `run.json`. It reports any **missing**
(un-annotated) or **malformed** docs and exits non-zero if any. See
[resolve_run.md](resolve_run.md).

### 4. Validate the offsets

```
uv run python scripts/check_offsets.py runs/<name> --verbose
```

Must end `RESULT: OK`. See [check_offsets.md](check_offsets.md).

## Resuming a partial run

Nothing is lost when an agent stops — each doc was written as its own file, and
`resolve_run.py` lists exactly which `doc_id`s are missing. To backfill:

- **Batched (parallel) runs:** just re-spawn a fresh cold-start agent for the
  missing batch with the same spec — that's consistent by construction (identical
  guideline/schema/prompt/model). This is the normal case.
- **Single-agent runs:** continue the *same* agent (SendMessage with its id) for
  the missing docs, rather than having a *differently-instructed* agent wing the
  remainder — that ad-hoc inconsistency is the thing to avoid (it's different from
  a planned uniform partition, see §2b).

## Output

```
runs/<name>/raw/NNNN.json     agent's verbatim annotations (input to resolve)
runs/<name>/predictions.jsonl resolved spans with offsets (standard run format)
runs/<name>/run.json          model, annotator, role, dataset, schema_ver, counts
```

`run.json.role` = `reference` marks this as the silver standard; candidate runs
(from `annotate.py`) are compared against it.
