"""Exercise the real window handoff helper against synthetic UI responses.

Certifies rejection/control flow only; live action/resume remains a separate
gate. The world model serves the SAME reads the helper makes against a real
emulator (per-record roster reads plus the global cursor/key bytes), so the
owner detection, the mode probe and the whole-board destination check are all
driven through the helper's real code path.

Controls:
  1. command-menu-own-tile-is-not-target-mode -- the refuted case: a FRESH
     COMMAND MENU also parks the target copy on the owner's tile, so the old
     "target == own tile" inference was wrong; the probe must find the
     command byte answering, drive Move->target, and still commit.
  2. already-open-target-mode -- the turn-start shape: a blocked direction
     answers neither byte, so the probe must keep trying directions instead
     of declaring the UI dead (the pre-A5.1 single-DOWN probe aborted here).
  3. ct-progress-with-wrong-move-rejects -- CT leaves the parked value but the
     roster tile never mirrors: the pre-fix helper printed PASS; now exit 1.
  4. no-cursor-echo-no-confirmation -- frozen UI: reject before any A.
  5. ambiguous-owner-never-commits -- two records on the target tile: DE-030's
     failure mode must not reach the commit path at all.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import c3_manual_layer as manual

ROSTER_BYTES = manual.REC_LEN * manual.UNITS
DIRS = {"DOWN": (0, 1), "UP": (0, -1), "RIGHT": (1, 0), "LEFT": (-1, 0)}
MOVE, WAIT = 0, 2


class World:
    """Minimal FFTA menu model: records, cursors and the walk commit."""

    def __init__(self, units, owner=6, mode="target", blocked=(),
                 wrong_result=False, frozen=False, clock=None):
        self.units = {s: dict(u) for s, u in units.items()}
        self.owner = owner
        self.owner_tile = [self.units[self.owner]["x"],
                           self.units[self.owner]["y"]]
        self.mode = mode                 # command | target | facing
        self.cmd = MOVE
        # a freshly opened menu parks the move cursor on the owner's tile
        self.target = list(self.owner_tile)
        self.blocked = set(blocked)
        self.wrong_result = wrong_result
        self.frozen = frozen
        self.walk = None
        self.closed = False
        self.closed_at = None
        self.clock = clock or [0.0]
        self.base_ct = units[self.owner].get("ct", 735)

    def _ct(self):
        """Parked CT while the menu is frozen; charging again after the
        turn closes (the engine's own turn-close signature)."""
        if self.closed_at is None:
            return self.base_ct
        return min(1000, int((self.clock[0] - self.closed_at) * 40))

    # -- memory image -----------------------------------------------------
    def _mem(self):
        mem = bytearray(ROSTER_BYTES)
        for slot, u in self.units.items():
            base = manual.REC_LEN * slot
            mem[base + manual.OFF_TILE_X] = u["x"]
            mem[base + manual.OFF_TILE_Y] = u["y"]
            for off, key_, default in ((manual.OFF_HP, "hp", 300),
                                       (manual.OFF_HP + 2, "max_hp", 300),
                                       (manual.OFF_CT, "ct", 0),
                                       (manual.OFF_SIDE, "side", 0x8000)):
                mem[base + off:base + off + 2] = int(
                    u.get(key_, default)).to_bytes(2, "little")
            mem[base + manual.OFF_ID] = u.get("id", slot)
        base = manual.REC_LEN * self.owner
        mem[base + manual.OFF_CT:base + manual.OFF_CT + 2] = \
            self._ct().to_bytes(2, "little")
        return mem

    def read(self, addr, length):
        if manual.ROSTER <= addr < manual.ROSTER + ROSTER_BYTES:
            mem = self._mem()
            off = addr - manual.ROSTER
            return bytes(mem[off:off + length])
        if addr == manual.CMD_CURSOR:
            return bytes([self.cmd])
        if addr == manual.TARGET_X:
            return bytes(self.target)
        if addr == manual.KEYINPUT:
            return (0x3FF).to_bytes(2, "little")
        raise AssertionError(f"unexpected monitor read {addr:#x}")

    # -- input ------------------------------------------------------------
    def key(self, name):
        if self.frozen:
            return
        if self.mode == "command":
            if name == "DOWN" and self.cmd < 3:
                self.cmd += 1
            elif name == "UP" and self.cmd > 0:
                self.cmd -= 1
            elif name == "A" and self.cmd == MOVE:
                self.mode, self.target = "target", list(self.owner_tile)
            elif name == "A" and self.cmd == WAIT:
                self.mode = "facing"
        elif self.mode == "target":
            if name in DIRS:
                dx, dy = DIRS[name]
                nx, ny = self.target[0] + dx, self.target[1] + dy
                if (name not in self.blocked and 0 < nx < 64 and 0 < ny < 64):
                    self.target = [nx, ny]
            elif name == "A" and self.target != self.owner_tile:
                self.walk = list(self.target)
                self.mode, self.cmd = "command", MOVE
                self.target = list(self.owner_tile)   # re-open law
        elif self.mode == "facing" and name == "A":
            self.closed = True
            self.closed_at = self.clock[0]
            if not self.wrong_result and self.walk:
                self.units[self.owner]["x"] = self.walk[0]
                self.units[self.owner]["y"] = self.walk[1]
                self.owner_tile = list(self.walk)


class FakeMonitor:
    def __init__(self, port, world):
        self.world = world
        self.reads = self.faults = self.reconnects = 0
        self.detached = False

    def read(self, addr, length=1):
        self.reads += 1
        return self.world.read(addr, length)

    def detach(self):
        self.detached = True

    def close(self):
        pass


def run_case(root, label, target_open=False, blocked=(), wrong_result=False,
             frozen=False, ambiguous=False, expect_pass=True):
    out = root / label
    out.mkdir(parents=True, exist_ok=True)
    receipt = out / "run.json"
    receipt.write_text(json.dumps({"final_state": "paused",
                                   "manual_handoff": {"pid": 12345,
                                                      "port": 2345}}))
    units = {6: {"x": 4, "y": 10, "hp": 388, "ct": 735, "side": 0,
                 "id": 6},
             0: {"x": 9, "y": 9, "hp": 319, "ct": 100, "side": 0x8000, "id": 0}}
    if ambiguous:
        # DE-030 shape: a second record parks on the same tile as the owner,
        # so "the unit whose own tile holds the cursor" is not unique.
        units[1] = {"x": 4, "y": 10, "hp": 300, "ct": 200, "side": 0x8000,
                    "id": 1}
    clock = [0.0]
    world = World(units, owner=6, mode="target" if target_open else "command",
                  blocked=blocked, wrong_result=wrong_result, frozen=frozen,
                  clock=clock)
    monitor = FakeMonitor(2345, world)
    sent = []

    def sendkey(pid, token):
        name = token.split(":")[0]
        sent.append(name)
        world.key(name)

    fake_time = SimpleNamespace(
        time=lambda: clock[0],
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    with patch.object(manual, "time", fake_time), \
            patch.object(manual, "Monitor", lambda port: monitor), \
            patch.object(manual, "pid_alive", lambda pid: True), \
            patch.object(manual, "capture", lambda *args: None), \
            patch.object(manual, "sendkey", sendkey):
        rc = manual.main(["--receipt", str(receipt), "--window-timeout", "30"])
    result = json.loads((out / "manual-layer.json").read_text())
    assert monitor.detached, "the handoff must resume and release the stub"

    if expect_pass:
        assert rc == 0, f"{label}: expected PASS, got rc={rc} result={result}"
        assert result["manual_move_committed"] is True
        assert result["tile_before"] != result["tile_after"]
        assert result["owner_tile_after"] == result["stepped_target"]
        assert result["other_same_side_moved"] == []
        assert result["destination_verified_by"].startswith("roster tile")
        assert result["owner_slot"] == 6
        assert "A" in sent
    elif ambiguous:
        assert rc == 1 and "A" not in sent, \
            f"{label}: ambiguous owner reached input ({sent})"
        assert result["menu_open"] is False
        assert result["manual_move_committed"] is False
    elif frozen:
        assert rc == 1 and "A" not in sent, f"{label}: pressed A ({sent})"
        assert result["menu_open"] is True
        assert result["manual_move_committed"] is False
    else:
        assert rc == 1 and result["manual_move_committed"] is False
        assert result.get("manual_turn_committed") is None
        assert result.get("observed_ct_progress") is True
    print("PASS", label)


def main():
    root = Path("outputs/autobattle/a51-manual-controls")
    run_case(root, "command-menu-own-tile-is-not-target-mode")
    run_case(root, "already-open-target-mode", target_open=True,
             blocked=("DOWN",))
    run_case(root, "ct-progress-with-wrong-move-rejects", target_open=True,
             wrong_result=True, expect_pass=False)
    run_case(root, "no-cursor-echo-no-confirmation", frozen=True,
             expect_pass=False)
    run_case(root, "ambiguous-owner-never-commits", ambiguous=True,
             expect_pass=False)
    print("MANUAL HANDOFF CONTROL PASS: 5 checks (synthetic, no live claim)")


if __name__ == "__main__":
    main()
