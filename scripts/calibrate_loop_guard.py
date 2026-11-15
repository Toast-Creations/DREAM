"""Replay recorded generations through the V1.3.3 loop guard; no model is loaded.

Reads every generation_complete event (raw text: reasoning plus answer) from the
given supervision event logs, tokenizes it with the model's own tokenizer, and
reports where the guard would have stopped it, checking every ``check_every``
tokens exactly as generation does. Read-only: it prints a summary and, with
--out, writes a JSON report there.
"""
import argparse
import json
from pathlib import Path
import _bootstrap  # noqa: F401  (adds src to sys.path)
from dream_core.modeling import loop_detected, loop_share


def first_stop(ids, guard):
    for end in range(guard["check_every"], len(ids) + 1, guard["check_every"]):
        if loop_detected(ids[:end], guard):
            return end
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer", required=True, help="local model directory")
    parser.add_argument("--guard", required=True, help='JSON, e.g. {"window_tokens":800,"ngram":12,"repeat_share":0.75,"check_every":16}')
    parser.add_argument("--out")
    parser.add_argument("events", nargs="+")
    args = parser.parse_args()
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True)
    guard = json.loads(args.guard)
    rows = []
    for path in args.events:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("event") != "generation_complete":
                continue
            out = event["output"]
            text = out.get("raw_text") or (out.get("thinking", "") + out.get("text", ""))
            ids = tokenizer.encode(text, add_special_tokens=False)
            shares = [loop_share(ids[:end], guard) for end in range(guard["window_tokens"], len(ids) + 1, 64)]
            rows.append({"log": path, "call": event.get("call"), "tokens": len(ids),
                         "finish_reason": out.get("finish_reason"), "stop_at": first_stop(ids, guard),
                         "max_share": max([s for s in shares if s is not None], default=None)})
    fired = [r for r in rows if r["stop_at"] is not None]
    print(f"{len(rows)} generations, guard fired on {len(fired)}")
    for r in sorted(fired, key=lambda r: r["log"]):
        print(f"  FIRED {r['log'].split('/Runs/')[-1]} call {r['call']}: stop at {r['stop_at']} of {r['tokens']} tokens ({r['finish_reason']})")
    top = sorted((r for r in rows if r["stop_at"] is None and r["max_share"] is not None), key=lambda r: -r["max_share"])[:8]
    for r in top:
        print(f"  near   {r['log'].split('/Runs/')[-1]} call {r['call']}: max share {r['max_share']:.2f}, {r['tokens']} tokens ({r['finish_reason']})")
    if args.out:
        Path(args.out).write_text(json.dumps({"guard": guard, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
