#!/usr/bin/env python3
"""Minimal Ollama client — list local models, or give one a prompt.

Same small (model, text) -> reply primitive as openrouter_client.py /
lmstudio_client.py, but it talks to a LOCAL Ollama server. No API key, no dollar
cost — the model runs on your own machine. Good for cheap/local candidate runs
(e.g. gemma) to compare against the silver standard.

Stdlib only (urllib). Speaks Ollama's native REST API:
  * GET  /api/tags  — list local models        (https://docs.ollama.com/api)
  * POST /api/chat  — one chat turn (stream:false)
(That is the same API the `ollama` Python package wraps; we use plain HTTP to
avoid a dependency and to keep the proxy-bypass below in our own hands.)

Server: OLLAMA_HOST (Ollama's own env var; default http://localhost:11434). A bare
host:port is fine — the scheme is added. Or pass --base-url.

Two Ollama specifics this handles:
  * num_predict — Ollama caps output at 128 tokens BY DEFAULT, which truncates a
    long NER reply. Pass --num-predict (e.g. -1 = until the model stops).
  * think — a thinking model (e.g. gemma4) emits a separate reasoning field; pass
    --no-think to turn it off (the equivalent of --reasoning none) so the whole
    budget is not spent thinking.

Use as a library:
    from ollama_client import chat, list_models
    reply = chat("gemma4:e2b", "Summarize: ...", system="You are terse.", think=False)

or standalone from the shell:
    uv run python scripts/ollama_client.py --list
    uv run python scripts/ollama_client.py --model gemma4:e2b --text "Hello"
    uv run python scripts/ollama_client.py --model gemma4:e2b --no-think --num-predict -1 --text-file note.txt
"""
import os, sys, json, argparse, urllib.request, urllib.error

DEFAULT_BASE_URL = "http://localhost:11434"

# Ollama is a LOCAL server. Any ambient HTTP proxy (e.g. a Clash proxy at
# 127.0.0.1:7897) must NOT be used for it — routing localhost through a proxy fails.
# This opener has an empty ProxyHandler, so it always connects directly.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def base_url(explicit=None):
    b = (explicit or os.environ.get("OLLAMA_HOST") or DEFAULT_BASE_URL).rstrip("/")
    if not b.startswith(("http://", "https://")):     # OLLAMA_HOST may be a bare host:port
        b = "http://" + b
    return b


def _unreachable(base, err):
    return RuntimeError(
        f"cannot reach Ollama at {base} ({err}). Is it running? (start it with `ollama serve`, "
        f"or set OLLAMA_HOST / --base-url).")


def list_models(*, base=None, timeout=30):
    """Return the names of the models Ollama has locally (like `ollama list`)."""
    b = base_url(base)
    try:
        with _OPENER.open(f"{b}/api/tags", timeout=timeout) as r:
            data = json.load(r)
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        raise _unreachable(b, e)
    return [m["name"] for m in data.get("models", [])]


def chat(model, text, *, system=None, temperature=0.0, num_predict=None,
         think=None, base=None, timeout=120):
    """Send one (model, text) turn to a local Ollama model. Return the reply text.

    `system` is an optional system prompt. `num_predict` caps output tokens (Ollama
    defaults to 128 — raise it, or -1 for no cap). `think=False` disables a thinking
    model's reasoning pass. If the model returns only `thinking` and an empty
    `content`, we fall back to the thinking text so the caller never gets ''."""
    b = base_url(base)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": text})
    options = {"temperature": temperature}
    if num_predict is not None:
        options["num_predict"] = num_predict
    payload = {"model": model, "messages": messages, "stream": False, "options": options}
    if think is not None:                              # only send for thinking-capable models
        payload["think"] = think
    req = urllib.request.Request(
        f"{b}/api/chat", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Ollama {e.code} for model {model!r}: {detail}")
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        raise _unreachable(b, e)
    msg = res.get("message", {})
    return (msg.get("content") or msg.get("thinking") or "").strip()


def main():
    ap = argparse.ArgumentParser(description="List local Ollama models, or prompt one.")
    ap.add_argument("--list", action="store_true", help="list local models and exit")
    ap.add_argument("--model", help="model name (see --list), e.g. gemma4:e2b")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--text", help="prompt text")
    g.add_argument("--text-file", help="read prompt text from a file")
    ap.add_argument("--system", help="system prompt text")
    ap.add_argument("--system-file", help="read system prompt from a file")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--num-predict", type=int,
                    help="max output tokens (Ollama default 128 truncates; use -1 for no cap)")
    ap.add_argument("--no-think", action="store_true",
                    help="disable the reasoning pass on a thinking model (e.g. gemma4)")
    ap.add_argument("--base-url", help=f"Ollama server (default {DEFAULT_BASE_URL}; or OLLAMA_HOST)")
    ap.add_argument("--timeout", type=int, default=120, help="seconds (default 120)")
    args = ap.parse_args()

    try:
        if args.list:
            models = list_models(base=args.base_url, timeout=args.timeout)
            print(f"# {len(models)} model(s) at {base_url(args.base_url)}")
            for m in models:
                print(m)
            return

        if not args.model:
            ap.error("--model is required (unless --list)")
        if args.text is None and args.text_file is None and sys.stdin.isatty():
            ap.error("give a prompt via --text, --text-file, or stdin")
        if args.text is not None:
            text = args.text
        elif args.text_file is not None:
            text = open(args.text_file).read()
        else:
            text = sys.stdin.read()
        system = open(args.system_file).read() if args.system_file else args.system

        reply = chat(args.model, text, system=system, temperature=args.temperature,
                     num_predict=args.num_predict, think=False if args.no_think else None,
                     base=args.base_url, timeout=args.timeout)
    except Exception as e:
        print(f"ollama_client: {e}", file=sys.stderr)
        sys.exit(1)
    print(reply)


if __name__ == "__main__":
    main()
