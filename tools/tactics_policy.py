"""A5.2 frozen tactics-policy contract (pure, host-only).

The companion architecture keeps policy evaluation separate from emulator
transport. This module owns only the pure half: it validates a policy
document and a per-turn observation snapshot, and picks one of the
*engine-legal candidates the adapter supplies*. It never reads memory,
never presses keys, never writes game state and knows nothing about the
GBA, so it is fully testable on the host (tools/validate_tactics_policy.py).

Frozen interface (A5.2, do not change without a schema bump)::

    choose_action(snapshot, policy) -> dict | None

``None`` is the documented no-match path (fallback disabled, or no legal
Wait candidate exists). ``evaluate(snapshot, policy)`` returns the same
decision plus the outcome/reason, for receipts and logs.

Contract rules this module enforces:

- Assignment precedence is character -> job -> party, first match wins.
  A matched scope governs; its rules are tried in order and the first rule
  that selects wins. A matched scope does **not** fall through to a lower
  scope -- that is what the scope's explicit fallback is for.
- Engine legality always wins over policy preference: a candidate is only
  selectable when the adapter marked it legal, and a snapshot whose actor
  identity is not verified can never commit.
- Missing facts make a predicate (and therefore a rule) ineligible; they
  never default to a permissive value.
- Selection ties break on the candidate id, so the same snapshot always
  produces the same decision regardless of adapter ordering.

Schema: docs/tactics-policy.md. Evidence for the status vocabulary:
docs/unit-flags.md ("Named status flags", live +0xe8..+0xed block).
"""
from __future__ import annotations

import json

# -- schema versions -------------------------------------------------------
SCHEMA = "ffta-tactics-policy/1"
SNAPSHOT_SCHEMA = "ffta-tactics-snapshot/1"

# -- frozen vocabularies ---------------------------------------------------
RELATIONS = ("self", "ally", "enemy")
KINDS = ("move", "wait", "ability")
SIDES = ("player", "enemy")
FALLBACKS = ("wait", "none")
SELECTORS = ("first", "lowest-target-hp", "highest-target-hp",
             "lowest-remaining-mp", "highest-remaining-mp")
COMPARISONS = ("lt", "lte", "gt", "gte", "eq")
SCOPE_KEYS = ("characters", "jobs", "party")
DEFAULT_MAX_AGE_SECONDS = 3.0
MAX_HP_PERCENT = 100
MAX_UNIT_ID = 254

# -- frozen outcome / reason vocabulary ------------------------------------
OUTCOME_SELECTED = "selected"
OUTCOME_FALLBACK = "fallback"
OUTCOME_NONE = "none"

REASON_MATCHED = "rule:matched"
REASON_FALLBACK_WAIT = "fallback:wait"
REASON_NO_RULE_MATCH = "no-rule-match"
REASON_NO_LEGAL_CANDIDATE = "no-legal-candidate"
REASON_IDENTITY_UNVERIFIED = "actor-identity-unverified"
REASON_SNAPSHOT_STALE = "snapshot-stale"
REASON_SNAPSHOT_INVALID = "snapshot-invalid"

