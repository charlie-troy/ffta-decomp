"""Apply a declarative auto-battle strategy profile to an FFTA USA ROM.

Profiles can tune ability priorities/rule selectors, fallback job priorities,
and the evaluator's self/other status gates. Rules match the original input
state and run in file order, so later rules deliberately override earlier ones.

    python tools/ai_strategy.py validate configs/ai-strategies/aggressive.json
    python tools/ai_strategy.py preview  baserom.gba configs/ai-strategies/aggressive.json
    python tools/ai_strategy.py apply    baserom.gba configs/ai-strategies/aggressive.json out.gba
"""
import argparse
import hashlib
import json
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ability_table as ability
import ai_targeting
from ffta_names import Names
from patch_ai_gates import find_gates


SCHEMA_VERSION = 1
SUPPORTED_BASE_SHA1 = "4ac05441f4de70a4ec3dd932116346c61b8783d9"
ABILITY_FIELDS = {name: (offset, width) for name, offset, width in ability.COLUMNS}
ABILITY_ACTION_FIELDS = {"ai_condition", "ai_behaviour", "ai_priority"}
JOB_ACTION_FIELDS = {"ai_priority"}
FLAG_BITS = {name: bit for bit, name in ability.FLAG_BITS}
FLAG_BITS.update({name.removeprefix("f_"): bit for bit, name in ability.FLAG_BITS})


class ProfileError(ValueError):
    pass


def _only(mapping, allowed, where):
    unknown = set(mapping) - set(allowed)
    if unknown:
        raise ProfileError(f"{where}: unknown key(s): {', '.join(sorted(unknown))}")


def load_profile(path):
    with open(path, encoding="utf-8") as handle:
        profile = json.load(handle)
    validate_profile(profile)
    return profile


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ProfileError("profile must be a JSON object")
    _only(profile, {"schema_version", "name", "description", "base_sha1",
                    "status_gates", "target_ordering", "ability_rules", "job_rules"}, "profile")
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise ProfileError(f"schema_version must be {SCHEMA_VERSION}")
    for key in ("name", "description"):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            raise ProfileError(f"{key} must be a non-empty string")
    sha1 = profile.get("base_sha1")
    if not isinstance(sha1, str) or sha1.lower() != SUPPORTED_BASE_SHA1:
        raise ProfileError(f"base_sha1 must be the supported FFTA USA SHA1 {SUPPORTED_BASE_SHA1}")
    gates = profile.get("status_gates")
    if gates is not None:
        if not isinstance(gates, dict):
            raise ProfileError("status_gates must be an object")
        _only(gates, {"self", "other"}, "status_gates")
        if set(gates) != {"self", "other"}:
            raise ProfileError("status_gates must provide both self and other")
        for key, value in gates.items():
            if not isinstance(value, int) or not 0 <= value <= 100:
                raise ProfileError(f"status_gates.{key} must be an integer from 0 to 100")
    target_ordering = profile.get("target_ordering", "retail")
    if target_ordering not in ai_targeting.POLICIES:
        raise ProfileError("target_ordering must be retail or deterministic_ties")
    _validate_rules(profile.get("ability_rules", []), "ability")
    _validate_rules(profile.get("job_rules", []), "job")
    if (gates is None and target_ordering == "retail" and
            not profile.get("ability_rules") and not profile.get("job_rules")):
        raise ProfileError("profile must define at least one strategy control")
    return profile


def _validate_condition(condition, where):
    if isinstance(condition, bool):
        raise ProfileError(f"{where} must be numeric")
    if isinstance(condition, (int, float)):
        return
    if isinstance(condition, list):
        if not condition or any(isinstance(value, bool) or not isinstance(value, (int, float))
                                for value in condition):
            raise ProfileError(f"{where} must be a non-empty numeric array")
        return
    if not isinstance(condition, dict):
        raise ProfileError(f"{where} must be numeric, an array, or a condition object")
    _only(condition, {"eq", "ne", "in", "not_in", "min", "max"}, where)
    if not condition:
        raise ProfileError(f"{where} condition cannot be empty")
    for key, value in condition.items():
        values = value if key in ("in", "not_in") else [value]
        if key in ("in", "not_in") and not isinstance(value, list):
            raise ProfileError(f"{where}.{key} must be an array")
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in values):
            raise ProfileError(f"{where}.{key} must contain only numbers")


