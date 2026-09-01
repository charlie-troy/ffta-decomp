"""Partition FFTA's AI evaluator switch into control-flow-owned rule blocks.

The 92-entry jump table inside ``sub_080C32C0`` has 66 distinct targets.
Linear slicing at the next target is incorrect: cases branch into shared success,
reject, and scoring tails, and literal pools sit between code islands.  This tool
walks actual Thumb control flow from every distinct case root, then assigns an
instruction to a case only when that case alone can reach it.  Instructions
reached by multiple roots are reported as shared joins instead.

Usage:
    python tools/partition_ai_evaluator.py <rom.gba> [--markdown PATH]
"""

import argparse
import collections
import os
import sys

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib
import thumb


BASE = 0x08000000
FUNC_START = 0x080C32C0
FUNC_END = 0x080C47A8
TABLE_ADDR = 0x080C3624
CASE_COUNT = 92
CASE_CODE_START = 0x080C3794
# These are evaluator-level exits, not rule-body instructions.  In particular,
# 0x080C477A can advance to another candidate and redispatch the switch; walking
# through it would falsely make every later case reachable from every root.
STOP_ADDRS = {0x080C37B4, 0x080C477A, 0x080C478C, 0x080C478E}


def read_u32(rom, addr):
    off = addr - BASE
    return int.from_bytes(rom[off:off + 4], "little")


def decode_one(md, rom, addr):
    off = addr - BASE
    insns = list(md.disasm(rom[off:off + 4], addr, count=1))
    if not insns:
        raise ValueError(f"cannot decode instruction at {addr:#010x}")
    insn = insns[0]

    # Capstone accepts newer Thumb encodings.  Reject anything the GBA's
    # ARM7TDMI cannot execute, and require a valid two-halfword BL pair.
    cls, _ = thumb.classify(romlib.halfword(rom, off))
    if cls == thumb.INVALID:
        raise ValueError(f"non-ARMv4T instruction at {addr:#010x}")
    if cls == thumb.BL:
        cls2, _ = thumb.classify(romlib.halfword(rom, off + 2))
        if cls2 != thumb.BL:
            raise ValueError(f"broken BL pair at {addr:#010x}")
    return insn


def direct_target(insn):
    text = insn.op_str.strip()
    if not text.startswith("#"):
        return None
    return int(text[1:], 0)


def successors(insn):
    """Return (flow successors, external calls, terminal description).

    GCC uses BL for long transfers between islands inside this giant function.
    Those transfers do not return: every internal destination eventually exits
    through the evaluator epilogue.  A BL outside the function is an ordinary
    call and execution continues at the following instruction.
    """
    next_addr = insn.address + insn.size
    mnemonic = insn.mnemonic

    if mnemonic == "bl":
        target = direct_target(insn)
        if target is None:
            return [], [], "indirect call"
        if FUNC_START <= target < FUNC_END:
            return [target], [], f"local transfer {target:#010x}"
        return [next_addr], [target], None

    if mnemonic == "b":
        target = direct_target(insn)
        return ([target] if target is not None else []), [], None

    if mnemonic.startswith("b") and mnemonic not in ("bic", "bics", "bx"):
        target = direct_target(insn)
        if target is not None:
            return [next_addr, target], [], None

    if mnemonic == "bx" or (mnemonic == "mov" and insn.op_str.startswith("pc,")):
        return [], [], insn.mnemonic + " " + insn.op_str
    if mnemonic == "pop" and "pc" in insn.op_str:
        return [], [], "return"
    return [next_addr], [], None


def contiguous_ranges(addresses, insns):
    if not addresses:
        return []
    ordered = sorted(addresses)
    ranges = []
    start = ordered[0]
    end = start + insns[start].size
    for addr in ordered[1:]:
        if addr == end:
            end = addr + insns[addr].size
        else:
            ranges.append((start, end))
            start = addr
            end = addr + insns[addr].size
    ranges.append((start, end))
    return ranges


def fmt_ranges(ranges):
    return ", ".join(
        f"{start:#010x}-{end:#010x}" if end - start > 2 else f"{start:#010x}"
        for start, end in ranges
    ) or "-"


