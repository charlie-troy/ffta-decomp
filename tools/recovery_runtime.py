"""Bounded public-runner self-Cure transaction for the seven-unit fixture.

Owns the modal interval only. The caller owns lifecycle, terminal cleanup,
and any later menu. This does not expose party healing or arbitrary abilities.
"""
from __future__ import annotations

import json
import time

from recovery_continuation import observe_continuation
from recovery_executor import SelfCureExecutor, WaitFacingExecutor, RecoveryStopped
from recovery_menu import RecoveryMenu, RecoveryStateError, require
from recovery_transport import RecoveryTransport
from fixture_guard import read_roster


def drive_recovery(runtime, journal, *, before_confirmation=lambda observation: None):
    owner, probe = runtime.owner, runtime.p
    start = len(getattr(probe, "key_write_log", []))

    def checkpoint():
        if runtime._stop_check():
            raise RecoveryStopped("STOP requested during bounded recovery")
        if time.time() - runtime.t0 >= runtime.wall_timeout:
            raise TimeoutError("bounded recovery reached runner wall budget")
        return False

    def log_input(record):
        # A recovery transaction cannot claim auditable input after a failed
        # ledger write. Propagate instead of the legacy best-effort logger.
        runtime._input_log.write(json.dumps(record) + "\n")
        runtime._input_log.flush()

    transport = RecoveryTransport(probe, log_input=log_input)
    journal.update(schema="ffta-recovery-turn/1", scope="seven-unit pinned self-Cure",
                   transport=transport.events, continuations=[], write_start=start,
                   policy_document=runtime.tactics.policy if runtime.tactics else None,
                   owner=dict(owner),
                   started_t=round(time.time() - runtime.t0, 3))
    try:
        require(runtime.tactics is not None, "bounded recovery requires a tactics policy")
        require((owner["id"], owner["job"], owner["race"], owner["x"], owner["y"])
                == (6, 2, 1, 4, 10) and len(runtime._pre_players) == 1,
                "bounded recovery fixture identity differs")
        rom = runtime.s.read_rom_bytes()
        with transport:
            checkpoint()
            roster = read_roster(transport.g, rom=rom)
            require(roster["struct_count"] == roster["live_count"] == 7
                    and roster["ids_distinct"] and roster["live_contiguous"]
                    and {r["id"] for r in roster["slots"] if r["live"]} == set(range(7)),
                    "bounded recovery requires the restored seven-unit roster")
            menu = RecoveryMenu(transport.g, rom, owner)
            require(menu.snapshot().cure_cost == 6, "bounded recovery requires six-MP Cure")

            def after_key(name):
                checkpoint()
                transport.cont()
                time.sleep(0.25)

            def before_policy_final(observation):
                checkpoint()
                log_input({"event": "recovery_confirmation", "state": observation.state,
                           "t": round(time.time() - runtime.t0, 3),
                           "actor_id": owner["id"]})
                before_confirmation(observation)
                checkpoint()

            options = dict(stop_check=checkpoint, after_key=after_key, before_policy_final=before_policy_final,
                           choose=runtime.tactics.choose_recovery)
            cure = SelfCureExecutor(menu, transport, runtime.tactics.policy, **options)
            journal["cure_events"] = cure.events
            journal["recovery"] = cure.run()
            finish = WaitFacingExecutor(menu, transport, runtime.tactics.policy, **options)
            journal["wait_events"] = finish.events
            journal["finish"] = finish.run()
            if journal["finish"]["outcome"] != "confirmed":
                journal["status"] = "unexecuted-wait"
                return False
            facing = journal["finish"]["facing"]
            deadline = min(time.monotonic() + 20,
                           time.monotonic() + max(0, runtime.wall_timeout - (time.time() - runtime.t0)))
            while len(journal["continuations"]) < 2 and time.monotonic() < deadline:
                checkpoint()
                transport.cont()
                time.sleep(0.25)
                checkpoint()
                transport.interrupt()
                try:
                    observation = observe_continuation(transport.g, rom, owner, facing)
                except RecoveryStateError as exc:
                    journal.setdefault("continuation_rejections", []).append(str(exc))
                    continue
                if observation["actor"]["id"] not in {r["actor"]["id"] for r in journal["continuations"]}:
                    journal["continuations"].append(observation)
            require(len(journal["continuations"]) == 2, "independent continuation not established")
            journal["status"] = "confirmed"
            return True
    finally:
        journal["raw_writes"] = list(getattr(probe, "key_write_log", [])[start:])
        journal["ended_t"] = round(time.time() - runtime.t0, 3)
