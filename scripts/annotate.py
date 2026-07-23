#!/usr/bin/env python3
"""Annotate the frozen NER dataset with any OpenRouter model.

Runs a CLEF-schema NER prompt (see SCHEMA.md) over every note in a dataset and
writes a model-agnostic run: runs/<model>[-<tag>]/predictions.jsonl + run.json.
Because every model annotates the *same frozen bytes* in docs/*.txt, runs are
directly comparable (self-consistency across repeats; agreement across models) —
that comparison is specs/compare.md.

OFFSETS: LLMs cannot reliably emit character offsets, so the model returns
verbatim entity SUBSTRINGS + labels and THIS script locates them in the frozen
text to produce [start,end). Entities whose text can't be found are kept with
start/end = null and "located": false — surfaced, never silently dropped.

The OpenRouter call goes through scripts/openrouter_client.py (the reusable
model+text->response primitive).

Auth: set OPENROUTER_API_KEY. Usage:
    export OPENROUTER_API_KEY=sk-or-...
    uv run python scripts/annotate.py --model anthropic/claude-sonnet-5 --limit 5

NOTE: reasoning defaults to 'none'. Thinking models (e.g. Claude Sonnet 5) will
otherwise spend the whole token budget reasoning and return EMPTY content — the
first live Sonnet-5 run failed exactly this way until reasoning was disabled.
"""
import sys, json, time, re, argparse, hashlib, pathlib
from datetime import datetime, timezone

from openrouter_client import chat, get_client

DATASET_DEFAULT = "datasets/mtsamples-ner-v1"
SCHEMA_VER = "clef-v1"          # SCHEMA.md label set
PROMPT_VER = "ner-v1"           # bump when SYSTEM_PROMPT changes (invalidates comparability)

ENTITIES = ["Condition", "Intervention", "Investigation", "Result", "Drug_or_device", "Locus"]
MODIFIERS = ["Negation", "Laterality", "Sub_location"]

SYSTEM_PROMPT = """\
You are a clinical NLP annotator. Extract named entities from the clinical note \
using EXACTLY this label set (CLEF scheme):

ENTITIES
- Condition: symptom, diagnosis, complication, problem, injury (e.g. "melanoma", "facial pain").
- Intervention: action a clinician performs to treat/change a Condition (e.g. "groin dissection", "ORIF").
- Investigation: action to measure/study — not change — a Condition (e.g. "CT scan", "biopsy").
- Result: numeric/qualitative finding of an Investigation (e.g. "normal", "80mg", "12 x 5 cm").
- Drug_or_device: a drug or device (e.g. "co-codamol", "Hemovac drain").
- Locus: anatomical location/structure/body substance (e.g. "right groin", "C2").

MODIFIERS (each attaches to one entity above)
- Negation: signals a Condition is negated/uncertain (e.g. "no evidence", "denies").
- Laterality: sidedness — right/left/bilateral.
- Sub_location: finer location — upper/lower/extra/etc.

RULES
- Copy each entity's `text` VERBATIM from the note — exact substring, same case, no paraphrase, no trimming.
- Mark the maximal clinically meaningful span (e.g. "fracture dislocation", not two spans).
- For a modifier, set `modifies` to the VERBATIM text of the entity it qualifies.
- Return ONLY JSON, no prose, no code fence:
  {"entities": [{"text": "...", "label": "<one label>", "modifies": "<entity text, modifiers only>"}]}
"""