def semantic_shape(owned, insns):
    """Normalize addresses while retaining the source-level instruction shape."""
    out = []
    for addr in sorted(owned):
        insn = insns[addr]
        target = direct_target(insn)
        if insn.mnemonic == "bl":
            if target == 0x08002804:
                out.append("CALL_RNG")
            elif target == 0x08142950:
                out.append("CALL_MOD")
            elif target is not None and not (FUNC_START <= target < FUNC_END):
                out.append("CALL_EFFECT_TEST")
            else:
                out.append("GOTO")
        elif insn.mnemonic == "b":
            out.append("GOTO")
        elif insn.mnemonic.startswith("b"):
            out.append(insn.mnemonic)
        else:
            out.append(f"{insn.mnemonic} {insn.op_str}")
    return tuple(out)


def analyze(rom):
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    entries = collections.defaultdict(list)
    for case_id in range(1, CASE_COUNT + 1):
        target = read_u32(rom, TABLE_ADDR + (case_id - 1) * 4) & ~1
        if not (FUNC_START <= target < FUNC_END):
            raise ValueError(f"case {case_id} target outside evaluator: {target:#010x}")
        entries[target].append(case_id)
    if len(entries) != 66:
        raise ValueError(f"expected 66 distinct case roots, got {len(entries)}")

    insns = {}
    reachers = collections.defaultdict(set)
    calls_by_addr = collections.defaultdict(set)
    terminals = collections.defaultdict(set)
    edges = collections.defaultdict(set)

    for root in sorted(entries):
        pending = [root]
        seen = set()
        while pending:
            addr = pending.pop()
            if addr in seen:
                continue
            if not (FUNC_START <= addr < FUNC_END):
                terminals[root].add(f"outside {addr:#010x}")
                continue
            if addr in STOP_ADDRS or addr < CASE_CODE_START:
                reachers[addr].add(root)
                terminals[root].add(f"evaluator exit {addr:#010x}")
                continue
            seen.add(addr)
            insn = insns.setdefault(addr, decode_one(md, rom, addr))
            reachers[addr].add(root)
            succ, calls, terminal = successors(insn)
            calls_by_addr[addr].update(calls)
            if terminal:
                terminals[root].add(terminal)
            for target in succ:
                edges[addr].add(target)
                pending.append(target)

    rows = []
    for root, case_ids in sorted(entries.items()):
        owned = {
            addr for addr, roots in reachers.items()
            if roots == {root} and addr in insns
        }
        shared_exits = set()
        for addr in owned:
            for target in edges[addr]:
                if target in STOP_ADDRS or (
                    target in reachers and len(reachers[target]) > 1
                ):
                    shared_exits.add(target)
        rows.append({
            "root": root,
            "case_ids": case_ids,
            "owned": owned,
            "owned_bytes": sum(insns[a].size for a in owned),
            "ranges": contiguous_ranges(owned, insns),
            "shared_exits": sorted(shared_exits),
            "external_calls": sorted({
                call for addr in owned for call in calls_by_addr[addr]
            }),
            "terminals": sorted(terminals[root]),
            "shape": semantic_shape(owned, insns),
        })

    shared = {
        addr for addr, roots in reachers.items()
        if len(roots) > 1 and addr in insns
    }
    shared_groups = collections.defaultdict(set)
    for addr in shared:
        shared_groups[frozenset(reachers[addr])].add(addr)

    stop_reachers = {
        addr: roots for addr, roots in reachers.items() if addr in STOP_ADDRS
    }
    return entries, insns, reachers, rows, shared_groups, stop_reachers


