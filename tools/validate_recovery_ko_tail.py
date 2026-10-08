"""Execute retail zero-HP accessors and turn-tail branches; bounded ROM proof.

Synthetic controls distinguish status bits from HP and pending tail flags.
Optional captured canonical unit bytes are read without editing the capture.
This does not certify live scheduling, Life targeting or a reusable KO fixture.
"""
import argparse
import hashlib
import json
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC

from emulate import Gba
from status_flags import STATUS_FLAGS

UNIT = 0x02002000
FLAGS = 0x02003000
TAIL = 0x0809E7FE
DESTINATIONS = {0x0809E1F8: 'living-loop', 0x0809E246: 'zero-HP-skip',
                0x0809E81E: 'pending-tail-return'}


def exercise(rom, unit_bytes, pending=0):
    gba = Gba(rom)
    gba.uc.mem_write(UNIT, unit_bytes)
    gba.write32(FLAGS, pending)
    zero = gba.call(0x080C8280, [UNIT])
    battle_zombie = gba.call(0x08131030, [UNIT])
    petrify = next(s for s in STATUS_FLAGS if s['name'] == 'petrify')
    auto = next(s for s in STATUS_FLAGS if s['name'] == 'auto_life')
    pet = gba.call(petrify['getter'], [UNIT])
    auto_life = gba.call(auto['getter'], [UNIT])
    destinations = []
    def stop_at_branch(uc, address, size, data):
        if address in DESTINATIONS:
            destinations.append(address)
            uc.emu_stop()
    hook = gba.uc.hook_add(UC_HOOK_CODE, stop_at_branch)
    gba.run_range(TAIL, 0x0809E82E, {'r4': UNIT, 'r7': 0, 'sl': FLAGS}, timeout_insns=100)
    gba.uc.hook_del(hook)
    assert len(destinations) == 1, ('tail failed to reach observed branch', gba.uc.reg_read(UC_ARM_REG_PC))
    return {'zero_hp': zero, 'battle_zombie': battle_zombie, 'petrify': pet,
            'auto_life': auto_life, 'pending_flags': pending,
            'destination': f'{destinations[0]:08x}', 'branch': DESTINATIONS[destinations[0]]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--members', help='Optional exact 14-unit canonical capture (local binary)')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    cases = []
    petrify = next(s for s in STATUS_FLAGS if s['name'] == 'petrify')
    auto = next(s for s in STATUS_FLAGS if s['name'] == 'auto_life')
    zombie = next(s for s in STATUS_FLAGS if s['name'] == 'zombie')
    for name, hp, statuses, persistent, pending, expected in (
            ('living', 100, (), 0, 0, 'living-loop'),
            ('KO', 0, (), 0, 0, 'zero-HP-skip'),
            ('living-Petrify', 100, (petrify,), 0, 0, 'living-loop'),
            ('KO-Petrify', 0, (petrify,), 0, 0, 'zero-HP-skip'),
            ('living-Auto-Life', 100, (auto,), 0, 0, 'living-loop'),
            ('KO-Auto-Life', 0, (auto,), 0, 0, 'zero-HP-skip'),
            ('living-Zombie', 100, (zombie,), 0, 0, 'living-loop'),
            ('KO-Zombie', 0, (zombie,), 0, 0, 'zero-HP-skip'),
            ('KO-persistent-Zombie', 0, (), 0x0800, 0, 'zero-HP-skip'),
            ('KO-pending-tail', 0, (), 0, 0x2000, 'pending-tail-return'),
            ('living-pending-tail', 100, (), 0, 0x2000, 'living-loop')):
        unit = bytearray(0x108)
        unit[0x18:0x1C] = hp.to_bytes(2, 'little') + (100).to_bytes(2, 'little')
        unit[0x28:0x2A] = persistent.to_bytes(2, 'little')
        for status in statuses:
            unit[status['offset']] |= status['mask']
        observed = exercise(args.rom, bytes(unit), pending)
        assert observed['branch'] == expected and observed['zero_hp'] == int(hp == 0), name
        assert observed['petrify'] == int(petrify in statuses), name
        assert observed['auto_life'] == int(auto in statuses), name
        assert observed['battle_zombie'] == int(zombie in statuses or persistent != 0), name
        cases.append({'name': name, 'hp': hp, **observed})
    captures = []
    if args.members:
        data = Path(args.members).read_bytes()
        assert len(data) == 14 * 0x108, 'short canonical capture'
        for index in range(14):
            unit = data[index*0x108:(index+1)*0x108]
            if int.from_bytes(unit[:4], 'little') and unit[0x104] in (5, 7):
                captures.append({'canonical': f'{0x02000080+index*0x108:08x}', 'id': unit[0x104],
                                 'hp': int.from_bytes(unit[0x18:0x1A], 'little'),
                                 'unit_sha256': hashlib.sha256(unit).hexdigest(),
                                 **exercise(args.rom, unit)})
        assert len(captures) == 2 and {c['id'] for c in captures} == {5, 7}, 'capture identity alias'
    sources = ['tools/validate_recovery_ko_tail.py', 'tools/emulate.py', 'tools/status_flags.py']
    result = {'status': 'pass-bounded-ROM-tail', 'scope': __doc__,
              'rom_sha256': hashlib.sha256(Path(args.rom).read_bytes()).hexdigest(),
              'source_sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources},
              'cases': cases, 'capture': args.members,
              'capture_sha256': hashlib.sha256(Path(args.members).read_bytes()).hexdigest() if args.members else None,
              'captured_units': captures,
              'limitations': ['This fragment begins after Zombie countdown and pending-flag construction.',
                              'Pending 0x2000 is a conditional tail branch, not a complete revival claim.',
                              'No fresh live scheduling, accepted Life target or reusable fixture proof.']}
    Path(args.out).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(f'PASS bounded ROM tail: {len(cases)} controls, {len(captures)} captured units')


if __name__ == '__main__':
    main()
