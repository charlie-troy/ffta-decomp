"""A2.4a fixture guard + owned emulator session (read-only verification).

This module repairs the two stale constants that made the old
`tools/boot_fixture_gdb.py` validate the wrong records:

* the old `NAME0_ADDR = 0x02015AF0` sampled **slot1** of the roster,
  not slot0 (`ROSTER + 0x108`).
* the old `MID6_ADDR = 0x0201611C` sampled the **refuted slot6/scratch
  record** at `0x02016018`, which is a turn-scratch record, not a unit.

Live layout established in A2.3 (2026-09-09, `docs/player-ai-control.md`):

    battle struct  0x020159E4   +0x00 u32 unit count, +0x04 unit array
    roster         0x020159E8   stride 0x108, slot0 = Marche
      +0x00   u32  ROM name pointer (RAM pointer => scratch record)
      +0x28   u16  persistent status; bit 0x8000 is the AI side bit
      +0xD0   u16  CT
      +0xEA   u8   menu-body handoff flag (bit7) / live status bits
      +0x104  u8   unit id (controller id)

The guard is deliberately read-only, so a wrong or missing fixture is
rejected before any memory write. All writes an experiment performs go
through `FixtureSession.write_bytes`, which records a receipt.

Usage (from an experiment script, one connection for boot + experiment):

    with FixtureSession(state="a2-battle-start.ss0") as s:
        print(s.receipt)

CLI entry point: `python tools/boot_fixture_gdb.py [fixture]`.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROM = os.path.join(REPO, "baserom.gba")
DEFAULT_SAVE = os.path.join(REPO, "baserom.sav")
DEFAULT_FIXTURE_DIR = os.path.join(REPO, "outputs", "lua-nav")
DEFAULT_EMULATOR = r"C:\Users\charl\ffta-tools\mGBA-0.10.5-win64\mGBA.exe"
DEFAULT_WORK_DIR = os.path.join(REPO, "outputs", "autobattle", "scratch")

# mGBA 0.10.5 hardcodes the GDB stub port for `-g` (no CLI/config override:
# GDBController::setPort is only reachable from the GDB window UI), so only one
# stub can exist at a time. Never reuse a listener we did not start.
GDB_PORT = 2345
EXPECTED_ROM_SHA1 = "4ac05441f4de70a4ec3dd932116346c61b8783d9"

BATTLE_STRUCT = 0x020159E4
ROSTER = 0x020159E8
STRIDE = 0x108
COUNT_OFF = 0x00
OFF_NAME = 0x00
OFF_SIDE = 0x28
OFF_CT = 0xD0
OFF_EA = 0xEA
OFF_ID = 0x104
OFF_ED = 0xED
OFF_E6 = 0xE6
OFF_DC = 0xDC

KEY_ENABLE_ADDR = 0x03000005
KEY_STRUCT = 0x03000000

# Both context-phase candidates from the earlier probe tooling. They are
# reported, not trusted: only slot0 identity decides "right fixture".
PHASE_ADDRS = {
    "ctx_normal": 0x0200F5C4 + 0x54F4,
    "ctx_alt": 0x020101F8 + 0x54F4,
}

ROM_LO, ROM_HI = 0x08000000, 0x09000000
SIDE_BIT = 0x8000        # which of the two battle sides a unit belongs to
UNAFFILIATED_BIT = 0x1000  # kept out of both side pools (e.g. the Judge)

# Live slot0 is an enemy unit (ROM name pointer, decodes to "Jon") in both
# `battle-start.ss0` and `fix3-battle-start.ss0`, observed 2026-09-10. The
# player's own unit is RAM-named (see PLAYER_NAME_PTR below); A2.3's "slot0 is
# Marche" was the misreading A2.4a repaired.
SLOT0_NAME_PTR = 0x085671EE
PLAYER_NAME_PTR = 0x02001F1C   # EWRAM name string observed as "Marche"

DEFAULT_EXPECT = {
    "slot0_name": SLOT0_NAME_PTR,
    "slot0_id": 0,             # unit ids are assigned from 0 at insertion
    "struct_count": 7,         # 5 enemies + Judge + the player unit
    "live_units": 7,
    "player_name_text": "Marche",
    "slot0_ct": None,          # informational unless a value is supplied
}


def decode_name(rom, ptr):
    """Decode a ROM name pointer (single-byte table) without importing the
    text tool at module import time."""
    if not rom or ptr is None or not (ROM_LO <= ptr < ROM_HI):
        return None
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import ffta_text
        text, _, _ = ffta_text.decode1(rom, ptr - ROM_LO)
        return text
    except Exception:
        return None


def decode_ram_name(g, ptr, rom=None):
    """Decode a unit name whether it lives in ROM or in EWRAM.

    Live fixtures hold generic/NPC units with ROM name pointers and the
    player's own characters with pointers into EWRAM (their names are edited
    in the save), so a ROM-only rule silently mislabels the protagonist as
    scratch. That mistake is what A2.4a corrected.
    """
    if ptr is None:
        return None
    if ROM_LO <= ptr < ROM_HI:
        return decode_name(rom, ptr)
    if 0x02000000 <= ptr < 0x04000000:
        data = g.read_mem(ptr, 32)
        if not data:
            return None
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import ffta_text
            for codec in (ffta_text.decode, ffta_text.decode1):
                try:
                    text, used, unknown = codec(data, 0)
                    if text and not unknown:
                        return text
                except Exception:
                    continue
        except Exception:
            return None
    return None


class FixtureError(RuntimeError):
    """Raised when the session cannot start or the guard rejects the fixture."""


# ---------------------------------------------------------------- memory reads

def u8(g, addr):
    d = g.read_mem(addr, 1)
    return d[0] if d else None


def u16(g, addr):
    d = g.read_mem(addr, 2)
    return int.from_bytes(d, "little") if d else None


def u32(g, addr):
    d = g.read_mem(addr, 4)
    return int.from_bytes(d, "little") if d else None


def read_slot(g, index):
    base = ROSTER + STRIDE * index
    return {
        "slot": index,
        "addr": f"{base:08x}",
        "name": u32(g, base + OFF_NAME),
        "side_raw": u16(g, base + OFF_SIDE),
        "ct": u16(g, base + OFF_CT),
        "ea": u8(g, base + OFF_EA),
        "id": u8(g, base + OFF_ID),
        # Identity helpers for the roster reconciliation (unit-struct.md).
        "type": u8(g, base + 0x04),
        "base_job": u8(g, base + 0x05),
        "race": u8(g, base + 0x06),
        "job": u8(g, base + 0x07),
        "level": u8(g, base + 0x09),
        "hp": u16(g, base + 0x18),
        "max_hp": u16(g, base + 0x1A),
        "mp": u16(g, base + 0x1C),
        "max_mp": u16(g, base + 0x1E),
    }


def read_roster(g, max_slots=8, rom=None):
    """Read the battle struct count plus every record it could cover.

    Records whose name pointer is not in ROM are turn/menu scratch records,
    not units; the caller must not infer party size from the struct count
    alone. `side_bit` is the raw 0x8000 grouping flag and says nothing about
    which group the player controls, so it is reported, never interpreted.
    """
    count = u32(g, BATTLE_STRUCT + COUNT_OFF)
    slots = []
    for i in range(max_slots):
        s = read_slot(g, i)
        s["is_rom_name"] = bool(s["name"] and ROM_LO <= s["name"] < ROM_HI)
        s["is_ram_name"] = bool(s["name"] and 0x02000000 <= s["name"] < 0x04000000)
        s["name_text"] = decode_ram_name(g, s["name"], rom=rom)
        s["side_bit"] = None if s["side_raw"] is None else bool(
            s["side_raw"] & SIDE_BIT)
        s["unaffiliated"] = None if s["side_raw"] is None else bool(
            s["side_raw"] & UNAFFILIATED_BIT)
        # A unit record, not a turn/menu scratch copy: real units carry a name
        # pointer, a unit id below the 0xFF sentinel, and positive max HP.
        s["live"] = bool(s["name"]) and s["id"] not in (None, 0xFF) and \
            (s["max_hp"] or 0) > 0
        slots.append(s)
    live = [s for s in slots if s["live"]]
    contiguous = [s["slot"] for s in live] == list(range(len(live)))
    ids = [s["id"] for s in live]
    ram_named = [s for s in live if s["is_ram_name"]]
    return {
        "struct_addr": f"{BATTLE_STRUCT:08x}",
        "roster_addr": f"{ROSTER:08x}",
        "struct_count": count,
        "slots": slots,
        "live_count": len(live),
        "live_slots": [s["slot"] for s in live],
        "live_names": [s["name_text"] for s in live],
        "live_contiguous": contiguous,
        "ids_distinct": len(set(ids)) == len(ids),
        "side_bit_set": sum(1 for s in live if s["side_bit"]),
        "side_bit_clear": sum(1 for s in live if s["side_bit"] is False),
        "unaffiliated": sum(1 for s in live if s["unaffiliated"]),
        "ram_named_slots": [s["slot"] for s in ram_named],
        "ram_named_units": [{"slot": s["slot"], "id": s["id"], "name": s["name_text"],
                             "level": s["level"], "max_hp": s["max_hp"]}
                            for s in ram_named],
        "scratch_slots": [s["slot"] for s in slots if not s["live"]],
    }


def read_scene(g):
    out = {"keystruct": None, "phases": {}}
    ks = g.read_mem(KEY_STRUCT, 8)
    out["keystruct"] = ks.hex() if ks else None
    for name, addr in PHASE_ADDRS.items():
        out["phases"][name] = u8(g, addr)
    return out


# --------------------------------------------------------------------- guard

def guard(g, expect=None, exact_ct=False, rom=None):
    """Read-only fixture verification. Returns a receipt dict.

    Required checks decide `ok`; informational checks are recorded for the
    receipt and never reject a fixture. The guard performs no writes.
    """
    exp = dict(DEFAULT_EXPECT)
    if expect:
        exp.update({k: v for k, v in expect.items() if v is not None})
    roster = read_roster(g, rom=rom)
    scene = read_scene(g)
    s0 = roster["slots"][0]
    checks = []

    def add(name, ok, detail, severity="required"):
        checks.append({"check": name, "ok": None if ok is None else bool(ok),
                       "severity": severity, "detail": detail})

    add("battle_struct_readable",
        roster["struct_count"] is not None and 2 <= roster["struct_count"] <= 16,
        f"struct_count={roster['struct_count']}")
    add("slot0_name_matches",
        s0["name"] is not None and
        (exp["slot0_name"] is None or s0["name"] == exp["slot0_name"]),
        f"slot0 name={s0['name'] and hex(s0['name'])} "
        f"({s0['name_text']!r}) expected={exp['slot0_name'] and hex(exp['slot0_name'])}")
    if exp["slot0_id"] is not None:
        add("slot0_id_matches", s0["id"] == exp["slot0_id"],
            f"slot0 id={s0['id']} expected={exp['slot0_id']}")
    add("live_ids_distinct", roster["ids_distinct"],
        f"ids={[s['id'] for s in roster['slots'] if s['live']]}")
    add("roster_live_contiguous", roster["live_contiguous"],
        f"live slots={roster['live_slots']}")
    add("at_least_two_live_units", roster["live_count"] >= 2,
        f"live_count={roster['live_count']}")
    add("struct_count_matches_units",
        roster["struct_count"] == roster["live_count"],
        f"struct_count={roster['struct_count']} unit_records={roster['live_count']}")
    if exp["struct_count"] is not None:
        add("struct_count_matches", roster["struct_count"] == exp["struct_count"],
            f"struct_count={roster['struct_count']} expected={exp['struct_count']}")
    if exp["live_units"] is not None:
        add("live_units_matches", roster["live_count"] == exp["live_units"],
            f"live_count={roster['live_count']} expected={exp['live_units']}")
    if exp["player_name_text"] is not None:
        named = [u for u in roster["ram_named_units"]
                 if u["name"] == exp["player_name_text"]]
        add("player_unit_named", bool(named),
            f"expected {exp['player_name_text']!r} among RAM-named units; "
            f"got {roster['ram_named_units']}")
    if exp["slot0_ct"] is not None:
        add("slot0_ct_matches", s0["ct"] == exp["slot0_ct"],
            f"slot0 ct={s0['ct']} expected={exp['slot0_ct']}",
            severity="required" if exact_ct else "info")
    add("slot0_ct_plausible", s0["ct"] is not None and 0 <= s0["ct"] <= 1000,
        f"slot0 ct={s0['ct']}", severity="info")
    add("scene_readable", any(v is not None for v in scene["phases"].values()),
        f"phases={scene['phases']}", severity="info")

    ok = all(c["ok"] for c in checks if c["severity"] == "required")
    return {"ok": ok, "checks": checks, "roster": roster, "scene": scene,
            "expect": exp}


# ------------------------------------------------------------------- session

def rom_sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def port_listener_pid(port):
    """PID listening on `port`, or None. Read-only netstat lookup."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and \
                parts[1].endswith(f":{port}") and parts[3].upper() == "LISTENING":
            return int(parts[4])
    return None