# -- frozen status vocabulary ---------------------------------------------
# name -> (struct byte, bit mask) in the live status block. Every name is
# backed by an application handler join in docs/unit-flags.md. Keys in the
# snapshot are the same byte strings ("0xe8"..."0xed").
STATUS_BITS = {
    # +0xe8
    "Quicken": (0xE8, 0x02),
    "Auto-Life": (0xE8, 0x04),
    "Regen": (0xE8, 0x08),
    "Astra": (0xE8, 0x10),
    "Reflect": (0xE8, 0x20),
    "Petrify": (0xE8, 0x40),
    "Berserk": (0xE8, 0x80),
    # +0xe9
    "Frog": (0xE9, 0x01),
    "Poison": (0xE9, 0x02),
    "Blind": (0xE9, 0x04),
    "Zombie": (0xE9, 0x08),
    "Conceal": (0xE9, 0x10),
    "Boost": (0xE9, 0x20),
    "Defending": (0xE9, 0x40),
    "Hibernate": (0xE9, 0x80),
    # +0xea
    "Advice": (0xEA, 0x01),
    "Mow Down Speed Down": (0xEA, 0x02),
    "Morphed": (0xEA, 0x04),
    "Cover": (0xEA, 0x08),
    "Doom": (0xEA, 0x10),
    "Haste": (0xEA, 0x20),
    "Slow": (0xEA, 0x40),
    "Stop": (0xEA, 0x80),
    # +0xeb
    "Shell": (0xEB, 0x01),
    "Protect": (0xEB, 0x02),
    "Sleep": (0xEB, 0x04),
    "Silence": (0xEB, 0x08),
    "Confuse": (0xEB, 0x10),
    "Charm": (0xEB, 0x20),
    "Immobilize": (0xEB, 0x40),
    "Disable": (0xEB, 0x80),
    # +0xec
    "Addle": (0xEC, 0x01),
    "Expert Guard": (0xEC, 0x02),
    "Speed Down": (0xEC, 0x04),
    "Attack Up": (0xEC, 0x08),
    "Magic Up": (0xEC, 0x10),
    "Attack Down": (0xEC, 0x20),
    "Defense Up": (0xEC, 0x40),
    "Magic Down": (0xEC, 0x80),
    # +0xed
    "Resistance Up": (0xED, 0x01),
    "Resistance Down": (0xED, 0x02),
    "Defense Down": (0xED, 0x04),
    "Controlled": (0xED, 0x08),
    "Petrify Critical": (0xED, 0x10),
}
STATUS_BYTES = tuple(sorted({byte for byte, _ in STATUS_BITS.values()}))
_STATUS_KEYS = {"0x%02x" % byte for byte in STATUS_BYTES}

# -- frozen key sets (unknown keys are rejected) ---------------------------
POLICY_KEYS = ("schema", "assignments", "fallback", "observation", "note")
RULESET_KEYS = ("rules", "fallback", "note")
RULE_KEYS = ("id", "enabled", "when", "select", "note")
WHEN_KEYS = ("relation", "kind", "action_id", "ability_name",
             "actor_hp_pct", "target_hp_pct", "remaining_mp_after_cost",
             "actor_status_present", "actor_status_absent",
             "target_status_present", "target_status_absent")
SNAPSHOT_KEYS = ("schema", "identity", "actor", "candidates",
                 "age_seconds", "observed_at", "note")
ACTOR_KEYS = ("name", "id", "job_id", "side", "hp", "max_hp", "mp",
              "max_mp", "ct", "tile", "status_bytes", "note")
CANDIDATE_KEYS = ("id", "kind", "action_id", "legal", "cost", "relation",
                  "target", "target_hp", "target_max_hp", "target_mp",
                  "target_status_bytes", "ability_name", "note")


class PolicyError(ValueError):
    """A policy document violates the frozen schema."""


class SnapshotError(ValueError):
    """A snapshot violates the frozen schema (no commit is allowed)."""


# ---------------------------------------------------------------------------
# policy validation
# ---------------------------------------------------------------------------
def _unknown(obj, allowed, where, error):
    extra = sorted(set(obj) - set(allowed))
    if extra:
        raise error(f"{where}: unknown key(s) {extra}")


def _is_int(value):
    return type(value) is int and not isinstance(value, bool)


def _nonneg_int(value, where, error, maximum=None):
    if not _is_int(value) or value < 0 or (maximum is not None and value > maximum):
        raise error(f"{where}: expected an integer in 0..{maximum if maximum is not None else 'inf'}, got {value!r}")
    return value


def _unit_id(value, where, error):
    return _nonneg_int(value, where, error, maximum=MAX_UNIT_ID)


def _char_key(key):
    """'Marche#7' -> ('Marche', 7); raises ValueError when malformed."""
    if not isinstance(key, str) or key.count("#") != 1:
        raise ValueError("character key must be '<name>#<id>'")
    name, _, raw = key.partition("#")
    if not name or "#" in name:
        raise ValueError("character key must have a non-empty name")
    if not raw.isdigit() or (len(raw) > 1 and raw[0] == "0"):
        raise ValueError("character key id must be canonical decimal 0..254")
    return name, int(raw)


def _job_key(key):
    if not isinstance(key, str) or not key.isdigit():
        raise ValueError("job key must be a canonical decimal job id")
    if len(key) > 1 and key[0] == "0":
        raise ValueError("job key must be canonical decimal (no leading zeros)")
    return int(key)


