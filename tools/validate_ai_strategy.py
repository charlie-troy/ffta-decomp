"""Validate declarative auto-battle strategy profiles against the retail ROM.

    python tools/validate_ai_strategy.py baserom.gba
"""
import copy
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_table as ability
import ai_strategy
import ai_targeting
from emulate import Gba, STOP
from patch_ai_gates import find_gates
from unicorn import UC_HOOK_CODE


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = (
    ("aggressive.json", 409),
    ("deterministic-actions.json", 451),
)
JOB_PRIORITY_GETTER = 0x0813413C
UNIT = 0x02000400
# The tie-break window: entered with equal candidate scores, exits at the swap
# store block (0x080C2F94) or the keep-ordering continue (0x080C2FC4).
TIE_ENTRY = 0x08000000 + ai_targeting.PATCH_OFFSET
TIE_SWAP_EXIT = 0x080C2F94
TIE_KEEP_EXIT = 0x080C2FC4
RNG_STATE = 0x030034B0


def expect_error(label, fn):
    try:
        fn()
    except ai_strategy.ProfileError:
        return True
    print(f"   {label}: expected rejection")
    return False


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    with open(argv[0], "rb") as handle:
        rom = handle.read()

    built = {}
    print("1. shipped profile schema and deterministic diff counts")
    ok = True
    for filename, expected_diff in PROFILES:
        path = os.path.join(REPO, "configs", "ai-strategies", filename)
        profile = ai_strategy.load_profile(path)
        mod, report = ai_strategy.build_profile(rom, profile)
        actual = sum(a != b for a, b in zip(rom, mod))
        passed = actual == expected_diff == report["changed_bytes"] and len(mod) == len(rom)
        print(f"   {filename}: {actual} changed byte(s) -> {'PASS' if passed else 'FAIL'}")
        ok &= passed
        built[filename] = (profile, mod, report)

    print("2. all writes stay inside declared AI strategy surfaces")
    allowed = set()
    for index in range(ability.COUNT):
        base = ability.BASE + index * ability.STRIDE
        allowed.update(base + ai_strategy.ABILITY_FIELDS[field][0]
                       for field in ai_strategy.ABILITY_ACTION_FIELDS)
    allowed.update(ability.UNIT_BASE + index * ability.UNIT_STRIDE + ability.UNIT_PRIO
                   for index in range(ability.UNIT_COUNT))
    allowed.update(offset for offset, _value in find_gates(rom))
    allowed.update(range(ai_targeting.PATCH_OFFSET, ai_targeting.PATCH_END))
    surface_ok = True
    for filename, (_profile, mod, _report) in built.items():
        outside = [index for index, (a, b) in enumerate(zip(rom, mod))
                   if a != b and index not in allowed]
        print(f"   {filename}: {len(outside)} out-of-surface byte(s)")
        surface_ok &= not outside
    print(f"   -> {'PASS' if surface_ok else 'FAIL'}")
    ok &= surface_ok

    print("3. selector and ordered-override behavior")
    profile = copy.deepcopy(built["aggressive.json"][0])
    profile["name"] = "Selector probe"
    profile["status_gates"] = {"self": 10, "other": 49}
    profile["target_ordering"] = "retail"
    profile["ability_rules"] = [
        {"name": "Cure by exact name", "match": {"names": ["Cure"]},
         "set": {"ai_priority": 81}, "expect_matches": 1},
        {"name": "Cure override by id", "match": {"ids": [1]},
         "add": {"ai_priority": 9}, "expect_matches": 1},
    ]
    profile["job_rules"] = []
    probe, report = ai_strategy.build_profile(rom, profile)
    cure = ability.BASE + ability.STRIDE + ai_strategy.ABILITY_FIELDS["ai_priority"][0]
    selector_ok = probe[cure] == 90 and report["changed_bytes"] == 1
    print(f"   Cure priority {rom[cure]} -> {probe[cure]}; one final byte -> "
          f"{'PASS' if selector_ok else 'FAIL'}")
    ok &= selector_ok

    print("4. malformed, mismatched, and unsafe profiles fail closed")
    invalid = copy.deepcopy(profile)
    invalid["ability_rules"][0]["match"] = {"names": ["Not A Retail Ability"]}
    invalid["ability_rules"] = invalid["ability_rules"][:1]
    bad_hash = copy.deepcopy(profile)
    bad_hash["base_sha1"] = "0" * 40
    out_of_range = copy.deepcopy(profile)
    out_of_range["ability_rules"][0]["set"] = {"ai_priority": 101}
    failures_ok = (
        expect_error("unmatched selector", lambda: ai_strategy.build_profile(rom, invalid)) and
        expect_error("wrong input hash", lambda: ai_strategy.build_profile(rom, bad_hash)) and
        expect_error("out-of-range action", lambda: ai_strategy.build_profile(rom, out_of_range))
    )
    print(f"   -> {'PASS' if failures_ok else 'FAIL'}")
    ok &= failures_ok

    print("5. patched job priority is visible through the retail getter")
    deterministic = built["deterministic-actions.json"][1]
    with tempfile.TemporaryDirectory(prefix="ffta-ai-strategy-") as temp:
        path = os.path.join(temp, "strategy.gba")
        with open(path, "wb") as handle:
            handle.write(deterministic)
        gba = Gba(path)
        getter_ok = True
        checked = 0
        for index in range(ability.UNIT_COUNT):
            offset = ability.UNIT_BASE + index * ability.UNIT_STRIDE + ability.UNIT_PRIO
            if rom[offset] and rom[offset] != deterministic[offset]:
                gba.uc.mem_write(UNIT, bytes(0x40))
                gba.uc.mem_write(UNIT + 5, bytes([index]))
                getter_ok &= gba.call(JOB_PRIORITY_GETTER, [UNIT, 0]) == 100
                checked += 1
    print(f"   {checked} changed job priorities read back as 100 -> "
          f"{'PASS' if getter_ok else 'FAIL'}")
    ok &= getter_ok and checked == 87

    print("6. deterministic target tie-break, executed")
    aggressive = built["aggressive.json"][1]
    with tempfile.TemporaryDirectory(prefix="ffta-ai-strategy-") as temp:
        gbas = {}
        for label, data in (("retail", rom), ("profile", aggressive)):
            path = os.path.join(temp, f"{label}.gba")
            with open(path, "wb") as handle:
                handle.write(data)
            gbas[label] = Gba(path)

        def tie_outcome(g, seed):
            g.reset_ram()
            g.write32(RNG_STATE, seed)
            landed = []

            def hook(uc, address, size, _):
                if address in (TIE_SWAP_EXIT, TIE_KEEP_EXIT):
                    landed.append(address)
                    uc.emu_stop()

            h = g.uc.hook_add(UC_HOOK_CODE, hook,
                              begin=TIE_SWAP_EXIT, end=TIE_KEEP_EXIT)
            try:
                g.run_range(TIE_ENTRY, STOP, {"r5": 5, "r4": 0})
            finally:
                g.uc.hook_del(h)
            return landed[0] if landed else None, g.read32(RNG_STATE)

        seeds = range(1, 501)
        outcomes = {label: [tie_outcome(g, s) for s in seeds]
                    for label, g in gbas.items()}
        retail_swap = sum(exit == TIE_SWAP_EXIT
                          for exit, _state in outcomes["retail"])
        profile_swap = sum(exit == TIE_SWAP_EXIT
                           for exit, _state in outcomes["profile"])
        rng_untouched = [state == seed
                         for (exit, state), seed in zip(outcomes["profile"],
                                                        seeds)]
    tie_ok = 200 <= retail_swap <= 300 and profile_swap == 0 and all(rng_untouched)
    print(f"   retail tie roll: {retail_swap}/500 swaps (about half)")
    print(f"   patched ties: {profile_swap}/500 swaps; ties keep the earlier candidate")
    print(f"   patched window leaves the battle RNG untouched -> "
          f"{'PASS' if tie_ok else 'FAIL'}")
    ok &= tie_ok

    print()
    print("PASS: 6/6 AI strategy checks" if ok else "FAIL: AI strategy validation")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