def _validate_rules(rules, kind):
    if not isinstance(rules, list):
        raise ProfileError(f"{kind}_rules must be an array")
    allowed_match = ({"ids", "names", "name_contains", "fields", "flags_all",
                      "flags_any", "flags_none"} if kind == "ability" else
                     {"indices", "names", "name_contains", "fields"})
    allowed_actions = ABILITY_ACTION_FIELDS if kind == "ability" else JOB_ACTION_FIELDS
    for index, rule in enumerate(rules):
        where = f"{kind}_rules[{index}]"
        if not isinstance(rule, dict):
            raise ProfileError(f"{where} must be an object")
        _only(rule, {"name", "match", "set", "add", "multiply", "expect_matches"}, where)
        if not isinstance(rule.get("name"), str) or not rule["name"].strip():
            raise ProfileError(f"{where}.name must be a non-empty string")
        match = rule.get("match", {})
        if not isinstance(match, dict):
            raise ProfileError(f"{where}.match must be an object")
        _only(match, allowed_match, f"{where}.match")
        for list_key in ("ids", "indices", "names", "name_contains",
                         "flags_all", "flags_any", "flags_none"):
            if list_key in match and not isinstance(match[list_key], list):
                raise ProfileError(f"{where}.match.{list_key} must be an array")
        id_key = "ids" if kind == "ability" else "indices"
        if id_key in match:
            limit = ability.COUNT if kind == "ability" else ability.UNIT_COUNT
            if any(isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < limit
                   for value in match[id_key]):
                raise ProfileError(f"{where}.match.{id_key} contains an out-of-range id")
        for text_key in ("names", "name_contains"):
            if text_key in match and (not match[text_key] or
                                      any(not isinstance(value, str) or not value
                                          for value in match[text_key])):
                raise ProfileError(f"{where}.match.{text_key} must contain non-empty strings")
        fields = match.get("fields", {})
        if not isinstance(fields, dict):
            raise ProfileError(f"{where}.match.fields must be an object")
        known_fields = set(ABILITY_FIELDS) if kind == "ability" else {"ai_priority"}
        _only(fields, known_fields, f"{where}.match.fields")
        for field, condition in fields.items():
            _validate_condition(condition, f"{where}.match.fields.{field}")
        if kind == "ability":
            for flag_key in ("flags_all", "flags_any", "flags_none"):
                for flag in match.get(flag_key, []):
                    if not isinstance(flag, str):
                        raise ProfileError(f"{where}.match.{flag_key} flags must be strings")
                    if flag not in FLAG_BITS:
                        raise ProfileError(f"{where}.match.{flag_key}: unknown flag {flag!r}")
        touched = set()
        for action in ("set", "add", "multiply"):
            values = rule.get(action, {})
            if not isinstance(values, dict):
                raise ProfileError(f"{where}.{action} must be an object")
            _only(values, allowed_actions, f"{where}.{action}")
            overlap = touched & set(values)
            if overlap:
                raise ProfileError(f"{where}: field appears in multiple actions: {sorted(overlap)[0]}")
            touched.update(values)
            for field, value in values.items():
                if action == "multiply":
                    valid = (isinstance(value, (int, float)) and not isinstance(value, bool)
                             and math.isfinite(value) and value >= 0)
                else:
                    valid = isinstance(value, int) and not isinstance(value, bool)
                if not valid:
                    raise ProfileError(f"{where}.{action}.{field} has an invalid value")
                if action == "set":
                    limits = ({"ai_condition": (0, 255), "ai_behaviour": (0, 3),
                               "ai_priority": (0, 100)} if kind == "ability" else
                              {"ai_priority": (0, 100)})
                    low, high = limits[field]
                    if not low <= value <= high:
                        raise ProfileError(f"{where}.set.{field} must be in {low}..{high}")
        if not touched:
            raise ProfileError(f"{where} must define at least one action")
        expected = rule.get("expect_matches")
        if expected is not None and (not isinstance(expected, int) or expected < 0):
            raise ProfileError(f"{where}.expect_matches must be a nonnegative integer")


