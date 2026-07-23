# `openrouter_client.py` — model + text → response

Script: `scripts/openrouter_client.py`

## What it does

The reusable primitive for talking to OpenRouter: **give it a model id and some
text, get the model's reply and the real dollar cost.** Wraps the `openrouter`
PyPI SDK (`client.chat.send`) so callers never touch its typed request objects.
`annotate.py` is built on it; use it directly for one-off calls or new scripts.

## Auth

Set `OPENROUTER_API_KEY` in the environment:

```
export OPENROUTER_API_KEY=sk-or-...
```

## As a library

```python
from openrouter_client import chat, get_client

reply, cost = chat("anthropic/claude-opus-4", "Summarize: ...", system="You are terse.")

# reuse one client across many calls (annotation loop):
client = get_client()
for note in notes:
    reply, cost = chat(model, note, system=SYS, temperature=0.0, client=client)
```

`chat(model, text, *, system=None, temperature=0.0, max_tokens=None,
timeout_ms=120000, client=None) -> (content, cost_usd)`.

## As a CLI

```
uv run python scripts/openrouter_client.py --model MODEL (--text T | --text-file F) \
    [--system S | --system-file F] [--temperature 0.0] [--max-tokens N]
```

| Option | Meaning |
| --- | --- |
| `--model` | OpenRouter model id, e.g. `anthropic/claude-opus-4`, `openai/gpt-4o`, `meta-llama/llama-3.1-8b-instruct`. |
| `--text` / `--text-file` | Prompt text, inline or from a file (one required). |
| `--system` / `--system-file` | Optional system prompt, inline or from a file. |
| `--temperature` | Sampling temperature (default `0.0`). |
| `--max-tokens` | Output cap (omitted → provider default). |

The reply prints to **stdout**; the cost prints to **stderr** (`[cost $…]`), so
you can pipe the reply cleanly.

### Example

```
$ uv run python scripts/openrouter_client.py --model anthropic/claude-opus-4 --text "Ping in one word"
Pong
[cost $0.000123]
```

*(Live example — needs a funded key; the exact reply/cost vary.)*

## Notes

- **Cost** is OpenRouter's reported `usage.cost` for the call, `0.0` if the
  provider didn't report it.
- Errors (missing key, HTTP/transport failures) raise; the CLI prints to stderr
  and exits non-zero. The SDK handles retries/timeouts internally.
