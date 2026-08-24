"""Validate two exact mGBA breakpoint traces of the same AI turn.

Usage:
    python tools/validate_ai_trace.py trace-a.json trace-b.json
"""
import argparse
import json
import sys


EVALUATOR = 0x080C32C0


def load(path):
    with open(path) as fh:
        return json.load(fh)


def normalized(trace):
    return [{
        "pc": hit["pc"],
        "registers": hit["registers"],
        "cpsr": hit.get("cpsr"),
        "rng_seed": hit.get("rng_seed"),
        "stack": hit.get("stack"),
    } for hit in trace["hits"]]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("first")
    ap.add_argument("second")
    args = ap.parse_args(argv)

    a, b = load(args.first), load(args.second)
    hits = a.get("hits", [])
    checks = [
        (a.get("mode") == b.get("mode") == "breakpoint",
         "both captures are exact breakpoint traces"),
        (a.get("address") == b.get("address") == EVALUATOR,
         "both traces target sub_080C32C0"),
        (len(hits) == len(b.get("hits", [])) == 4,
         "one AI actor evaluates exactly four targets"),
        (len({h["registers"]["r0"] for h in hits}) == 1 and
         len({h["registers"]["r1"] for h in hits}) == 4,
         "user pointer is stable and target pointers are distinct"),
        (normalized(a) == normalized(b),
         "registers, RNG states, and stack snapshots reproduce exactly"),
    ]
    for ok, label in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
    print(f"\n{sum(ok for ok, _ in checks)}/{len(checks)} checks passed")
    return 0 if all(ok for ok, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
