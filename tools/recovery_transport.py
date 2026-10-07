"""Scoped debugger ownership for recovery; no gameplay or policy decisions.

Keep router breakpoints out of the modal interval, halt before memory reads,
and restore tracing while halted. No monkeypatching of Probe.arm, no retry of
input, and no claim that a delivered final A completed a turn.
"""
from __future__ import annotations

from recovery_menu import require


class RecoveryTransport:
    def __init__(self, probe, *, log_input=lambda rec: None):
        self.probe = probe
        self.g = self  # executor passive_tick and RecoveryMenu read surface
        self.log_input = log_input
        self.events = []
        self.active = False
        self.halted = False
        self.closed = False

    def __enter__(self):
        require(not self.active and not self.closed, "modal transport cannot be reused")
        # Consume any trace stop before removing hooks. interrupt() settles
        # the RSP stream; an unsolicited stop is never used as memory data.
        self.active = True
        try:
            self.interrupt()
            self.probe.disarm(strict=True)
            self.events.append({"event": "trace_suspended"})
        except BaseException:
            self.close()
            raise
        return self

    def interrupt(self):
        require(self.active, "modal transport is not active")
        self.halted = False
        reply = self.probe.g.interrupt()
        require(isinstance(reply, str) and len(reply) >= 3 and reply[0] in ("S", "T")
                and all(c in "0123456789abcdefABCDEF" for c in reply[1:3])
                and reply[:3] not in ("S04", "T04"),
                f"modal debugger halt not established: {reply!r}")
        self.halted = True
        self.events.append({"event": "halt", "reply": reply})
        return reply

    def read_mem(self, address, size):
        require(self.active, "modal transport is not active")
        if not self.halted:
            self.interrupt()
        return self.probe.g.read_mem(address, size)

    def cont(self):
        require(self.active, "modal transport is not active")
        self.halted = False  # invalidate even if continue delivery is ambiguous
        self.probe.g.cont()

    def disarm(self):
        require(self.active, "modal transport is not active")
        self.probe.disarm(strict=True)

    def press(self, mask, **kwargs):
        require(self.active, "modal transport is not active")
        require("rearm_trace" not in kwargs, "modal caller cannot re-arm tracing")
        start = len(getattr(self.probe, "key_write_log", []))
        self.halted = False
        try:
            # Probe owns key-poll insertion/removal and STOP polling. Its
            # original method remains in use, including its finally cleanup.
            return self.probe.press(mask, rearm_trace=False, **kwargs)
        finally:
            # Preserve partial/ambiguous transport writes too. Public runtime
            # integration must use this callback for its raw input ledger.
            for write in getattr(self.probe, "key_write_log", [])[start:]:
                self.log_input({"event": "key_write", **write})

    def close(self):
        if self.closed:
            return
        self.closed = True
        if not self.active:
            return
        try:
            if not self.halted:
                self.interrupt()
            self.probe.arm(strict=True)
            self.events.append({"event": "trace_restored",
                                "write_count": len(getattr(self.probe, "key_write_log", []))})
            self.cont()
        except BaseException as exc:
            self.events.append({"event": "restore_failed", "error": repr(exc)})
            # A failed restore must not leave partially inserted hooks behind.
            self.probe.disarm()
            raise
        finally:
            self.active = False
            self.halted = False

    def __exit__(self, exc_type, exc, tb):
        self.close()
