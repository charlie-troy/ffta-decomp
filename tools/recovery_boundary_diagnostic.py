"""Read-only terminal evidence; observations never authorize input or completion."""
from fixture_guard import ROSTER, STRIDE
from recovery_menu import MEMBERS, MEMBER_COUNT, integer, exact


def capture_boundary_diagnostic(g, probe):
    blocks = {}
    for label, address, count in [('mirror', ROSTER, 8), ('canonical', MEMBERS, MEMBER_COUNT)]:
        raw = exact(g, address, count * STRIDE)
        if len(raw) != count * STRIDE:
            raise ValueError('short terminal diagnostic ' + label)
        players = []
        for index in range(count):
            unit = raw[index * STRIDE:(index + 1) * STRIDE]
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
            'sleep_reader': {'getter': 0x080CDB24, 'offset': 0xEB, 'mask': 4,
                             'duration_offset': 0xDF}}
