---
reviewed: No
reviewed_by:
---

# manual/

How-to pages for every command in this repo — one `.md` per command, with real
commands and real output. The goal: **anyone can do a task here without AI**. Read
the page, copy a command, and see what it does and what it makes.

For AI: treat these pages as the source of truth. Follow the page instead of
guessing a command from the code.

## Conventions

- **One file per command**, named after the script (`build_dataset.md` ↔
  `scripts/build_dataset.py`). A task that spans several commands (or a spawned
  agent) gets a **workflow** page instead (e.g. `agent-annotation.md`).
- Each page has the same parts: **What it does · Usage · Options · Examples (with
  real output) · Output files · Gotchas**.
- **Examples show real output**, copied from an actual run — not made up. Re-copy
  it when the command changes.
- Keep it in sync: when you add or change a command, add or update its page in the
  same commit.

## Commands

| Command | Page | Purpose |
| --- | --- | --- |
| `scripts/build_dataset.py` | [build_dataset.md](build_dataset.md) | Clean + stratified-sample MTSamples into the frozen `mtsamples-ner-v1` dataset |
| `scripts/openrouter_client.py` | [openrouter_client.md](openrouter_client.md) | Small helper: give it a model + text, get the reply (+ cost) from OpenRouter |
| `scripts/annotate.py` | [annotate.md](annotate.md) | Run any OpenRouter model as the NER annotator over a frozen dataset → `runs/<model>/` |
| `scripts/resolve_run.py` | [resolve_run.md](resolve_run.md) | Turn offline (agent/human) annotations into a run — finds offsets, writes `runs/<name>/` |
| `scripts/check_offsets.py` | [check_offsets.md](check_offsets.md) | Check a run's offsets against the frozen dataset (`doc[start:end] == text`) |

## Workflows

Tasks that combine several commands (and, for the agent path, a spawned Opus
agent):

| Workflow | Page | What it does |
| --- | --- | --- |
| Annotate with one Opus agent | [agent-annotation.md](agent-annotation.md) | Use a single Claude Code Opus agent (no API) as a reference/silver annotator → resolve → check |