def _comparison(value, where, maximum=None):
    if not isinstance(value, dict):
        raise PolicyError(f"{where}: expected a comparison object like {{\"lte\": 25}}")
    _unknown(value, COMPARISONS, where, PolicyError)
    if len(value) != 1:
        raise PolicyError(f"{where}: exactly one operator of {COMPARISONS} is required")
    ((op, operand),) = value.items()
    _nonneg_int(operand, f"{where}.{op}", PolicyError, maximum=maximum)
    return {op: operand}


def _status_list(value, where):
    if not isinstance(value, list) or not value:
        raise PolicyError(f"{where}: expected a non-empty list of status names")
    for name in value:
        if name not in STATUS_BITS:
            raise PolicyError(f"{where}: unknown status name {name!r} "
                              f"(frozen vocabulary in docs/tactics-policy.md)")
    if len(set(value)) != len(value):
        raise PolicyError(f"{where}: duplicate status name")
    return list(value)


def _rule(value, where, seen_ids):
    if not isinstance(value, dict):
        raise PolicyError(f"{where}: rule must be an object")
    _unknown(value, RULE_KEYS, where, PolicyError)
    rule_id = value.get("id")
    if not isinstance(rule_id, str) or not rule_id:
        raise PolicyError(f"{where}.id: non-empty string required")
    if rule_id in seen_ids:
        raise PolicyError(f"{where}.id: duplicate rule id {rule_id!r}")
    seen_ids.add(rule_id)
    enabled = value.get("enabled", True)
    if type(enabled) is not bool:
        raise PolicyError(f"{where}.enabled: boolean required")
    if "note" in value and not isinstance(value["note"], str):
        raise PolicyError(f"{where}.note: string required")
    selector = value.get("select")
    if selector not in SELECTORS:
        raise PolicyError(f"{where}.select: one of {SELECTORS} required")
    when = value.get("when", {})
    if not isinstance(when, dict):
        raise PolicyError(f"{where}.when: object required")
    _unknown(when, WHEN_KEYS, f"{where}.when", PolicyError)
    out = {"id": rule_id, "enabled": enabled, "select": selector, "when": {}}
    for key, operand in when.items():
        sub = f"{where}.when.{key}"
        if key == "relation":
            if operand not in RELATIONS:
                raise PolicyError(f"{sub}: one of {RELATIONS} required")
        elif key == "kind":
            if operand not in KINDS:
                raise PolicyError(f"{sub}: one of {KINDS} required")
        elif key == "action_id":
            _nonneg_int(operand, sub, PolicyError)
        elif key == "ability_name":
            if not isinstance(operand, str) or not operand:
                raise PolicyError(f"{sub}: non-empty string required")
        elif key in ("actor_hp_pct", "target_hp_pct"):
            operand = _comparison(operand, sub, maximum=MAX_HP_PERCENT)
        elif key == "remaining_mp_after_cost":
            operand = _comparison(operand, sub)
        else:  # status lists
            operand = _status_list(operand, sub)
        out["when"][key] = operand
    if "note" in value:
        out["note"] = value["note"]
    return out


def _ruleset(value, where):
    if not isinstance(value, dict):
        raise PolicyError(f"{where}: rule set must be an object")
    _unknown(value, RULESET_KEYS, where, PolicyError)
    rules = value.get("rules", [])
    if not isinstance(rules, list):
        raise PolicyError(f"{where}.rules: list required")
    seen = set()
    parsed = [_rule(rule, f"{where}.rules[{i}]", seen) for i, rule in enumerate(rules)]
    out = {"rules": parsed}
    if "fallback" in value:
        if value["fallback"] not in FALLBACKS:
            raise PolicyError(f"{where}.fallback: one of {FALLBACKS} required")
        out["fallback"] = value["fallback"]
    if "note" in value:
        if not isinstance(value["note"], str):
            raise PolicyError(f"{where}.note: string required")
        out["note"] = value["note"]
    return out


