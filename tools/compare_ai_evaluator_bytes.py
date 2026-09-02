"""Compare the evaluator candidate with retail while masking relocations.

Run ``tools/report_ai_evaluator_candidate.sh`` first.  The candidate object is
relocatable, so external calls, global pointers, and internal jump-table words
cannot equal their linked retail encodings yet.  This tool masks exactly those
four-byte relocation sites and compares every remaining byte at the same
function-relative offset.  Size equality alone is not treated as a match.
"""

import argparse
import re
import subprocess

import partition_ai_evaluator as evaluator


RELOCATION = re.compile(
    r"^([0-9a-fA-F]{8})\s+.*\b(R_ARM_THM_CALL|R_ARM_ABS32)\b"
)


def relocation_offsets(obj_path):
    quoted = obj_path.replace("'", "'\\''")
    command = (
        "$HOME/ffta-toolchain/local/usr/bin/arm-none-eabi-readelf "
        f"-r '{quoted}'"
    )
    output = subprocess.check_output(["wsl", "bash", "-lc", command], text=True)
    offsets = set()
    for line in output.splitlines():
        match = RELOCATION.match(line)
        if match:
            offsets.update(range(int(match.group(1), 16),
                                 int(match.group(1), 16) + 4))
    return offsets


def symbol_size(obj_path):
    quoted = obj_path.replace("'", "'\\''")
    command = (
        "$HOME/ffta-toolchain/local/usr/bin/arm-none-eabi-nm -S "
        f"'{quoted}'"
    )
    output = subprocess.check_output(["wsl", "bash", "-lc", command], text=True)
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[3] == "AiEvaluateAbility":
            return int(fields[1], 16)
    raise ValueError("AiEvaluateAbility symbol size not found")


def mismatch_runs(candidate, retail, masked):
    mismatches = [
        offset for offset in range(min(len(candidate), len(retail)))
        if offset not in masked and candidate[offset] != retail[offset]
    ]
    runs = []
    for offset in mismatches:
        if not runs or offset > runs[-1][-1] + 1:
            runs.append([offset])
        else:
            runs[-1].append(offset)
    return mismatches, runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", nargs="?", default="baserom.gba")
    parser.add_argument("--bin", default="build/ai_eval_probe/sub_080C32C0.bin")
    parser.add_argument("--obj", default="build/ai_eval_probe/sub_080C32C0.o")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    rom = open(args.rom, "rb").read()
    candidate = open(args.bin, "rb").read()[:symbol_size(args.obj)]
    retail = rom[evaluator.FUNC_START - evaluator.BASE:
                 evaluator.FUNC_END - evaluator.BASE]
    masked = relocation_offsets(args.obj)
    compared = min(len(candidate), len(retail)) - sum(
        offset < min(len(candidate), len(retail)) for offset in masked
    )
    mismatches, runs = mismatch_runs(candidate, retail, masked)
    equal = compared - len(mismatches)

    print(f"size: candidate {len(candidate)} / retail {len(retail)} "
          f"({len(candidate) - len(retail):+d})")
    print(f"relocation-masked bytes: {len(masked)}")
    print(f"comparable bytes equal: {equal} / {compared} "
          f"({len(mismatches)} mismatch(es) in {len(runs)} run(s))")
    if len(candidate) != len(retail):
        print(f"unpaired trailing bytes: {abs(len(candidate) - len(retail))}")
    for run in runs[:args.limit]:
        start = run[0]
        end = run[-1] + 1
        print(f"  +{start:#06x}..+{end:#06x}: "
              f"candidate {candidate[start:end].hex(' ')} / "
              f"retail {retail[start:end].hex(' ')}")
    if len(runs) > args.limit:
        print(f"  ... {len(runs) - args.limit} more run(s)")


if __name__ == "__main__":
    main()
