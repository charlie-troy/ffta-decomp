"""Read-only terminal evidence; observations never authorize input or completion."""
from fixture_guard import BATTLE_STRUCT, ROSTER, STRIDE
from recovery_menu import MEMBERS, MEMBER_COUNT, integer, exact


def capture_boundary_diagnostic(g, probe):
    blocks = {}
    struct_raw = exact(g, BATTLE_STRUCT, 4)
    mirror_snapshots = []
    for label, address, count in [('mirror', ROSTER, 8), ('canonical', MEMBERS, MEMBER_COUNT)]:
        players = []
        for index in range(count):
            # Stay below mGBA's RSP reply limit; a whole canonical array
            # exceeds it and can yield an unusable prefix.
            unit = exact(g, address + index * STRIDE, STRIDE)
            if label == 'mirror':
                mirror_snapshots.append({'address':address + index * STRIDE, 'raw':unit.hex()})
            if unit[0x104] not in (5, 7) or integer(unit, 0) == 0:
                continue
            players.append({'address': address + index * STRIDE, 'raw': unit.hex(),
                'id': unit[0x104], 'name': integer(unit, 0),
                'hp': integer(unit, 0x18, 2), 'mp': integer(unit, 0x1C, 2),
                'status_EB': unit[0xEB], 'sleep': bool(unit[0xEB] & 4),
                'sleep_duration': unit[0xDF]})
        blocks[label] = players
    return {'scope': __doc__, 'party': blocks, 'target_cursor': probe.read_target_cursor(),
            'command_cursor': probe.read_cmd_cursor(),
            'structure':{'address':BATTLE_STRUCT,'raw':struct_raw.hex(),'count':integer(struct_raw,0)},
            'mirror_snapshots':mirror_snapshots,
            'sleep_reader': {'getter': 0x080CDB24, 'offset': 0xEB, 'mask': 4,
                             'duration_offset': 0xDF}}