def _die(msg: str):
    print(f"annotate: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_entities(raw):
    """Lenient parse of the model's JSON reply (handles code fences / stray prose).
    Return (entities_list, error_or_None)."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)          # strip a wrapping code fence
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)              # fall back to first {...}
        if not m:
            return [], "no JSON object in reply"
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            return [], f"unparseable JSON: {e}"
    ents = obj.get("entities") if isinstance(obj, dict) else None
    if not isinstance(ents, list):
        return [], "no 'entities' list"
    return ents, None


def locate(text, doc, claimed):
    """Find the first occurrence of `text` in `doc` not already claimed (to keep
    repeated words distinct). Return (start, end) or (None, None)."""
    start = 0
    while True:
        idx = doc.find(text, start)
        if idx < 0:
            return None, None
        span = (idx, idx + len(text))
        if span not in claimed:
            return span
        start = idx + 1


def resolve(ents, doc, *, entities_only):
    """Turn the model's [{text,label,modifies?}] into schema spans with offsets.
    Entities first (so modifiers can point at their index); modifiers second."""
    out, claimed = [], set()
    valid = set(ENTITIES) if entities_only else set(ENTITIES) | set(MODIFIERS)
    ent_items = [e for e in ents if isinstance(e, dict) and e.get("label") in ENTITIES]
    mod_items = [] if entities_only else [
        e for e in ents if isinstance(e, dict) and e.get("label") in MODIFIERS]
    text_to_i = {}                                          # entity text -> its span index
    i = 0
    for e in ent_items:
        t = (e.get("text") or "").strip()
        if not t:
            continue
        st, en = locate(t, doc, claimed)
        if st is not None:
            claimed.add((st, en))
        span = {"i": i, "start": st, "end": en, "text": t, "label": e["label"]}
        if st is None:
            span["located"] = False
        out.append(span); text_to_i.setdefault(t, i); i += 1
    for e in mod_items:
        t = (e.get("text") or "").strip()
        if not t:
            continue
        st, en = locate(t, doc, claimed)
        if st is not None:
            claimed.add((st, en))
        span = {"i": i, "start": st, "end": en, "text": t, "label": e["label"]}
        if st is None:
            span["located"] = False
        tgt = (e.get("modifies") or "").strip()
        if tgt in text_to_i:
            span["modifies"] = text_to_i[tgt]
        out.append(span); i += 1
    n_unlocated = sum(1 for s in out if s.get("located") is False)
    return out, n_unlocated


def load_manifest(dataset):
    rows = {}
    with open(pathlib.Path(dataset) / "manifest.jsonl") as f:
        for line in f:
            r = json.loads(line)
            rows[r["doc_id"]] = r
    return rows


def model_slug(model):
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser(description="Annotate the frozen NER dataset via OpenRouter.")
    ap.add_argument("--model", required=True, help="OpenRouter model id, e.g. anthropic/claude-opus-4")
    ap.add_argument("--dataset", default=DATASET_DEFAULT)
    ap.add_argument("--out", help="run dir (default runs/<model-slug>[-<tag>])")
    ap.add_argument("--run-tag", help="suffix for repeated runs, e.g. r1/r2/r3 (self-consistency)")
    ap.add_argument("--limit", type=int, help="only the first N docs (pilot)")
    ap.add_argument("--docs", help="comma-separated doc_ids, e.g. 0001,0002")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--reasoning", default="none",
                    choices=["none", "minimal", "low", "medium", "high", "xhigh", "max"],
                    help="reasoning-model thinking budget; default 'none' — thinking wastes the "
                         "token budget on verbatim extraction and can truncate output to empty.")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--entities-only", action="store_true", help="skip the 3 modifiers")
    ap.add_argument("--dry-run", action="store_true", help="print the prompt for the first doc; no API call")
    args = ap.parse_args()

    dataset = pathlib.Path(args.dataset)
    manifest = load_manifest(dataset)

    doc_ids = sorted(manifest)
    if args.docs:
        want = [d.strip() for d in args.docs.split(",")]
        missing = [d for d in want if d not in manifest]
        if missing:
            _die(f"doc_ids not in dataset: {missing}")
        doc_ids = want
    if args.limit:
        doc_ids = doc_ids[:args.limit]

    # load + verify we are annotating the frozen bytes (sha256 must match manifest)
    docs = {}
    for did in doc_ids:
        text = (dataset / manifest[did]["text_file"]).read_text()
        if hashlib.sha256(text.encode()).hexdigest() != manifest[did]["text_sha256"]:
            _die(f"{did}: text sha256 != manifest — dataset not frozen/consistent, aborting.")
        docs[did] = text

    if args.dry_run:
        did = doc_ids[0]
        print(f"# DRY RUN — {did} ({len(docs[did])} chars), model={args.model}, "
              f"temp={args.temperature}, entities_only={args.entities_only}\n")
        print("=== system ===\n" + SYSTEM_PROMPT)
        print("\n=== user ===\n" + docs[did])
        return

    out_name = args.out
    if not out_name:
        out_name = "runs/" + model_slug(args.model) + (f"-{args.run_tag}" if args.run_tag else "")
    out = pathlib.Path(out_name); out.mkdir(parents=True, exist_ok=True)

    try:
        client = get_client()          # fail fast on a missing key, before any writes
    except RuntimeError as e:
        _die(str(e))

    total_cost, results, n_failed, n_unlocated_total = 0.0, [], 0, 0
    t0 = time.time()
    for n, did in enumerate(doc_ids, 1):
        try:
            raw, cost = chat(args.model, docs[did], system=SYSTEM_PROMPT,
                             temperature=args.temperature, max_tokens=args.max_tokens,
                             reasoning_effort=args.reasoning,
                             timeout_ms=args.timeout * 1000, client=client)
        except Exception as e:
            n_failed += 1
            print(f"  [{n}/{len(doc_ids)}] {did}  API FAIL: {e}", file=sys.stderr)
            results.append({"doc_id": did, "entities": [], "error": str(e)})
            continue
        total_cost += cost
        ents, perr = parse_entities(raw)
        if perr:
            n_failed += 1
            print(f"  [{n}/{len(doc_ids)}] {did}  PARSE FAIL: {perr}", file=sys.stderr)
            results.append({"doc_id": did, "entities": [], "error": perr})
            continue
        spans, n_unloc = resolve(ents, docs[did], entities_only=args.entities_only)
        n_unlocated_total += n_unloc
        results.append({"doc_id": did, "entities": spans})
        flag = f"  ({n_unloc} unlocated)" if n_unloc else ""
        print(f"  [{n}/{len(doc_ids)}] {did}  {len(spans)} spans  ${total_cost:.4f}{flag}")

    with open(out / "predictions.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    run_meta = {
        "model": args.model,
        "run_tag": args.run_tag,
        "date": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset.name,
        "schema_ver": SCHEMA_VER,
        "prompt_ver": PROMPT_VER,
        "entities_only": args.entities_only,
        "temperature": args.temperature,       # KEY for self-consistency (see specs/compare.md)
        "reasoning_effort": args.reasoning,
        "max_tokens": args.max_tokens,
        "n_docs": len(doc_ids),
        "n_failed_docs": n_failed,
        "n_unlocated_spans": n_unlocated_total,
        "total_cost_usd": round(total_cost, 6),
        "elapsed_sec": round(time.time() - t0, 1),
        "provider": "openrouter",
    }
    json.dump(run_meta, open(out / "run.json", "w"), indent=2)
    print(f"\nwrote {len(results)} predictions + run.json to {out}"
          f"  (cost ${total_cost:.4f}, {n_failed} failed, {n_unlocated_total} unlocated spans)")


if __name__ == "__main__":
    main()