class FixtureSession:
    """Launch an owned mGBA on a fixture and hold one GDB connection.

    Refuses to attach to or terminate any emulator it did not launch. The
    battery save and ROM are copied into a scratch directory, so the user's
    `baserom.sav` is never written.
    """

    def __init__(self, state, rom=DEFAULT_ROM, emulator=DEFAULT_EMULATOR,
                 save=DEFAULT_SAVE, work_dir=None, port=GDB_PORT,
                 expected_rom_sha1=EXPECTED_ROM_SHA1, verify_rom=True,
                 missing_state_ok=False, expect=None, exact_ct=False,
                 boot_wait=2.0, attach_timeout=20.0, quiet=False):
        # Absolute paths throughout: mGBA resolves -t/ROM arguments relative to
        # its own cwd, so relative scratch paths silently load nothing.
        self.state = os.path.abspath(state) if state else None
        self.rom = os.path.abspath(rom)
        self.emulator = emulator
        self.save = os.path.abspath(save) if save else None
        self.work_dir = os.path.abspath(work_dir or os.path.join(
            DEFAULT_WORK_DIR, os.path.splitext(os.path.basename(state or "nostate"))[0]))
        self.port = port
        self.expected_rom_sha1 = expected_rom_sha1
        self.verify_rom = verify_rom
        self.missing_state_ok = missing_state_ok
        self.expect = expect
        self.exact_ct = exact_ct
        self.boot_wait = boot_wait
        self.attach_timeout = attach_timeout
        self.quiet = quiet

        self.proc = None
        self.pid = None
        self.g = None
        self.receipt = None
        self.writes = []
        self._rom_data = None
        self.emulator_version = None
        self.rom_sha1 = None
        self.work_paths = {}

    # -- logging -----------------------------------------------------------
    def log(self, msg):
        if not self.quiet:
            print(msg, flush=True)

    # -- lifecycle ---------------------------------------------------------
    def _check_port_free(self):
        owner = port_listener_pid(self.port)
        if owner is not None:
            raise FixtureError(
                f"GDB port {self.port} already has a listener (pid {owner}); "
                "refusing to reuse or kill an emulator this session did not "
                "launch. Close that instance or run on a machine/port where "
                "the stub is free (mGBA 0.10.5 has no CLI port override).")

    def _prepare_scratch(self):
        state_abs = self.state
        if state_abs and not os.path.isfile(state_abs) and not self.missing_state_ok:
            raise FixtureError(f"fixture state not found: {state_abs}")
        if not os.path.isfile(self.rom):
            raise FixtureError(f"ROM not found: {self.rom}")
        if self.verify_rom:
            self.rom_sha1 = rom_sha1(self.rom)
            if self.rom_sha1 != self.expected_rom_sha1:
                raise FixtureError(
                    f"ROM SHA1 mismatch: {self.rom_sha1} != "
                    f"{self.expected_rom_sha1}")
        os.makedirs(self.work_dir, exist_ok=True)
        rom_copy = os.path.join(self.work_dir, os.path.basename(self.rom))
        shutil.copyfile(self.rom, rom_copy)
        save_copy = None
        if self.save and os.path.isfile(self.save):
            save_copy = os.path.join(
                self.work_dir, os.path.splitext(os.path.basename(self.rom))[0] + ".sav")
            shutil.copyfile(self.save, save_copy)
        state_copy = None
        if state_abs and os.path.isfile(state_abs):
            state_copy = os.path.join(self.work_dir, os.path.basename(state_abs))
            shutil.copyfile(state_abs, state_copy)
        self.work_paths = {"rom": rom_copy, "save": save_copy, "state": state_copy}
        self.log(f"scratch: {self.work_dir} (rom+save+state copied; user save untouched)")

    def start(self, attempts=3):
        """Boot and verify, relaunching on the known `-g` boot flake.

        The stub occasionally comes up non-responsive (the same bimodality the
        old helper retried around), so a failed attach/halt relaunches the
        owned process rather than weakening the guard.
        """
        self._check_port_free()
        self._prepare_scratch()
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                self._boot_once()
                self.receipt = guard(self.g, expect=self.expect,
                                     exact_ct=self.exact_ct,
                                     rom=self.read_rom_bytes())
                return self.receipt
            except Exception as exc:
                last_error = exc
                self.log(f"boot attempt {attempt}/{attempts} failed: {exc}")
                self.stop()
                time.sleep(2.0)
        raise FixtureError(f"could not boot a responsive fixture: {last_error}")

    def read_rom_bytes(self):
        """ROM bytes for name decoding (cached; never written back)."""
        if self._rom_data is None:
            try:
                with open(self.rom, "rb") as fh:
                    self._rom_data = fh.read()
            except OSError:
                return None
        return self._rom_data

    def _boot_once(self):
        cmd = [self.emulator, "-g"]
        if self.work_paths["state"]:
            cmd += ["-t", self.work_paths["state"]]
        cmd.append(self.work_paths["rom"])
        self.proc = subprocess.Popen(cmd, cwd=self.work_dir,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        self.pid = self.proc.pid
        self.log(f"launched owned mGBA pid {self.pid} port {self.port}")
        time.sleep(self.boot_wait)
        self._attach()
        self._move_window_to_primary()

    def _move_window_to_primary(self):
        """Move the emulator window to the primary monitor's top-left.

        Verified live (2026-09-15): this workstation opens mGBA on a secondary
        portrait monitor, where the GL surface does not composite into
        CopyFromScreen captures — every in-run screenshot grabbed desktop
        pixels at the window's coordinates and the whole visual record was
        void. Probe input is injected via GDB breakpoints, never window
        messages, so moving the window cannot affect the run; it only
        restores reliable screenshots. Best-effort: never fatal.
        """
        try:
            import ctypes
            user32 = ctypes.windll.user32
            if not hasattr(user32, "EnumWindows"):
                self.log("window move skipped: not Windows")
                return
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                          ctypes.c_void_p)
            found = []

            def _cb(hwnd, _lparam):
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == self.pid and user32.IsWindowVisible(hwnd):
                    found.append(hwnd)
                return True

            user32.EnumWindows(EnumProc(_cb), 0)
            if not found:
                self.log("window move skipped: no visible window for pid")
                return

            class _RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            hwnd = found[0]
            rect = _RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                self.log("window move skipped: degenerate window rect")
                return
            # 0x0004 = SWP_NOZORDER; primary monitor origin is (0, 0)
            ok = user32.SetWindowPos(hwnd, None, 60, 60, w, h, 0x0004)
            self.log(f"moved emulator window to primary (60,60 {w}x{h}) "
                     f"ok={bool(ok)}")
        except Exception as exc:
            self.log(f"window move skipped: {exc}")

    def _attach(self):
        deadline = time.time() + self.attach_timeout
        last = None
        while time.time() < deadline:
            try:
                self.g = Gdb("127.0.0.1", self.port, timeout=6)
                break
            except OSError as exc:
                last = exc
                time.sleep(1.0)
        if self.g is None:
            raise FixtureError(f"GDB stub never came up on port {self.port}: {last}")
        stop = self._halt()
        self.log(f"attached, halted ({stop})")
        return stop

    def _halt(self, timeout=20.0):
        """Poll for a stop reply.

        mGBA may deliver the synchronous stop packet on connect, on the first
        `?`, or only after `\x03`; which one varies between launches. Short
        polling reads avoid losing it to a long blocking recv.
        """
        g = self.g
        g.sock.settimeout(1.0)
        deadline = time.time() + timeout
        nudge = 0
        try:
            while time.time() < deadline:
                try:
                    stop = g.interrupt()
                    if stop:
                        return stop
                except Exception:
                    pass
                nudge += 1
                if nudge % 3 == 0:
                    # Release a `-g` launch pause once in a while; harmless when
                    # the emulator is already running.
                    try:
                        g.send("c", expect_reply=False)
                    except Exception:
                        pass
                time.sleep(0.25)
        finally:
            if self.g is not None:
                g.sock.settimeout(6.0)
        raise FixtureError(f"no stop reply within {timeout:.0f}s of attach")

    # -- writes (the only path experiments may use) ------------------------
    def write_bytes(self, addr, data, note=""):
        """Write memory and record a receipt (old/new/addr/width/note)."""
        g = self.g
        old = g.read_mem(addr, len(data))
        hexs = data.hex()
        reply = g.send(f"M{addr:x},{len(data)}:{hexs}")
        new = g.read_mem(addr, len(data))
        entry = {
            "addr": f"{addr:08x}",
            "width": len(data),
            "old": old.hex() if old else None,
            "new": new.hex() if new else None,
            "requested": hexs,
            "reply": reply,
            "note": note,
        }
        self.writes.append(entry)
        self.log(f"  write {entry['addr']} {entry['old']} -> {entry['new']} ({note})")
        return entry

    def write_u8(self, addr, value, note=""):
        return self.write_bytes(addr, bytes([value & 0xFF]), note)

    # -- misc --------------------------------------------------------------
    def screenshot(self, path):
        if not self.pid:
            return None
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        script = os.path.join(REPO, "tools", "capture_window.ps1")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", script, "-ProcId", str(self.pid), "-Out", path],
                       capture_output=True, text=True, timeout=45)
        return path

    def stop(self, keep_process=False, wait=15.0):
        if self.g is not None:
            try:
                self.g.send("c", expect_reply=False)
            except Exception:
                pass
            try:
                self.g.close()
            except Exception:
                pass
            self.g = None
        if self.proc is not None and not keep_process:
            # Own process only: never `taskkill /IM mgba.exe`.
            subprocess.run(["taskkill", "/F", "/PID", str(self.pid)],
                           capture_output=True, timeout=30)
            deadline = time.time() + wait
            while time.time() < deadline:
                if self.proc.poll() is not None and \
                        port_listener_pid(self.port) is None:
                    break
                time.sleep(0.5)
            self.log(f"terminated owned pid {self.pid} "
                     f"(port {self.port} "
                     f"{'free' if port_listener_pid(self.port) is None else 'STILL HELD'})")
        self.proc = None
        self.pid = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False

    def summary(self):
        return {
            "state": self.state,
            "rom": self.rom,
            "rom_sha1": self.rom_sha1,
            "emulator": self.emulator,
            "port": self.port,
            "pid": self.pid,
            "work_paths": self.work_paths,
            "guard": self.receipt,
            "writes": self.writes,
        }


def write_receipt(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        json.dump(payload, fh, indent=1, default=str)
    return path
