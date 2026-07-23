---
reviewed: No
reviewed_by:
---

# `openrouter_client.py` — model + text → reply

Script: `scripts/openrouter_client.py`

## What it does

The small helper for talking to OpenRouter: **give it a model id and some text,
get the model's reply and the real dollar cost.** It wraps the `openrouter` PyPI
SDK (`client.chat.send`) so callers never touch the SDK's typed request objects.
`annotate.py` is built on it; you can also use it directly for one-off calls or
new scripts.

## Auth

Set `OPENROUTER_API_KEY` in the environment:

```
export OPENROUTER_API_KEY=sk-or-...
```

## As a library

```python
from openrouter_client import chat, get_client

reply, cost = chat("anthropic/claude-sonnet-5", "Summarize: ...", system="You are terse.")

# reuse one client across many calls (an annotation loop):
client = get_client()
for note in notes:
    reply, cost = chat(model, note, system=SYS, temperature=0.0, client=client)
```

`chat(model, text, *, system=None, temperature=0.0, max_tokens=None,
reasoning_effort=None, timeout_ms=120000, client=None) -> (content, cost_usd)`.

Pass `reasoning_effort="none"` to turn off thinking on reasoning models (see the
note below).

## As a CLI

```
uv run python scripts/openrouter_client.py --model MODEL (--text T | --text-file F) \
    [--system S | --system-file F] [--temperature 0.0] [--max-tokens N] [--reasoning LEVEL]
```

| Option | Meaning |
| --- | --- |
| `--model` | OpenRouter model id, e.g. `anthropic/claude-sonnet-5`, `openai/gpt-4o`, `meta-llama/llama-3.1-8b-instruct`. |
| `--text` / `--text-file` | The prompt text, inline or from a file (one is required). |
| `--system` / `--system-file` | Optional system prompt, inline or from a file. |
| `--temperature` | Sampling temperature (default `0.0`). |
| `--max-tokens` | Cap on output tokens (left off → the provider's default). |
| `--reasoning` | Thinking budget for reasoning models (`none`…`max`). |

The reply prints to **stdout**; the cost prints to **stderr** (`[cost $…]`), so
you can pipe the reply on its own.

### Example

```
$ uv run python scripts/openrouter_client.py --model anthropic/claude-sonnet-5 --text "Ping in one word"
Pong
[cost $0.000123]
```

*(Live example — needs a funded key; the exact reply and cost vary.)*

## Notes

- **Cost** is OpenRouter's reported `usage.cost` for the call, `0.0` if the
  provider did not report it.
- **Reasoning models** (like Claude Sonnet 5) think by default. If the thinking
  uses up the whole token budget, `content` comes back empty. Pass
  `reasoning_effort="none"` (or `--reasoning none`) to turn thinking off for plain
  tasks. `annotate.py` does this by default.
- Errors (missing key, network failures) raise. The CLI prints to stderr and
  exits non-zero. The SDK handles retries and timeouts inside.
