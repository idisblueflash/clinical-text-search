---
reviewed: Yes
reviewed_by: Flash Hu
---

# CLAUDE.md — working rules for clinical-annotation-tools

Rules for Claude Code (and humans) working in this repo. Read `README.md` for
what the project is and `devlog.md` for *why* past decisions were made.

## Write in plain, simple English

The reader may be an L2 English speaker. Write so they get it on the first read —
in chat replies **and** in docs, comments, and commit messages.

- Use short, common words. Skip rare or fancy ones (say "use", not "utilize";
  "enough", not "sufficient"; "so", not "consequently").
- Keep sentences short — one idea each. Break up long ones.
- Prefer the active voice ("the script writes X", not "X is written by the script").
- Cut filler. Say the thing directly.
- Keep needed technical terms (offset, span, schema, stdlib) — they are precise.
  Just explain a term the first time if it is not obvious.
- Short does not mean vague: keep every fact, number, and caveat. Say it plainly.

## The main rule: frozen datasets never change

A dataset under `datasets/<name>/` is a **frozen, versioned thing**. Once it
exists (and once a run has annotated it), its bytes are the shared source of truth
for character offsets.

- **Never edit `docs/*.txt`, `manifest.jsonl`, or `sampling.json` by hand.** The
  script `scripts/build_dataset.py` makes them. Change the script, not the output.
- **Any change to cleaning, axes, N, or schema ⇒ a new version dir** (`-v2`),
  never a change to the old one. Changing a frozen dataset quietly breaks every
  run that was scored against it.
- The dataset is committed to git on purpose — so results can be reproduced.
  Don't gitignore it.

## Keep it repeatable

- `build_dataset.py` is **repeatable** (`SEED = 20260723`). Any code change must
  keep it so — re-running must make the same bytes.
- After changing the sampler, run `--report-only` and check that every axis hits
  its target exactly (`target == achieved`, `selected == N`). A stalled draw
  (`selected < N`) is a bug, not an acceptable result — see the rare-cells-first
  draw order in `devlog.md`.
- The **data pipeline stays stdlib-only** — do not add third-party deps to
  `build_dataset.py`. (Annotation may use deps: `openrouter` is the one runtime
  dependency, for API calls. Manage the env with `uv` — `uv run python …`,
  `uv add …`; the lockfile `uv.lock` is committed.)

## Model runs go in `runs/`, never in the dataset

- Predictions live in `runs/<model>/predictions.jsonl` + `run.json`, one sibling
  dir per model — **outside** `datasets/`. This keeps the input frozen and makes
  run-vs-run comparison simple.
- Every model annotates the **same bytes** with the **same schema** (`SCHEMA.md`).
  Don't invent per-model labels or re-clean the text per model.
- Offsets are half-open `[start, end)` character offsets into `docs/<doc_id>.txt`.
  Check that `text == doc[start:end]` before you trust a run (`check_offsets.py`).

## Data and licensing

- **MIMIC-IV is restricted — never commit it** (or any restricted-license data).
  This repo uses only public MTSamples. If you touch data sources, keep this line.
- The notes are de-identified clinical text; keep them that way.

## Decisions and deferred work

- `devlog.md` is the decision log: **newest on top, write down the *why*.** When
  you make a non-obvious choice or knowingly defer something, add an entry (mark
  deferrals so nothing quietly slips through).
- Prefer updating `devlog.md` / the dataset card over leaving decisions only in
  commit messages.

## Keep the manual in sync

- `manual/` has a plain how-to page per command, so a person can do a task
  **without AI**. When you add or change a command's behavior, options, or output,
  update its `manual/*.md` page in the **same commit**, and re-copy the example
  output by actually running the command (examples must be real, not made up).
- Add new commands to the table in `manual/README.md`.

## Doc review status (frontmatter)

Every `.md` starts with frontmatter:

```
---
reviewed: No
reviewed_by:
---
```

- `reviewed: No` means **no human has verified this doc yet** (AI may have written
  it). A person flips it to `Yes` after reading it, and puts their name in
  `reviewed_by:`.
- **Editing a doc's body resets `reviewed` to `No` and clears `reviewed_by:`.** A
  review only vouches for the version that was read. So when you change any doc,
  reset its frontmatter (unless a human is doing the review in the same change).
- Find docs that still need a human read:
  `grep -rl "reviewed: No" --include=*.md .`

## Commits

- Commit or push only when asked. Branch first if on the default branch.
