"""Compare agbcc evaluator case-root ownership with the retail CFG partition.

Run ``tools/report_ai_evaluator_candidate.sh`` first so the candidate object and
binary exist. This reads internal jump-table relocations from that relocatable
object, treats unresolved BL relocations as returning external calls, and ranks
the 66 roots by owned-byte delta.
"""

import argparse
import collections
import re
import subprocess

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

import partition_ai_evaluator as retail


CASE_COUNT = 92


def direct_target(insn):
    text = insn.op_str.strip()
    return int(text[1:], 0) if text.startswith("#") else None


def external_call_offsets(obj_path):
    command = (
        "$HOME/ffta-toolchain/local/usr/bin/arm-none-eabi-readelf "
        f"-r '{obj_path.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"
    )
    output = subprocess.check_output(
        ["wsl", "bash", "-lc", command], text=True
    )
    offsets = set()
    for line in output.splitlines():
        match = re.match(r"^([0-9a-fA-F]{8})\s+.*R_ARM_THM_CALL", line)
        if match:
            offsets.add(int(match.group(1), 16))
    return offsets


def find_case_table(data):
    for offset in range(0, len(data) - CASE_COUNT * 4 + 1, 4):
        values = [
            int.from_bytes(data[offset + i * 4:offset + i * 4 + 4], "little") & ~1
            for i in range(CASE_COUNT)
        ]
        if (60 <= len(set(values)) <= 66 and
                all(offset + CASE_COUNT * 4 <= value < len(data) for value in values)):
            return offset, values
    raise ValueError("could not locate the 92-entry / 66-root candidate table")


def successors(insn, size, external_calls):
    next_addr = insn.address + insn.size
    mnemonic = insn.mnemonic
    target = direct_target(insn)
    if mnemonic == "bl":
        if insn.address in external_calls:
            return [next_addr]
        return [target] if target is not None and 0 <= target < size else []
    if mnemonic == "b":
        return [target] if target is not None else []
    if mnemonic.startswith("b") and mnemonic not in ("bic", "bics", "bx"):
        return [next_addr, target] if target is not None else [next_addr]
    if mnemonic == "bx" or (mnemonic == "mov" and insn.op_str.startswith("pc,")):
        return []
    if mnemonic == "pop" and "pc" in insn.op_str:
        return []
    return [next_addr]


def candidate_rows(data, roots, external_calls):
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    entries = collections.defaultdict(list)
    for case_id, root in enumerate(roots, 1):
        entries[root].append(case_id)

    insns = {}
    reachers = collections.defaultdict(set)
    for root in entries:
        pending = [root]
        seen = set()
        while pending:
            address = pending.pop()
            if address in seen or not (0 <= address < len(data)):
                continue
            seen.add(address)
            decoded = list(md.disasm(data[address:address + 4], address, count=1))
            if not decoded:
                raise ValueError(f"cannot decode candidate instruction at {address:#x}")
            insn = decoded[0]
            insns[address] = insn
            reachers[address].add(root)
            pending.extend(successors(insn, len(data), external_calls))

    rows = {}
    for root, case_ids in entries.items():
        owned = {
            address for address, owners in reachers.items()
            if owners == {root} and address in insns
        }
        rows[tuple(case_ids)] = sum(insns[address].size for address in owned)
    shared = sum(
        insns[address].size for address, owners in reachers.items()
        if len(owners) > 1 and address in insns
    )
    return rows, shared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", nargs="?", default="baserom.gba")
    parser.add_argument("--bin", default="build/ai_eval_probe/ai_ability_eval.bin")
    parser.add_argument("--obj", default="build/ai_eval_probe/ai_ability_eval.o")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    rom = open(args.rom, "rb").read()
    candidate = open(args.bin, "rb").read()
    table_offset, roots = find_case_table(candidate)
    candidate_by_ids, candidate_shared = candidate_rows(
        candidate, roots, external_call_offsets(args.obj)
    )
    _, _, _, retail_rows, _, _ = retail.analyze(rom)

    comparisons = []
    retail_by_ids = {tuple(row["case_ids"]): row for row in retail_rows}
    candidate_groups = set(candidate_by_ids)
    retail_groups = set(retail_by_ids)
    if candidate_groups != retail_groups:
        print("root grouping differences:")
        for ids in sorted(candidate_groups - retail_groups):
            print("  candidate merged: " + ",".join(str(value) for value in ids))
        for ids in sorted(retail_groups - candidate_groups):
            print("  retail separate:  " + ",".join(str(value) for value in ids))

    for row in retail_rows:
        ids = tuple(row["case_ids"])
        if ids not in candidate_by_ids:
            continue
        candidate_bytes = candidate_by_ids[ids]
        comparisons.append((candidate_bytes - row["owned_bytes"], ids,
                            row["owned_bytes"], candidate_bytes))

    comparisons.sort(key=lambda item: (-abs(item[0]), item[1]))
    print(f"candidate table: {table_offset:#x}; {len(set(roots))} roots")
    candidate_owned_total = sum(candidate_by_ids.values())
    retail_owned_total = sum(row["owned_bytes"] for row in retail_rows)
    print(f"owned CFG bytes: candidate {candidate_owned_total} / retail "
          f"{retail_owned_total} ({candidate_owned_total - retail_owned_total:+d})")
    print(f"candidate shared CFG bytes: {candidate_shared}")
    print("largest owned-byte deltas (candidate - retail):")
    for delta, ids, retail_bytes, candidate_bytes in comparisons[:args.limit]:
        label = ",".join(str(value) for value in ids)
        print(f"  {label:>23}: {candidate_bytes:4} - {retail_bytes:4} = {delta:+4}")
    print(f"sum of 66 owned deltas: {sum(item[0] for item in comparisons):+d}")


if __name__ == "__main__":
    main()
