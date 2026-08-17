"""Sample the program counter from a running mGBA and map it to functions.

mGBA exposes a GDB stub (`mgba -g`). Rather than single-stepping, which is far
too slow for a whole game turn, this interrupts repeatedly, reads the PC, and
resumes. The result is a statistical profile: whatever the game is busy doing
shows up as the hot functions.

That is the cheapest way to turn 3,594 anonymous addresses into a short list of
candidates for a subsystem, which is the point of it for AI work.

Usage:
    python tools/trace_mgba.py <manifest.json> [--host H] [--port P]
                               [--samples N] [--interval S] [--out FILE]
"""
import os
import sys
import json
import time
import socket
import argparse
import collections

BASE = 0x08000000


class Gdb:
    """Minimal GDB remote serial protocol client."""

    def __init__(self, host, port, timeout=5.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    @staticmethod
    def _frame(payload):
        csum = sum(payload.encode()) & 0xFF
        return f"${payload}#{csum:02x}".encode()

    def _read_packet(self):
        while True:
            start = self.buf.find(b"$")
            end = self.buf.find(b"#", start + 1)
            if start != -1 and end != -1 and len(self.buf) >= end + 3:
                pkt = self.buf[start + 1:end].decode(errors="replace")
                self.buf = self.buf[end + 3:]
                return pkt
            chunk = self.sock.recv(4096)
            if not chunk:
                raise EOFError("gdb stub closed")
            self.buf += chunk

    def send(self, payload, expect_reply=True):
        self.sock.sendall(self._frame(payload))
        # swallow the '+' ack if present
        try:
            while True:
                if self.buf[:1] == b"+":
                    self.buf = self.buf[1:]
                    break
                if self.buf:
                    break
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self.buf += chunk
        except socket.timeout:
            pass
        if not expect_reply:
            return None
        return self._read_packet()

    def interrupt(self):
        """Halt the CPU and settle the stream.

        The stop reply must be consumed, and querying status afterwards keeps
        replies paired with requests; without it the next 'g' can be answered
        with a stale packet and the PC reads back as zero.
        """
        self.sock.sendall(b"\x03")
        try:
            stop = self._read_packet()
        except (socket.timeout, EOFError):
            return None
        try:
            self.sock.sendall(self._frame("?"))
            self._read_packet()
        except (socket.timeout, EOFError):
            pass
        return stop

    def read_pc(self):
        """ARM 'g' packet: registers as little-endian hex; r15 is the PC.

        Stop replies ('S02') and acks interleave with register dumps, so keep
        reading until a payload long enough to be a register block arrives
        rather than assuming the next packet is the answer.
        """
        data = self.send("g")
        for _ in range(4):
            if data and len(data) >= 16 * 8 and all(c in "0123456789abcdefABCDEF"
                                                    for c in data[:16 * 8]):
                break
            try:
                data = self._read_packet()
            except (socket.timeout, EOFError):
                return None
        else:
            return None
        try:
            return int.from_bytes(bytes.fromhex(data[15 * 8:16 * 8]), "little")
        except ValueError:
            return None

    def cont(self):
        self.sock.sendall(self._frame("c"))


def load_functions(path):
    with open(path) as fh:
        funcs = json.load(fh)
    if isinstance(funcs, dict):
        funcs = funcs.get("functions", [])
    out = []
    for f in funcs:
        addr = f.get("addr") or f.get("address")
        out.append((addr, addr + f["size"], f["name"], f["size"]))
    out.sort()
    return out


def locate(funcs, pc):
    lo, hi = 0, len(funcs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end, name, size = funcs[mid]
        if pc < start:
            hi = mid - 1
        elif pc >= end:
            lo = mid + 1
        else:
            return name
    return None


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("manifest")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    p.add_argument("--samples", type=int, default=400)
    p.add_argument("--interval", type=float, default=0.01)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    funcs = load_functions(args.manifest)
    print(f"manifest: {len(funcs):,} functions")

    gdb = Gdb(args.host, args.port)
    print(f"connected to mGBA gdb stub at {args.host}:{args.port}")

    hits = collections.Counter()
    unknown = collections.Counter()
    iwram = collections.Counter()
    taken = 0
    try:
        for _ in range(args.samples):
            gdb.interrupt()
            pc = gdb.read_pc()
            gdb.cont()
            if pc is None:
                continue
            taken += 1
            name = locate(funcs, pc)
            if name:
                hits[name] += 1
            elif 0x03000000 <= pc < 0x04000000:
                # The game copies hot routines into IWRAM and runs them there,
                # so these samples cannot be attributed from a ROM manifest.
                iwram[pc & ~0xF] += 1
            else:
                unknown[pc & ~0xFF] += 1
            time.sleep(args.interval)
    except (EOFError, socket.timeout, ConnectionError) as exc:
        print(f"stopped early: {exc}")
    finally:
        gdb.close()

    print(f"\nsamples taken: {taken}")
    print(f"  in known ROM functions : {sum(hits.values())}")
    print(f"  in IWRAM (copied code) : {sum(iwram.values())}")
    print(f"  elsewhere              : {sum(unknown.values())}\n")

    print(f"{'hits':>6}  {'%':>6}  function")
    print("-" * 44)
    for name, n in hits.most_common(30):
        print(f"{n:>6}  {100.0*n/max(taken,1):>5.1f}%  {name}")

    if unknown:
        print("\nhot addresses outside any known function (page granularity):")
        for addr, n in unknown.most_common(8):
            print(f"  {addr:#010x}  {n}")

    if args.out:
        with open(args.out, "w", newline="\n") as fh:
            json.dump({"samples": taken,
                       "functions": hits.most_common(),
                       "unknown": [[a, n] for a, n in unknown.most_common()]},
                      fh, indent=1)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
