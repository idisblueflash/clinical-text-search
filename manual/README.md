# manual/

Human-readable usage docs for every CLI in this repo — one `.md` per command,
with real commands and real output. The goal is that **anyone can pick up a task
here without AI assistance**: read the doc, copy a command, understand what it
does and what it produces.

For AI: treat these as the authoritative how-to. Prefer following a manual page
over re-deriving a command from the source.

## Conventions

- **One file per CLI**, named after the script (`build_dataset.md` ↔
  `scripts/build_dataset.py`). Multi-step procedures that span several commands
  (or a spawned agent) get a **workflow** page instead (e.g. `agent-annotation.md`).
- Each page follows the same shape: **What it does · Usage · Options ·
  Examples (with real output) · Output files · Gotchas**.
- **Examples show actual output**, captured by running the command — not
  invented. Re-capture when behavior changes.
- Keep it in sync: when you add or change a CLI, add or update its page in the
  same commit.

## Commands

| Command | Page | Purpose |
| --- | --- | --- |
| `scripts/build_dataset.py` | [build_dataset.md](build_dataset.md) | Clean + stratified-sample MTSamples into the frozen `mtsamples-ner-v1` dataset |
| `scripts/openrouter_client.py` | [openrouter_client.md](openrouter_client.md) | Reusable primitive: assign a model + text, get the response (+ cost) from OpenRouter |
| `scripts/annotate.py` | [annotate.md](annotate.md) | Run any OpenRouter model as the NER annotator over a frozen dataset → `runs/<model>/` |
| `scripts/resolve_run.py` | [resolve_run.md](resolve_run.md) | Resolve offline (agent/human) annotations into a run — computes offsets, writes `runs/<name>/` |
| `scripts/check_offsets.py` | [check_offsets.md](check_offsets.md) | Validate a run's entity offsets against the frozen dataset (`doc[start:end] == text`) |

## Workflows

Multi-step procedures that combine several commands (and, for the agent path, a
spawned Opus subagent):

| Workflow | Page | What it does |
| --- | --- | --- |
| Annotate with one Opus agent | [agent-annotation.md](agent-annotation.md) | Use a single Claude Code Opus agent (no API) as a reference/silver annotator → resolve → validate |
