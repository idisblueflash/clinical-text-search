#!/usr/bin/env python3
"""Minimal OpenRouter client — assign a model + text, get a response back.

The reusable primitive the annotator (and any future caller) builds on: give it
a model id and some text, get the model's reply and the real dollar cost. Wraps
the `openrouter` PyPI SDK (client.chat.send) so callers never touch its typed
request objects.

Auth: OPENROUTER_API_KEY. Use as a library:

    from openrouter_client import chat
    reply, cost = chat("anthropic/claude-opus-4", "Summarize: ...", system="You are terse.")

or standalone from the shell:

    export OPENROUTER_API_KEY=sk-or-...
    uv run python scripts/openrouter_client.py --model anthropic/claude-opus-4 --text "Hello"
    uv run python scripts/openrouter_client.py --model x/y --text-file note.txt --system-file sys.txt
"""
import os, sys, argparse
from openrouter import OpenRouter

TITLE = "clinical-annotation-tools"          # shown in OpenRouter activity logs (X-Title)


def get_client(api_key=None):
    """One configured OpenRouter client. Reuse it across many calls."""
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (required to call OpenRouter).")
    return OpenRouter(api_key=key, x_open_router_title=TITLE)


def chat(model, text, *, system=None, temperature=0.0, max_tokens=None,
         reasoning_effort=None, timeout_ms=120_000, client=None):
    """Send one (model, text) turn. Return (content, cost_usd).

    `system` is an optional system prompt. `reasoning_effort` controls a thinking
    model's reasoning budget ('none'..'max'); pass 'none' to disable thinking —
    important for reasoning models (e.g. Claude Sonnet 5) that otherwise spend the
    whole token budget thinking and return empty `content`. `cost_usd` is
    OpenRouter's reported dollar cost for the call (0.0 if not reported)."""
    client = client or get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": text})

    kwargs = {"model": model, "messages": messages, "temperature": temperature,
              "timeout_ms": timeout_ms}
    if max_tokens is not None:                 # omit so the model uses its own default
        kwargs["max_tokens"] = max_tokens
    if reasoning_effort is not None:           # omit for models without a reasoning knob
        kwargs["reasoning_effort"] = reasoning_effort

    res = client.chat.send(**kwargs)
    content = res.choices[0].message.content if res.choices else ""
    if isinstance(content, list):              # multimodal parts -> join text
        content = "".join(getattr(p, "text", "") or "" for p in content)
    cost = float(getattr(res.usage, "cost", None) or 0.0) if res.usage else 0.0
    return content or "", cost


def main():
    ap = argparse.ArgumentParser(description="Send a model + text to OpenRouter, print the reply.")
    ap.add_argument("--model", required=True, help="OpenRouter model id, e.g. anthropic/claude-opus-4")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="prompt text")
    g.add_argument("--text-file", help="read prompt text from a file")
    ap.add_argument("--system", help="system prompt text")
    ap.add_argument("--system-file", help="read system prompt from a file")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--reasoning", choices=["none", "minimal", "low", "medium", "high", "xhigh", "max"],
                    help="reasoning-model thinking budget (e.g. 'none' to disable)")
    args = ap.parse_args()

    text = args.text if args.text is not None else open(args.text_file).read()
    system = args.system
    if args.system_file:
        system = open(args.system_file).read()

    try:
        reply, cost = chat(args.model, text, system=system, temperature=args.temperature,
                           max_tokens=args.max_tokens, reasoning_effort=args.reasoning)
    except Exception as e:
        print(f"openrouter_client: {e}", file=sys.stderr)
        sys.exit(1)
    print(reply)
    print(f"\n[cost ${cost:.6f}]", file=sys.stderr)


if __name__ == "__main__":
    main()