def _condition_matches(value, condition):
    if isinstance(condition, list):
        return value in condition
    if not isinstance(condition, dict):
        return value == condition
    _only(condition, {"eq", "ne", "in", "not_in", "min", "max"}, "field condition")
    return (("eq" not in condition or value == condition["eq"]) and
            ("ne" not in condition or value != condition["ne"]) and
            ("in" not in condition or value in condition["in"]) and
            ("not_in" not in condition or value not in condition["not_in"]) and
            ("min" not in condition or value >= condition["min"]) and
            ("max" not in condition or value <= condition["max"]))


def _ability_value(rom, index, field):
    offset, width = ABILITY_FIELDS[field]
    start = ability.BASE + index * ability.STRIDE + offset
    return int.from_bytes(rom[start:start + width], "little")


def _matches_common(index, name, match, id_key):
    if id_key in match and index not in match[id_key]:
        return False
    lowered = name.casefold()
    if "names" in match and lowered not in {value.casefold() for value in match["names"]}:
        return False
    if "name_contains" in match and not any(value.casefold() in lowered for value in match["name_contains"]):
        return False
    return True


def _ability_matches(rom, index, name, match):
    if not _matches_common(index, name, match, "ids"):
        return False
    for field, condition in match.get("fields", {}).items():
        if not _condition_matches(_ability_value(rom, index, field), condition):
            return False
    base = ability.BASE + index * ability.STRIDE
    flags = int.from_bytes(rom[base + 0x10:base + 0x14], "little")
    selected = lambda key: [FLAG_BITS[flag] for flag in match.get(key, [])]
    if any(not (flags >> bit) & 1 for bit in selected("flags_all")):
        return False
    if selected("flags_any") and not any((flags >> bit) & 1 for bit in selected("flags_any")):
        return False
    if any((flags >> bit) & 1 for bit in selected("flags_none")):
        return False
    return True


def _job_matches(rom, index, name, match):
    if not _matches_common(index, name, match, "indices"):
        return False
    fields = match.get("fields", {})
    priority = rom[ability.UNIT_BASE + index * ability.UNIT_STRIDE + ability.UNIT_PRIO]
    return all(_condition_matches(priority, condition)
               for field, condition in fields.items() if field == "ai_priority")


def _new_value(rule, field, old, limits):
    if field in rule.get("set", {}):
        value = rule["set"][field]
    elif field in rule.get("add", {}):
        value = old + rule["add"][field]
    else:
        value = int(old * rule["multiply"][field] + 0.5)
    low, high = limits[field]
    if not low <= value <= high:
        raise ProfileError(f"rule {rule['name']!r} makes {field}={value}, outside {low}..{high}")
    return value


def _apply_rule_set(original, output, rules, kind, names):
    count = ability.COUNT if kind == "ability" else ability.UNIT_COUNT
    matcher = _ability_matches if kind == "ability" else _job_matches
    offsets = ({field: ABILITY_FIELDS[field][0] for field in ABILITY_ACTION_FIELDS}
               if kind == "ability" else {"ai_priority": ability.UNIT_PRIO})
    limits = ({"ai_condition": (0, 255), "ai_behaviour": (0, 3), "ai_priority": (0, 100)}
              if kind == "ability" else {"ai_priority": (0, 100)})
    stride = ability.STRIDE if kind == "ability" else ability.UNIT_STRIDE
    base = ability.BASE if kind == "ability" else ability.UNIT_BASE
    report = []
    for rule in rules:
        matched = [index for index in range(count)
                   if matcher(original, index, names[index], rule.get("match", {}))]
        expected = rule.get("expect_matches")
        if expected is not None and len(matched) != expected:
            raise ProfileError(f"rule {rule['name']!r} expected {expected} matches, found {len(matched)}")
        if expected is None and not matched:
            raise ProfileError(f"rule {rule['name']!r} matched nothing")
        changed = 0
        action_fields = set(rule.get("set", {})) | set(rule.get("add", {})) | set(rule.get("multiply", {}))
        for index in matched:
            for field in sorted(action_fields):
                offset = base + index * stride + offsets[field]
                old = output[offset]
                new = _new_value(rule, field, old, limits)
                if new != old:
                    output[offset] = new
                    changed += 1
        report.append({"name": rule["name"], "matched": len(matched), "updates": changed})
    return report