def validate_policy(policy):
    """Validate and normalize a policy document; returns the normalized copy."""
    if not isinstance(policy, dict):
        raise PolicyError("policy: object required")
    _unknown(policy, POLICY_KEYS, "policy", PolicyError)
    if policy.get("schema") != SCHEMA:
        raise PolicyError(f"policy.schema: must be {SCHEMA!r}")
    fallback = policy.get("fallback", "wait")
    if fallback not in FALLBACKS:
        raise PolicyError(f"policy.fallback: one of {FALLBACKS} required")
    observation = policy.get("observation", {})
    if not isinstance(observation, dict):
        raise PolicyError("policy.observation: object required")
    _unknown(observation, ("max_age_seconds",), "policy.observation", PolicyError)
    max_age = observation.get("max_age_seconds", DEFAULT_MAX_AGE_SECONDS)
    if isinstance(max_age, bool) or not isinstance(max_age, (int, float)) or max_age < 0:
        raise PolicyError("policy.observation.max_age_seconds: non-negative number required")
    assignments = policy.get("assignments", {})
    if not isinstance(assignments, dict):
        raise PolicyError("policy.assignments: object required")
    _unknown(assignments, SCOPE_KEYS, "policy.assignments", PolicyError)
    parsed_assignments = {}
    if "characters" in assignments:
        chars = assignments["characters"]
        if not isinstance(chars, dict):
            raise PolicyError("policy.assignments.characters: object required")
        out = {}
        for key, value in chars.items():
            try:
                name, unit_id = _char_key(key)
            except ValueError as exc:
                raise PolicyError(f"policy.assignments.characters[{key!r}]: {exc}")
            if unit_id > MAX_UNIT_ID:
                raise PolicyError(f"policy.assignments.characters[{key!r}]: id must be 0..254")
            if name + "#" + str(unit_id) != key:
                raise PolicyError(f"policy.assignments.characters[{key!r}]: non-canonical id")
            out[key] = _ruleset(value, f"policy.assignments.characters[{key!r}]")
        parsed_assignments["characters"] = out
    if "jobs" in assignments:
        jobs = assignments["jobs"]
        if not isinstance(jobs, dict):
            raise PolicyError("policy.assignments.jobs: object required")
        out = {}
        for key, value in jobs.items():
            try:
                _job_key(key)
            except ValueError as exc:
                raise PolicyError(f"policy.assignments.jobs[{key!r}]: {exc}")
            out[key] = _ruleset(value, f"policy.assignments.jobs[{key!r}]")
        parsed_assignments["jobs"] = out
    if "party" in assignments:
        party = assignments["party"]
        if not isinstance(party, dict):
            raise PolicyError("policy.assignments.party: object required")
        out = {}
        for key, value in party.items():
            if key not in SIDES:
                raise PolicyError(f"policy.assignments.party[{key!r}]: one of {SIDES} required")
            out[key] = _ruleset(value, f"policy.assignments.party[{key!r}]")
        parsed_assignments["party"] = out
    if "note" in policy and not isinstance(policy["note"], str):
        raise PolicyError("policy.note: string required")
    normalized = {"schema": SCHEMA, "fallback": fallback,
                  "observation": {"max_age_seconds": float(max_age)},
                  "assignments": parsed_assignments}
    if "note" in policy:
        normalized["note"] = policy["note"]
    return normalized


def load_policy_file(path):
    """Read + validate a policy JSON file (raises PolicyError/OSError)."""
    with open(path, encoding="utf-8") as fh:
        return validate_policy(json.load(fh))


# ---------------------------------------------------------------------------
# snapshot validation
# ---------------------------------------------------------------------------
def _status_bytes(value, where):
    if not isinstance(value, dict):
        raise SnapshotError(f"{where}: object mapping status byte -> byte value required")
    _unknown(value, _STATUS_KEYS, where, SnapshotError)
    out = {}
    for key, byte in value.items():
        if not _is_int(byte) or not 0 <= byte <= 0xFF:
            raise SnapshotError(f"{where}[{key!r}]: byte 0..255 required")
        out[key] = byte
    return out


def _unit_facts(value, where, require_identity):
    if not isinstance(value, dict):
        raise SnapshotError(f"{where}: object required")
    _unknown(value, ACTOR_KEYS, where, SnapshotError)
    out = {}
    if require_identity:
        name = value.get("name")
        if not isinstance(name, str) or not name:
            raise SnapshotError(f"{where}.name: non-empty string required")
        out["name"] = name
        out["id"] = _unit_id(value.get("id"), f"{where}.id", SnapshotError)
        out["job_id"] = _nonneg_int(value.get("job_id"), f"{where}.job_id", SnapshotError)
        side = value.get("side")
        if side not in SIDES:
            raise SnapshotError(f"{where}.side: one of {SIDES} required")
        out["side"] = side
    for field in ("hp", "max_hp", "mp", "max_mp", "ct"):
        if field in value:
            out[field] = _nonneg_int(value[field], f"{where}.{field}", SnapshotError)
    if "tile" in value:
        tile = value["tile"]
        if (not isinstance(tile, (list, tuple)) or len(tile) != 2
                or not all(_is_int(v) and 0 <= v < 64 for v in tile)):
            raise SnapshotError(f"{where}.tile: [x, y] with 0 <= v < 64 required")
        out["tile"] = [int(tile[0]), int(tile[1])]
    if "status_bytes" in value:
        out["status_bytes"] = _status_bytes(value["status_bytes"], f"{where}.status_bytes")
    return out