def render(entries, insns, reachers, rows, shared_groups, stop_reachers):
    total_owned = sum(row["owned_bytes"] for row in rows)
    shared_bytes = sum(
        insns[a].size for a in reachers
        if len(reachers[a]) > 1 and a in insns
    )
    lines = [
        "# AI evaluator control-flow partitions",
        "",
        "Generated by `tools/partition_ai_evaluator.py`; do not hand-edit.",
        "",
        f"The 92 effect ids enter {len(entries)} distinct roots. Recursive Thumb flow",
        f"decodes {len(insns)} instructions: {total_owned} case-owned bytes and",
        f"{shared_bytes} shared bytes. Literal-pool and jump-table data are never",
        "misclassified as code because traversal begins only at executable roots.",
        "",
        "A case-owned range is safe to reconstruct as part of that rule. A shared",
        "join must be represented once in the surrounding evaluator C rather than",
        "copied into every case.",
        "",
        "## Case-owned blocks",
        "",
        "| Effect ids | Root | Owned bytes | Owned instruction ranges | Shared joins | External calls |",
        "|---|---:|---:|---|---|---|",
    ]
    for row in rows:
        ids = ",".join(str(x) for x in row["case_ids"])
        joins = ", ".join(f"`{x:#010x}`" for x in row["shared_exits"]) or "-"
        calls = ", ".join(f"`{x:#010x}`" for x in row["external_calls"]) or "-"
        lines.append(
            f"| {ids} | `{row['root']:#010x}` | {row['owned_bytes']} | "
            f"`{fmt_ranges(row['ranges'])}` | {joins} | {calls} |"
        )

    lines.extend([
        "",
        "## Shared joins",
        "",
        "| Reaching case roots | Bytes | Instruction ranges |",
        "|---:|---:|---|",
    ])
    groups = sorted(shared_groups.items(), key=lambda item: (min(item[1]), len(item[0])))
    for roots, addresses in groups:
        byte_count = sum(insns[a].size for a in addresses)
        lines.append(
            f"| {len(roots)} | {byte_count} | "
            f"`{fmt_ranges(contiguous_ranges(addresses, insns))}` |"
        )
    lines.extend([
        "",
        "## Evaluator exits",
        "",
        "These addresses terminate a rule partition. They are deliberately not",
        "walked because the reject-next path can redispatch the entire switch.",
        "",
        "| Address | Reaching case roots | Role |",
        "|---:|---:|---|",
    ])
    roles = {
        0x080C37B4: "accept current candidate",
        0x080C477A: "reject current candidate and try next",
        0x080C478C: "reject evaluation",
        0x080C478E: "return accepted",
    }
    for addr in sorted(stop_reachers):
        lines.append(
            f"| `{addr:#010x}` | {len(stop_reachers[addr])} | {roles[addr]} |"
        )
    probability_rows = [
        row for row in rows
        if 0x08002804 in row["external_calls"]
        and 0x08142950 in row["external_calls"]
        and row["owned_bytes"] in (70, 74)
    ]
    shapes = collections.defaultdict(list)
    for row in probability_rows:
        shapes[row["shape"]].append(row)
    dominant = max(shapes.values(), key=len)
    dominant_ids = [case_id for row in dominant for case_id in row["case_ids"]]
    lines.extend([
        "",
        "## Dominant probability/status family",
        "",
        f"One normalized instruction shape covers {len(dominant)} roots /",
        f"{len(dominant_ids)} effect ids: " + ", ".join(map(str, dominant_ids)) + ".",
        "Each chooses `Rand() % 101 <= 10` for self-targeting or `<= 49` for",
        "other-targeting, rejects on failure, calls one effect/status test, then",
        "accepts only when that test returns zero. Case ids 65-67 use the same",
        "probability gate but pass a second argument to their effect test.",
        "",
        "## Present-state cancellation family",
        "",
        "Case ids 13, 23, 25, 36, 47, and 57 share one normalized shape:",
        "call one state getter, then accept only when it returns exactly one.",
        "Case 64 reaches the same shared comparison with a different getter-call",
        "encoding. Together these seven roots are the inverse/present-state",
        "counterpart to the absent-state family.",
    ])
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("rom")
    parser.add_argument("--markdown")
    args = parser.parse_args(argv)

    rom = romlib.load(args.rom)
    result = analyze(rom)
    report = render(*result)
    if args.markdown:
        with open(args.markdown, "w", newline="\n") as f:
            f.write(report)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
