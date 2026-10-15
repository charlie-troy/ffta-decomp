"""Terminal research transport: disarm while halted before owned process close.

Public handoff/resume continues to use RecoveryTransport's normal restoration.
This terminal mode never resumes or restores trace hooks on context exit.
"""
from recovery_transport import RecoveryTransport


class ConsumableResearchTransport(RecoveryTransport):
    def close(self):
        if self.closed:return
        self.closed=True
        if not self.active:return
        try:
            if not self.halted:self.interrupt()
            self.probe.disarm(strict=True)
            self.events.append({'event':'terminal_trace_disarmed','write_count':len(getattr(self.probe,'key_write_log',[]))})
        except BaseException as exc:
            self.events.append({'event':'terminal_disarm_failed','error':repr(exc)})
            raise
        finally:
            self.active=False;self.halted=False