def _candidate(value, where):
    if not isinstance(value, dict):
        raise SnapshotError(f"{where}: object required")
    _unknown(value, CANDIDATE_KEYS, where, SnapshotError)
    out = {}
    cid = value.get("id")
    if not isinstance(cid, str) or not cid:
        raise SnapshotError(f"{where}.id: non-empty string required")
    out["id"] = cid
    if value.get("kind") not in KINDS:
        raise SnapshotError(f"{where}.kind: one of {KINDS} required")
    out["kind"] = value["kind"]
    out["action_id"] = _nonneg_int(value.get("action_id"), f"{where}.action_id", SnapshotError)
    if type(value.get("legal")) is not bool:
        raise SnapshotError(f"{where}.legal: boolean required (the adapter asserts engine legality)")
    out["legal"] = value["legal"]
    out["cost"] = _nonneg_int(value.get("cost", 0), f"{where}.cost", SnapshotError)
    if "relation" in value and value["relation"] is not None:
        if value["relation"] not in RELATIONS:
            raise SnapshotError(f"{where}.relation: one of {RELATIONS} or null")
        out["relation"] = value["relation"]
    if "target" in value and value["target"] is not None:
        target = value["target"]
        if not isinstance(target, dict):
            raise SnapshotError(f"{where}.target: object or null required")
        if target.get("kind") == "unit":
            _unknown(target, ("kind", "id"), f"{where}.target", SnapshotError)
            out["target"] = {"kind": "unit",
                             "id": _unit_id(target.get("id"), f"{where}.target.id", SnapshotError)}
        elif target.get("kind") == "tile":
            _unknown(target, ("kind", "x", "y"), f"{where}.target", SnapshotError)
            x, y = target.get("x"), target.get("y")
            if not (_is_int(x) and _is_int(y) and 0 <= x < 64 and 0 <= y < 64):
                raise SnapshotError(f"{where}.target: tile x/y in 0..63 required")
            out["target"] = {"kind": "tile", "x": x, "y": y}
        else:
            raise SnapshotError(f"{where}.target.kind: 'unit' or 'tile' required")
    for field in ("target_hp", "target_max_hp", "target_mp"):
        if field in value:
            out[field] = _nonneg_int(value[field], f"{where}.{field}", SnapshotError)
    if "target_status_bytes" in value:
        out["target_status_bytes"] = _status_bytes(
            value["target_status_bytes"], f"{where}.target_status_bytes")
    if "ability_name" in value:
        if not isinstance(value["ability_name"], str) or not value["ability_name"]:
            raise SnapshotError(f"{where}.ability_name: non-empty string required")
        out["ability_name"] = value["ability_name"]
    return out


def validate_snapshot(snapshot):
    """Validate and normalize a snapshot; raises SnapshotError, never commits."""
    if not isinstance(snapshot, dict):
        raise SnapshotError("snapshot: object required")
    _unknown(snapshot, SNAPSHOT_KEYS, "snapshot", SnapshotError)
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise SnapshotError(f"snapshot.schema: must be {SNAPSHOT_SCHEMA!r}")
    identity = snapshot.get("identity")
    if not isinstance(identity, str) or not identity:
        raise SnapshotError("snapshot.identity: non-empty string required")
    actor = _unit_facts(snapshot.get("actor"), "snapshot.actor", require_identity=True)
    candidates = snapshot.get("candidates")
    if not isinstance(candidates, list):
        raise SnapshotError("snapshot.candidates: list required")
    parsed = [_candidate(c, f"snapshot.candidates[{i}]") for i, c in enumerate(candidates)]
    ids = [c["id"] for c in parsed]
    if len(set(ids)) != len(ids):
        raise SnapshotError("snapshot.candidates: duplicate candidate id")
    age = snapshot.get("age_seconds")
    if isinstance(age, bool) or not isinstance(age, (int, float)) or age < 0:
        raise SnapshotError("snapshot.age_seconds: non-negative number required")
    out = {"schema": SNAPSHOT_SCHEMA, "identity": identity, "actor": actor,
           "candidates": parsed, "age_seconds": float(age)}
    if "observed_at" in snapshot:
        out["observed_at"] = snapshot["observed_at"]
    return out


