"""Read-only A5.1 identity adapter for the verified fresh player menu.

Cursor ownership is evidence only at a fresh menu, before targeting input.
CT stability corroborates the menu; its numeric value never names an actor.
"""
from fixture_guard import read_roster, u8, ROSTER, STRIDE


class IdentityError(ValueError):
    pass


def key(row):
    return row.get("name_text"), row.get("id")


def players(roster):
    return [r for r in roster["slots"] if r.get("live")
            and r.get("side_bit") is False and not r.get("unaffiliated")
            and r.get("type") != 20]


class ActorAdapter:
    def __init__(self, session):
        self.s = session
        self.expected = players(session.receipt["roster"])
        if not self.expected:
            raise IdentityError("no verified player identities")
        self._validate_keys(session.receipt["roster"]["slots"])
        self.prior = None
        self.last_rejection = None

    @staticmethod
    def _validate_keys(rows):
        live = [r for r in rows if r.get("live")]
        keys = [key(r) for r in live]
        ids = [r.get("id") for r in live]
        if any(not n or i is None or not 0 <= i < 255 for n, i in keys):
            raise IdentityError("missing identity")
        if len(set(keys)) != len(keys) or len(set(ids)) != len(ids):
            raise IdentityError("duplicate identity or unit id")

    def snapshot(self):
        roster = read_roster(self.s.g, rom=self.s.read_rom_bytes())
        if roster["struct_count"] not in (7, 8):
            raise IdentityError("roster outside verified fixture bounds")
        self._validate_keys(roster["slots"])
        rows = []
        for expected in self.expected:
            matches = [r for r in roster["slots"] if key(r) == key(expected)]
            if len(matches) != 1:
                raise IdentityError("missing or ambiguous player identity")
            row = dict(matches[0])
            for field in ("job", "base_job", "race", "type", "level",
                          "side_bit", "unaffiliated"):
                if row.get(field) != expected.get(field):
                    raise IdentityError("player identity/job/side changed")
            base = ROSTER + STRIDE * row["slot"]
            row["x"], row["y"] = u8(self.s.g, base + 0xF6), u8(self.s.g, base + 0xF7)
            if (row["hp"] is None or row["max_hp"] is None
                    or not 0 <= row["hp"] <= row["max_hp"] <= 999
                    or row["mp"] is None or row["max_mp"] is None
                    or not 0 <= row["mp"] <= row["max_mp"] <= 999
                    or row["ct"] is None or not 0 <= row["ct"] <= 1500
                    or row["x"] is None or row["y"] is None
                    or not 0 <= row["x"] < 64 or not 0 <= row["y"] < 64):
                raise IdentityError("invalid player stats or tile")
            rows.append(row)
        return rows

    def observe(self, probe, rows):
        """Two consecutive fresh-menu observations; no CT fallback."""
        cursor = probe.read_target_cursor()
        command = probe.read_cmd_cursor()
        matches = [r for r in rows if r["hp"] > 0 and r["max_hp"] > 0
                   and (r["x"], r["y"]) == cursor and cursor != (0, 0)]
        if len(matches) != 1 or command not in (0, 1, 2):
            self.prior = None
            self.last_rejection = "fresh-menu owner rejected: ambiguous/missing cursor match or unknown command"
            return None
        self.last_rejection = None
        row = matches[0]
        observation = (key(row), row["job"], row["side_bit"],
                       row["x"], row["y"], row["ct"], command)
        owner = row if self.prior == observation and row["ct"] != 1000 else None
        self.prior = observation
        return owner

    def revalidate(self, owner, probe):
        rows = self.snapshot()
        matches = [r for r in rows if key(r) == key(owner)]
        if len(matches) != 1:
            raise IdentityError("owner disappeared")
        row = matches[0]
        if any(row[f] != owner[f] for f in ("slot", "ct", "x", "y", "job", "side_bit")):
            raise IdentityError("stale fresh-menu owner")
        if row["hp"] <= 0 or probe.read_target_cursor() != (row["x"], row["y"]):
            raise IdentityError("owner no longer owns the fresh menu")
        return rows

    @staticmethod
    def result(owner, pre, post, kind, dest):
        """Independent full-party tile cross-check, before enemy progress."""
        before, after = {key(r): r for r in pre}, {key(r): r for r in post}
        if set(before) != set(after):
            raise IdentityError("result identity set changed")
        moved = [k for k in before if (before[k]["x"], before[k]["y"])
                 != (after[k]["x"], after[k]["y"])]
        actor = key(owner)
        if kind == "identified-move":
            if (moved != [actor] or dest is None
                    or (after[actor]["x"], after[actor]["y"]) != tuple(dest)):
                raise IdentityError("move result belongs to wrong actor/destination")
        elif kind == "identified-wait":
            if moved:
                raise IdentityError("Wait result moved a player")
        else:
            raise IdentityError("unsupported result")
        return {"verified": True, "moved_actors": [list(k) for k in moved],
                "players_before": pre, "players_after": post}