def build_profile(rom, profile):
    validate_profile(profile)
    actual_sha1 = hashlib.sha1(rom).hexdigest()
    if actual_sha1.lower() != profile["base_sha1"].lower():
        raise ProfileError(f"input SHA1 {actual_sha1} does not match profile base_sha1 {profile['base_sha1']}")
    if len(rom) != 0x1000000:
        raise ProfileError(f"input ROM is {len(rom)} bytes; expected 16,777,216")

    original = bytes(rom)
    output = bytearray(rom)
    names = Names(original)
    ability_names = [names.ability(index) for index in range(ability.COUNT)]
    job_names = [names.job(index) for index in range(ability.UNIT_COUNT)]
    ability_report = _apply_rule_set(original, output, profile.get("ability_rules", []),
                                     "ability", ability_names)
    job_report = _apply_rule_set(original, output, profile.get("job_rules", []),
                                 "job", job_names)

    gate_report = None
    if "status_gates" in profile:
        gates = find_gates(original)
        values = sorted({value for _offset, value in gates})
        if len(gates) != 85 or len(values) != 2:
            raise ProfileError(f"expected 85 status gates with two thresholds; found {len(gates)} / {values}")
        mapping = {values[0]: profile["status_gates"]["self"],
                   values[1]: profile["status_gates"]["other"]}
        updates = 0
        for offset, old in gates:
            new = mapping[old]
            if output[offset] != new:
                output[offset] = new
                updates += 1
        gate_report = {"old": values, "new": [mapping[value] for value in values],
                       "matched": len(gates), "updates": updates}

    target_policy = profile.get("target_ordering", "retail")
    try:
        target_updates = ai_targeting.apply_policy(output, target_policy)
    except ValueError as error:
        raise ProfileError(str(error)) from error

    changed = [index for index, (old, new) in enumerate(zip(original, output)) if old != new]
    return bytes(output), {"ability_rules": ability_report, "job_rules": job_report,
                           "status_gates": gate_report,
                           "target_ordering": {"policy": target_policy,
                                               "updates": target_updates},
                           "changed_bytes": len(changed)}


def print_report(profile, report):
    print(f"strategy: {profile['name']}")
    print(profile["description"])
    for kind in ("ability_rules", "job_rules"):
        if report[kind]:
            print(f"{kind.replace('_', ' ')}:")
            for row in report[kind]:
                print(f"  {row['name']}: {row['matched']} matched, {row['updates']} update(s)")
    gates = report["status_gates"]
    if gates:
        print(f"status gates: self {gates['old'][0]} -> {gates['new'][0]}, "
              f"other {gates['old'][1]} -> {gates['new'][1]} "
              f"({gates['updates']} update(s))")
    targeting = report["target_ordering"]
    print(f"target ordering: {targeting['policy']} ({targeting['updates']} update(s))")
    print(f"final changed bytes: {report['changed_bytes']}")


def write_atomic(path, data):
    """Write a completed ROM via a same-directory temporary and replace."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".ffta-strategy-", suffix=".tmp",
                                     dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate profile structure without a ROM")
    validate.add_argument("profile")
    for command in ("preview", "apply"):
        child = sub.add_parser(command, help=f"{command} a profile")
        child.add_argument("rom")
        child.add_argument("profile")
        if command == "apply":
            child.add_argument("output")
            child.add_argument("--force", action="store_true",
                               help="replace an existing output file")
    args = parser.parse_args(argv)
    try:
        profile = load_profile(args.profile)
        if args.command == "validate":
            print(f"profile {profile['name']!r}: valid schema v{SCHEMA_VERSION}")
            return 0
        with open(args.rom, "rb") as handle:
            rom = handle.read()
        output, report = build_profile(rom, profile)
        print_report(profile, report)
        if args.command == "apply":
            source = os.path.realpath(args.rom)
            destination = os.path.realpath(args.output)
            if source == destination:
                raise ProfileError("output must not overwrite the input ROM")
            if os.path.exists(destination) and not args.force:
                raise ProfileError("output already exists; pass --force to replace it")
            write_atomic(args.output, output)
            print(f"wrote {args.output}")
        else:
            print("preview only; no output written")
        return 0
    except (OSError, json.JSONDecodeError, ProfileError) as error:
        print(f"error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
