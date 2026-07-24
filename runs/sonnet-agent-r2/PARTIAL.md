---
reviewed: No
reviewed_by:
---

# sonnet-agent-r2 — PARTIAL run (do not compare yet)

Second Sonnet agent round, meant to give Sonnet's **self-consistency** ceiling
next to `sonnet-agent-r1` (see [`../SELF_CONSISTENCY.md`](../SELF_CONSISTENCY.md)).
It is **incomplete** — the 8 cold-start batch agents hit a session limit mid-run.

- **Have:** `raw/NNNN.json` for **37 of 80** docs (all valid JSON).
- **No** `predictions.jsonl` / `run.json` yet — `resolve_run.py` has not been run.
- **Do not** feed this to `compare.py`: an incomplete run would fake-deflate the
  self-consistency number.

## Missing 43 docs (to finish the round)

```
0002–0010, 0020, 0028–0030, 0032–0040, 0046–0050, 0057–0060, 0069–0080
```

## How to resume

Annotate only the missing docs the same way `raw/` was made (fresh Sonnet agents,
cold start — do NOT let them read `sonnet-agent-r1`, so r1 vs r2 stays
independent). Then build and check the run:

```
uv run python scripts/resolve_run.py runs/sonnet-agent-r2 --model claude-sonnet-5 \
    --annotator "claude-code agent (Sonnet, cold-start batches)" --run-tag r2 --role candidate
uv run python scripts/check_offsets.py runs/sonnet-agent-r2
uv run python scripts/compare.py runs/sonnet-agent-r1 runs/sonnet-agent-r2 --match exact
uv run python scripts/compare.py runs/sonnet-agent-r1 runs/sonnet-agent-r2 --match relaxed
```

Then add a Sonnet section to `runs/SELF_CONSISTENCY.md` and delete this file.
