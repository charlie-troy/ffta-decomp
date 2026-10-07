"""Offline assertions for the public runner's bounded recovery journal."""
from recovery_executor import KEYS, CURE, WAIT
from tactics_policy import evaluate, validate_policy
from recovery_menu import require


def validate_recovery(journal, ledger, *, confirmed=False):
    require(journal["schema"] == "ffta-recovery-turn/1", "recovery journal schema")
    writes = journal["raw_writes"]
    observed = [{k: v for k, v in row.items() if k != "event"} for row in ledger
                if row.get("event") == "key_write"
                and journal["started_t"] <= row["t"] <= journal["ended_t"]]
    require(writes == observed, "recovery raw ledger missing or changed")
    transport = journal["transport"]
    if writes or confirmed:
        require(transport and transport[0]["event"] == "halt", "recovery explicit halt missing")
    if not confirmed and journal.get("status") not in ("confirmed", "unexecuted-wait"):
        return
    require(journal["status"] == "confirmed" if confirmed else journal["status"] in ("confirmed", "unexecuted-wait"),
            "recovery completion missing")
    wait_confirmed = journal["status"] == "confirmed"
    require(transport[1]["event"] == "trace_suspended"
            and transport[-1]["event"] == "trace_restored"
            and sum(e["event"] == "trace_suspended" for e in transport) == 1
            and sum(e["event"] == "trace_restored" for e in transport) == 1
            and all(e["event"] in ("halt", "trace_suspended", "trace_restored") for e in transport),
            "recovery trace lifecycle invalid")
    require(transport[-1]["write_count"] == journal["write_start"] + len(writes),
            "recovery input after trace restoration")
    halts = [e for e in transport if e["event"] == "halt"]
    require(all(isinstance(e["reply"], str) and len(e["reply"]) >= 3
                and e["reply"][0] in "ST" and e["reply"][1:3] not in ("04",)
                and all(c in "0123456789abcdefABCDEF" for c in e["reply"][1:3]) for e in halts),
            "recovery halt reply invalid")
    owner = journal["owner"]
    tile = [owner["x"], owner["y"]]
    cure, finish = journal["recovery"], journal["finish"]
    before, after = cure["before"], cure["after"]
    accepted = cure["outcome"] == "accepted"
    require(cure["outcome"] in ("accepted", "declined") and before["state"] == after["state"] == "command",
            "recovery action boundary differs")
    require((owner["id"], owner["job"], owner["race"], tile) == (6, 2, 1, [4, 10]),
            "recovery fixture owner differs")
    for field in ("member", "context", "callback", "max_hp", "max_mp", "target_tile"):
        require(before[field] == after[field] == finish["before"][field], "recovery pin changed")
    require(before["target_tile"] == tile and (before["hp"], before["mp"]) == (owner["hp"], owner["mp"])
            and 0 < before["hp"] <= before["max_hp"] <= 999
            and 0 <= before["mp"] <= before["max_mp"] <= 999
            and before["cure_cost"] == 6, "recovery resources or cost invalid")
    if accepted:
        require(after["hp"] > before["hp"] and after["mp"] == before["mp"] - 6
                and after["hp"] <= after["max_hp"]
                and after["rows"].count(9) == 1 and after["enabled"][after["rows"].index(9)] == 0,
                "recovery heal/cost/Action effect missing")
    else:
        require((after["hp"], after["mp"]) == (before["hp"], before["mp"])
                and cure["fallback"] == "unexecuted", "declined recovery spent resources")
    facing = finish.get("facing")
    require((finish["before"]["hp"], finish["before"]["mp"]) == (after["hp"], after["mp"]),
            "Wait resources differ")
    if wait_confirmed:
        require(finish["outcome"] == "confirmed" and finish["continuation"] == "unverified"
                and facing["state"] == "facing" and facing["driver_state"] == 47
                and type(facing["facing_direction"]) is int and facing["facing_direction"] in range(4),
                "guarded Wait facing missing")
        require((facing["hp"], facing["mp"]) == (after["hp"], after["mp"])
                and facing["member"] == after["member"] and facing["target_tile"] == tile,
                "Wait actor/resources differ")
    else:
        require(finish["outcome"] == "unexecuted" and facing is None, "unselected Wait was executed")
    policy = validate_policy(journal["policy_document"])
    requests, deliveries = [], []
    for family, expected_id, facts in (("cure_events", CURE, before), ("wait_events", WAIT, after)):
        events = journal[family]
        req = [e for e in events if e["event"] == "input_requested"]
        delivered = [e for e in events if e["event"] == "input_delivered"]
        require(len(req) == len(delivered) and [e["key"] for e in req] == [e["key"] for e in delivered],
                "recovery request/delivery mismatch")
        require(all(e["facts"]["member"] == before["member"]
                    and e["facts"]["actor_wrapper"] == before["actor_wrapper"]
                    and (e["facts"]["hp"], e["facts"]["mp"]) == (facts["hp"], facts["mp"])
                    for e in req), "recovery input owner/resources drifted")
        finals = [e for e in req if e["final"]]
        needed = wait_confirmed if family == "wait_events" else accepted
        require(len(finals) == int(needed) and (not finals or req[-1] == finals[0]),
                "duplicate or post-final recovery input")
        policies = [e for e in events if e["event"] in ("policy", "final_policy")]
        if needed:
            require([e["event"] for e in policies] == ["policy", "final_policy"]
                    and events.index(policies[-1]) < events.index(finals[0]), "recovery final policy missing")
        elif policies:
            require([e["event"] for e in policies] == ["policy"], "declined policy lifecycle differs")
        elif family == "cure_events":
            unavailable = [e for e in events if e["event"] == "unavailable"]
            observations = [e["facts"] for e in events if e["event"] == "observation"
                            and e["facts"]["state"] == "ability-list"]
            require(unavailable == [{"event": "unavailable", "ability": 1}]
                    and observations and observations[-1]["ability_ids"].count(1) == 1
                    and not observations[-1]["enabled"][observations[-1]["ability_ids"].index(1)],
                    "disabled Cure evidence missing")
        else:
            raise ValueError("unexecuted Wait policy missing")
        if family == "wait_events" and not wait_confirmed:
            require(not req, "policy-unselected Wait received input")
        for entry in policies:
            snap = entry["snapshot"]
            require(evaluate(snap, policy) == entry["evaluation"], "recovery policy replay differs")
            actor = snap["actor"]
            require((actor["name"], actor["id"], actor["job_id"], actor["side"], actor["tile"],
                     actor["hp"], actor["max_hp"], actor["mp"], actor["max_mp"])
                    == (owner["name_text"], owner["id"], owner["job"], "player", tile,
                        facts["hp"], facts["max_hp"], facts["mp"], facts["max_mp"]), "recovery chooser actor differs")
            candidate = ({"id": CURE, "kind": "ability", "action_id": 1, "legal": True, "cost": 6,
                          "ability_name": "Cure", "relation": "self", "target": {"kind": "unit", "id": owner["id"]},
                          "target_hp": facts["hp"], "target_max_hp": facts["max_hp"], "target_mp": facts["mp"]}
                         if expected_id == CURE else
                         {"id": WAIT, "kind": "wait", "action_id": 10, "legal": True, "cost": 0})
            require(snap["candidates"] == [candidate], "recovery engine candidate differs")
            if needed:
                require((entry["evaluation"].get("decision") or {}).get("candidate_id") == expected_id,
                        "recovery policy did not select confirmed action")
            else:
                require((entry["evaluation"].get("decision") or {}).get("candidate_id") != expected_id,
                        "declined action was selected by policy")
        if family == "cure_events" and accepted:
            fact = finals[0]["facts"]
            require(fact["state"] == "confirmation" and fact["cursor"] == 0
                    and fact["selected_ability"] == 1 and fact["peer"] == fact["member"] == after["member"]
                    and (fact["hp"], fact["mp"], fact["target_tile"]) == (before["hp"], before["mp"], tile),
                    "final self-Cure target differs")
        if family == "wait_events" and wait_confirmed:
            require({k: v for k, v in finals[0]["facts"].items() if k != "observed_at"}
                    == {k: v for k, v in facing.items() if k != "observed_at"},
                    "final Wait observation differs")
        requests.extend(req)
        deliveries.extend(delivered)
    require(len(halts) >= len(requests) and len(writes) == sum(d["hits"] for d in deliveries),
            "recovery halt/write count differs")
    offset = 0
    for request, delivery in zip(requests, deliveries):
        group = writes[offset:offset + delivery["hits"]]
        require([w["hits"] for w in group] == list(range(1, delivery["hits"] + 1))
                and all(w["val"] == KEYS[request["key"]] and w["manual"] is False for w in group),
                "recovery raw key sequence differs")
        offset += delivery["hits"]
    later = journal["continuations"]
    if not wait_confirmed:
        require(not later, "unexecuted Wait claims continuation")
        return
    require(len(later) == 2 and len({r["actor"]["id"] for r in later}) == 2
            and len({r["wrapper"] for r in later}) == 2 and len({r["canonical"] for r in later}) == 2,
            "independent later actors missing")
    for item in later:
        row, own = item["actor"], item["player_after"]
        require(row["side_bit"] is True and row["unaffiliated"] is False and row["id"] in range(6)
                and row["side_raw"] & 0x8000 and not row["side_raw"] & 0x1000
                and 0 < row["hp"] <= row["max_hp"] <= 999 and 0 <= row["mp"] <= row["max_mp"] <= 999
                and row["job"] in range(116) and row["base_job"] in range(116)
                and row["type"] in (1, 2) and 1 <= row["race"] <= 8 and 1 <= row["level"] <= 50
                and row["tile"] == item["target_tile"] and all(0 <= v < 64 for v in row["tile"])
                and item["canonical"] != facing["member"] and item["wrapper"] != facing["actor_wrapper"],
                "continuing enemy attribution differs")
        require((own["name"], own["id"], own["job"], own["side_bit"], own["x"], own["y"], own["hp"], own["mp"])
                == (owner["name"], owner["id"], owner["job"], False, *tile, after["hp"], after["mp"]),
                "completed player changed during continuation")
