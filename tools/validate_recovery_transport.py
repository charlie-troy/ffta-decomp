"""Real Probe.press and modal transport with a fake RSP peer; host proof only."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from probe_control_handoff import Probe, BP_KEY, ALL_BPS
from recovery_transport import RecoveryTransport
from recovery_menu import RecoveryStateError


class Peer:
    def __init__(self):
        self.armed = set()
        self.log = []
        self.halted = False
        self.halt_reply = "T05"
        self.fail_after = None
        self.writes = 0
        self.reject = None

    def send(self, command):
        self.log.append(command)
        if self.reject and command.startswith(self.reject):
            return "E01"
        if command.startswith(("Z0,", "z0,")):
            address = int(command.split(",")[1], 16)
            (self.armed.add if command.startswith("Z") else self.armed.discard)(address)
        if command.startswith("P1="):
            if self.fail_after is not None and self.writes == self.fail_after:
                raise OSError("peer disconnected during press")
            self.writes += 1
        return "OK"

    def cont(self):
        self.log.append("continue")
        self.halted = False

    def interrupt(self):
        self.log.append("interrupt")
        self.halted = self.halt_reply == "T05"
        return self.halt_reply

    def _read_packet(self):
        self.halted = True
        return "T05"

    def read_registers(self):
        assert self.armed == {BP_KEY}, "only key poll may be armed during input"
        return [0] * 15 + [BP_KEY]

    def read_mem(self, address, size):
        assert self.halted, "memory read without explicit halt"
        self.log.append("memory")
        return bytes(size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--probe-source", help="pre-fix source for discriminating regression")
    args = parser.parse_args()
    probe_class = Probe
    if args.probe_source:
        spec = importlib.util.spec_from_file_location("historical_probe", args.probe_source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        probe_class = module.Probe
    checks = []

    def setup():
        peer = Peer()
        probe = probe_class(SimpleNamespace(g=peer), verbose=False)
        probe.arm()
        ledger = []
        return peer, probe, ledger, RecoveryTransport(probe, log_input=ledger.append)

    with patch("probe_control_handoff.time.sleep", lambda _: None):
        peer, probe, ledger, transport = setup()
        assert probe.press(1, pause=0) == 5
        assert peer.armed == set(ALL_BPS)
        checks.append("legacy Probe.press still restores all trace breakpoints")
        start = len(probe.key_write_log)
        with transport:
            assert peer.halted and not peer.armed
            assert transport.read_mem(0x02000000, 4) == bytes(4)
            interrupts = peer.log.count("interrupt")
            transport.read_mem(0x02000000, 2)
            assert peer.log.count("interrupt") == interrupts
            assert transport.press(1, pause=0) == 5
            assert not peer.armed and not transport.halted
            transport.read_mem(0x02000000, 4)
            assert peer.log.count("interrupt") == interrupts + 1
            transport.cont()
            transport.read_mem(0x02000000, 4)
            assert peer.log.count("interrupt") == interrupts + 2
        assert peer.armed == set(ALL_BPS) and not peer.halted
        assert [{k: v for k, v in r.items() if k != "event"} for r in ledger] == probe.key_write_log[start:]
        checks.extend(["scoped press leaves router hooks suspended", "memory reads explicitly halt after press/passive continue",
                       "same halt is reused until continue", "exit restores real tracing then resumes", "all modal raw writes reach ledger"])
        keys = peer.writes
        transport.close()
        assert peer.writes == keys
        checks.append("idempotent cleanup never injects a key")
        for operation in (lambda: transport.press(1), lambda: transport.read_mem(0, 1),
                          lambda: transport.__enter__()):
            try:
                operation()
            except RecoveryStateError:
                pass
            else:
                raise AssertionError("closed modal transport authorized activity")
        checks.append("closed/reused transport rejects input and reads")

        peer, probe, ledger, transport = setup()
        with transport:
            assert transport.press(1, pause=0, stop_check=lambda: True) == -1
        assert peer.writes == 0 and not ledger and peer.armed == set(ALL_BPS)
        checks.append("pre-input STOP yields zero writes and restores tracing")
        for reply in (None, "OK", "S04", "T04", "", "01020304", "S", "Txy"):
            peer, probe, ledger, transport = setup()
            peer.halt_reply = reply
            try:
                with transport:
                    raise AssertionError("invalid halt was accepted")
            except RecoveryStateError:
                pass
            assert not peer.armed and peer.writes == 0
        checks.append("eight absent/malformed/non-stop/fatal halt replies fail closed with hooks removed")

        peer, probe, ledger, transport = setup()
        peer.fail_after = 2
        try:
            with transport:
                transport.press(1, pause=0)
        except OSError:
            pass
        else:
            raise AssertionError("disconnect suppressed")
        assert len(ledger) == 2 and peer.writes == 2 and peer.armed == set(ALL_BPS)
        checks.append("partial disconnected input is ledgered and never retried")
        peer, probe, ledger, transport = setup()
        with transport:
            try:
                transport.press(1, rearm_trace=True)
            except RecoveryStateError:
                pass
            else:
                raise AssertionError("caller escaped trace suspension")
        assert peer.writes == 0
        checks.append("caller cannot re-arm tracing during modal press")
        for reject in ("Z0,", "z0,"):
            peer, probe, ledger, transport = setup()
            try:
                if reject == "z0,":
                    peer.reject = reject
                with transport:
                    peer.reject = reject
            except OSError:
                pass
            else:
                raise AssertionError("rejected trace hook acknowledged as restored")
            assert peer.writes == 0
            if reject == "Z0,":
                assert any(e["event"] == "restore_failed" for e in transport.events)
                assert not any(e["event"] == "trace_restored" for e in transport.events)
            else:
                assert not any(e["event"] == "trace_suspended" for e in transport.events)
        checks.append("rejected insertion/removal cannot claim restoration/suspension respectively")

    result = {"scope": "host transport/control flow only; not ROM or public-runtime acceptance",
              "status": "pass", "checks": checks, "count": len(checks)}
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS recovery transport: {len(checks)} checks")


if __name__ == "__main__":
    main()