# ---------------------------------------------------------------------------
# status decoding
# ---------------------------------------------------------------------------
def statuses_present(unit):
    """Named statuses set in a normalized unit's status_bytes.

    Returns None when the unit carries no status bytes at all, so a status
    predicate can distinguish "known absent" from "unknown" and fail closed.
    """
    block = unit.get("status_bytes")
    if block is None:
        return None
    names = set()
    for byte in STATUS_BYTES:
        value = block.get("0x%02x" % byte)
        if value is None:
            continue
        for name, (bit_byte, mask) in STATUS_BITS.items():
            if bit_byte == byte and value & mask:
                names.add(name)
    return names


def target_statuses(actor, candidate):
    """Named statuses of a candidate's target (the actor's own for relation self).

    None when the required status bytes are absent, matching
    `statuses_present`.
    """
    return statuses_present(_target_unit(actor, candidate))


def _has_status(unit, name, present):
    names = statuses_present(unit)
    if names is None:
        return False
    return (name in names) == present


# ---------------------------------------------------------------------------
# fact extraction + predicates
# ---------------------------------------------------------------------------
def hp_percent(hp, maximum):
    """Integer percent, floored; None when the facts are missing/implausible."""
    if not _is_int(hp) or not _is_int(maximum) or maximum <= 0 or hp < 0:
        return None
    return min(hp, maximum) * 100 // maximum


def _compare(operand, actual):
    for op, value in operand.items():
        if op == "lt" and not actual < value:
            return False
        if op == "lte" and not actual <= value:
            return False
        if op == "gt" and not actual > value:
            return False
        if op == "gte" and not actual >= value:
            return False
        if op == "eq" and not actual == value:
            return False
    return True


def _target_unit(actor, candidate):
    """The candidate's target status block, or the actor's for a self target."""
    block = candidate.get("target_status_bytes")
    if block is None and candidate.get("relation") == "self":
        block = actor.get("status_bytes")
    return {"status_bytes": block} if block is not None else {}


def matches(when, actor, candidate):
    """True when every predicate in `when` holds for this candidate."""
    if not candidate["legal"]:
        return False
    for key, operand in when.items():
        if key == "relation":
            if candidate.get("relation") != operand:
                return False
        elif key == "kind":
            if candidate["kind"] != operand:
                return False
        elif key == "action_id":
            if candidate["action_id"] != operand:
                return False
        elif key == "ability_name":
            if candidate["kind"] != "ability" or candidate.get("ability_name") != operand:
                return False
        elif key == "actor_hp_pct":
            value = hp_percent(actor.get("hp"), actor.get("max_hp"))
            if value is None or not _compare(operand, value):
                return False
        elif key == "target_hp_pct":
            value = hp_percent(candidate.get("target_hp"), candidate.get("target_max_hp"))
            if value is None or not _compare(operand, value):
                return False
        elif key == "remaining_mp_after_cost":
            if actor.get("mp") is None:
                return False
            remaining = actor["mp"] - candidate["cost"]
            if remaining < 0 or not _compare(operand, remaining):
                return False
        elif key == "actor_status_present":
            if not all(_has_status(actor, name, True) for name in operand):
                return False
        elif key == "actor_status_absent":
            if not all(_has_status(actor, name, False) for name in operand):
                return False
        elif key == "target_status_present":
            target = _target_unit(actor, candidate)
            if not all(_has_status(target, name, True) for name in operand):
                return False
        elif key == "target_status_absent":
            target = _target_unit(actor, candidate)
            if not all(_has_status(target, name, False) for name in operand):
                return False
    return True


def _orderable(candidate, field, actor):
    """The selector score, or None when the candidate lacks the fact."""
    if field == "target-hp":
        return candidate.get("target_hp")
    if actor.get("mp") is None:
        return None
    remaining = actor["mp"] - candidate["cost"]
    return remaining if remaining >= 0 else None


