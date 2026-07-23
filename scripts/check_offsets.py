#!/usr/bin/env python3
"""Validate a run's entity offsets against the frozen dataset.

The core invariant of every run: each located span must satisfy
    doc[start:end] == text
against the exact frozen bytes in docs/<doc_id>.txt. This CLI checks that (and a
few related integrity rules) for a whole run, so offset correctness is verified
by a command, not by eyeballing.

Checks per predicted entity:
  * bounds        0 <= start <= end <= len(doc), ints, half-open
  * text match    doc[start:end] == text            (MISMATCH = corruption/bug)
  * unlocated     start/end null + located:false    (reported, not a failure)
  * modifies      points at a valid, different span index in the same doc
  * label         is in the CLEF schema set          (warning)
And per run: every predicted doc_id exists in the dataset and its text sha256
matches the manifest (i.e. the run annotated the frozen bytes).

Exit status: 0 if clean (unlocated spans allowed), 1 if any MISMATCH / bounds /
bad-modifies / unknown-doc / sha-drift is found.

    uv run python scripts/check_offsets.py runs/anthropic-claude-sonnet-5
    uv run python scripts/check_offsets.py runs/<model> --verbose
"""
import sys, json, hashlib, argparse, pathlib

DATASET_DEFAULT = "datasets/mtsamples-ner-v1"
ENTITIES = {"Condition", "Intervention", "Investigation", "Result", "Drug_or_device", "Locus"}
MODIFIERS = {"Negation", "Laterality", "Sub_location"}
LABELS = ENTITIES | MODIFIERS


def load_manifest(dataset):
    rows = {}
    with open(pathlib.Path(dataset) / "manifest.jsonl") as f:
        for line in f:
            r = json.loads(line)
            rows[r["doc_id"]] = r
    return rows


def check_doc(rec, doc, manifest_row):
    """Return (n_spans, n_located_ok, n_unlocated, problems[]). `problems` are
    hard failures (each a (kind, detail) tuple)."""
    problems, n_ok, n_unloc = [], 0, 0
    ents = rec.get("entities", [])
    n = len(ents)
    idxs = {e.get("i") for e in ents}
    for e in ents:
        i, text, label = e.get("i"), e.get("text", ""), e.get("label")
        start, end = e.get("start"), e.get("end")
        tag = f"i={i} {label!r} {text!r}"
        if label not in LABELS:
            problems.append(("unknown-label", f"{tag}: label not in schema"))
        # modifies pointer
        if "modifies" in e:
            m = e["modifies"]
            if m not in idxs:
                problems.append(("bad-modifies", f"{tag}: modifies={m} has no such span"))
            elif m == i:
                problems.append(("bad-modifies", f"{tag}: modifies points at itself"))
        # offsets
        if start is None or end is None:
            n_unloc += 1
            if e.get("located") is not False:
                problems.append(("null-offset-unmarked",
                                 f"{tag}: null offset but not marked located:false"))
            continue
        if not (isinstance(start, int) and isinstance(end, int)):
            problems.append(("bad-type", f"{tag}: start/end not ints")); continue
        if not (0 <= start <= end <= len(doc)):
            problems.append(("out-of-bounds", f"{tag}: [{start},{end}) vs len {len(doc)}")); continue
        actual = doc[start:end]
        if actual != text:
            problems.append(("MISMATCH", f"{tag}: doc[{start}:{end}]={actual!r}"))
        else:
            n_ok += 1
    return n, n_ok, n_unloc, problems


def main():
    ap = argparse.ArgumentParser(description="Validate a run's entity offsets against the frozen dataset.")
    ap.add_argument("run", help="run dir (runs/<model>) or a predictions.jsonl path")
    ap.add_argument("--dataset", default=DATASET_DEFAULT)
    ap.add_argument("--verbose", action="store_true", help="print every problem span")
    args = ap.parse_args()

    run = pathlib.Path(args.run)
    pred_path = run if run.is_file() else run / "predictions.jsonl"
    if not pred_path.exists():
        print(f"check_offsets: no predictions.jsonl at {pred_path}", file=sys.stderr); sys.exit(2)

    dataset = pathlib.Path(args.dataset)
    manifest = load_manifest(dataset)

    tot_spans = tot_ok = tot_unloc = tot_prob = n_failed = 0
    hard_fail = False
    print(f"run: {run}   dataset: {dataset.name}")
    with open(pred_path) as f:
        for line in f:
            rec = json.loads(line)
            did = rec["doc_id"]
            if did not in manifest:
                print(f"  {did}  UNKNOWN DOC — not in dataset"); hard_fail = True; continue
            if "error" in rec and not rec.get("entities"):
                n_failed += 1
                print(f"  {did}  (failed doc: {rec['error'][:60]})"); continue
            doc = (dataset / manifest[did]["text_file"]).read_text()
            if hashlib.sha256(doc.encode()).hexdigest() != manifest[did]["text_sha256"]:
                print(f"  {did}  SHA DRIFT — dataset bytes changed since run"); hard_fail = True; continue
            n, n_ok, n_unloc, problems = check_doc(rec, doc, manifest[did])
            tot_spans += n; tot_ok += n_ok; tot_unloc += n_unloc; tot_prob += len(problems)
            hard = [p for p in problems if p[0] != "null-offset-unmarked"] or problems
            if problems:
                hard_fail = True
            flag = f"  {len(problems)} PROBLEM(S)" if problems else ""
            unl = f"  {n_unloc} unlocated" if n_unloc else ""
            print(f"  {did}  {n:>3} spans  {n_ok:>3} verified{unl}{flag}")
            if args.verbose:
                for kind, detail in problems:
                    print(f"        - {kind}: {detail}")

    print(f"\nsummary: {tot_spans} spans across the run  |  {tot_ok} located & verified  |  "
          f"{tot_unloc} unlocated  |  {tot_prob} problems  |  {n_failed} failed docs")
    if hard_fail:
        print("RESULT: FAIL" + ("" if args.verbose else "  (re-run with --verbose for details)"))
        sys.exit(1)
    print("RESULT: OK — all located spans match the frozen text")


if __name__ == "__main__":
    main()