def select(matched, selector, actor):
    """Deterministic pick among matched candidates; None when none is orderable."""
    if not matched:
        return None
    if selector == "first":
        return matched[0]
    field = "target-hp" if selector.endswith("target-hp") else "remaining-mp"
    scored = [(score, c) for score, c in
              ((_orderable(c, field, actor), c) for c in matched)
              if score is not None]
    if not scored:
        return None
    if selector.startswith("lowest"):
        return min(scored, key=lambda pair: (pair[0], pair[1]["id"]))[1]
    return min(scored, key=lambda pair: (-pair[0], pair[1]["id"]))[1]


def target_id(candidate):
    target = candidate.get("target")
    if isinstance(target, dict) and target.get("kind") == "unit":
        return target["id"]
    return None


# ---------------------------------------------------------------------------
# scope resolution + evaluation
# ---------------------------------------------------------------------------
def scope_key(actor):
    return f"{actor['name']}#{actor['id']}"


def resolve_scope(actor, assignments):
    """First matching assignment scope in frozen precedence order."""
    characters = assignments.get("characters", {})
    key = scope_key(actor)
    if key in characters:
        return "character", characters[key]
    jobs = assignments.get("jobs", {})
    if str(actor["job_id"]) in jobs:
        return "job", jobs[str(actor["job_id"])]
    party = assignments.get("party", {})
    if actor["side"] in party:
        return "party", party[actor["side"]]
    return None, None


def _decision(scope, rule_id, candidate, fallback, reason):
    return {"candidate_id": candidate["id"], "kind": candidate["kind"],
            "action_id": candidate["action_id"],
            "target": candidate.get("target"), "target_id": target_id(candidate),
            "scope": scope, "rule_id": rule_id, "fallback": fallback,
            "reason": reason}


def _none_outcome(reason, scope, detail=None):
    return {"outcome": OUTCOME_NONE, "reason": reason, "scope": scope,
            "rule_id": None, "decision": None, "detail": detail}


def evaluate(snapshot, policy):
    """Full evaluation: outcome, reason and the decision (or None)."""
    normalized_policy = validate_policy(policy)
    try:
        snap = validate_snapshot(snapshot)
    except SnapshotError as exc:
        return _none_outcome(REASON_SNAPSHOT_INVALID, None, str(exc))
    if snap["identity"] != "verified":
        return _none_outcome(REASON_IDENTITY_UNVERIFIED, None,
                             f"identity={snap['identity']!r}")
    if snap["age_seconds"] > normalized_policy["observation"]["max_age_seconds"]:
        return _none_outcome(REASON_SNAPSHOT_STALE, None,
                             f"age={snap['age_seconds']}s")
    actor = snap["actor"]
    scope, ruleset = resolve_scope(actor, normalized_policy["assignments"])
    if ruleset is not None:
        for rule in ruleset["rules"]:
            if not rule["enabled"]:
                continue
            matched = [c for c in snap["candidates"] if matches(rule["when"], actor, c)]
            chosen = select(matched, rule["select"], actor)
            if chosen is not None:
                return {"outcome": OUTCOME_SELECTED, "reason": REASON_MATCHED,
                        "scope": scope, "rule_id": rule["id"],
                        "decision": _decision(scope, rule["id"], chosen, False,
                                              REASON_MATCHED),
                        "detail": None}
    fallback = normalized_policy["fallback"]
    if ruleset is not None and "fallback" in ruleset:
        fallback = ruleset["fallback"]
    if fallback == "none":
        return _none_outcome(REASON_NO_RULE_MATCH, scope)
    waits = [c for c in snap["candidates"] if c["legal"] and c["kind"] == "wait"]
    if not waits:
        return _none_outcome(REASON_NO_LEGAL_CANDIDATE, scope)
    chosen = min(waits, key=lambda c: c["id"])
    return {"outcome": OUTCOME_FALLBACK, "reason": REASON_FALLBACK_WAIT,
            "scope": scope, "rule_id": "fallback",
            "decision": _decision(scope, "fallback", chosen, True, REASON_FALLBACK_WAIT),
            "detail": None}


def choose_action(snapshot, policy):
    """The frozen A5.2 seam: one engine-legal candidate, or None for no match.

    The adapter must treat None as "commit nothing" (pause), never as
    permission to press keys on its own.
    """
    return evaluate(snapshot, policy)["decision"]
