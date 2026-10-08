"""Replay the retained Life list and reject stale/foreign input tokens."""
import argparse
import hashlib
import json
from pathlib import Path

from ability_resources import effective_mp_cost
from recovery_menu import MEMBERS, STRIDE, PLAYER_DRIVER, RecoveryStateError
from recovery_menu_list import ResearchMenuList


class Memory:
    def __init__(self, data):
        self.data = bytearray(data)

    def read_mem(self, address, size):
        offset = address-0x02000000
        return bytes(self.data[offset:offset+size]) if 0 <= offset <= len(self.data)-size else None

    def write(self, address, data):
        offset = address-0x02000000
        self.data[offset:offset+len(data)] = data


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture', required=True)
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    directory = Path(args.capture)
    doc = json.loads((directory/'Life-menu.json').read_text())
    assert doc['status'] == 'pass-enabled-Life-and-cost' and doc['inputs_unchanged']
    for name, digest in doc['capture_sha256'].items():
        assert hashlib.sha256((directory/name).read_bytes()).hexdigest() == digest
    data = (directory/'ewram.bin').read_bytes()
    rom = Path(args.rom).read_bytes()
    assert len(data) == 0x40000
    caster = next(p for p in doc['party'] if p['id'] == doc['owner']['id'])
    memory = Memory(data)
    menu = ResearchMenuList(memory, rom, doc['owner'], caster['canonical'])
    token = menu.snapshot()
    assert json.loads(json.dumps(token.receipt())) == doc['menu']
    index = token.ability_ids.index(5)
    assert token.ability_ids.count(5) == 1 and token.enabled[index] == 1
    unit = memory.read_mem(caster['canonical'], STRIDE)
    assert effective_mp_cost(rom, 5, unit) == doc['life']['actual_ROM_cost'] == doc['life']['effective_cost']
    rejected = []
    def reject(label, address, changed):
        g = Memory(data)
        reader = ResearchMenuList(g, rom, doc['owner'], caster['canonical'])
        original = reader.snapshot()
        g.write(address, changed)
        try:
            reader.revalidate(original)
        except (RecoveryStateError, ValueError):
            rejected.append(label)
        else:
            raise AssertionError('accepted stale Life list token: '+label)
    for label, offset, changed in (
            ('KO-caster', 0x18, b'\0\0'), ('MP-change', 0x1C, b'\0\0'),
            ('race', 6, b'\x02'), ('job', 7, b'\x06'), ('secondary', 8, b'\0'),
            ('id', 0x104, b'\x2a'), ('name', 0, b'\0'*4), ('tile', 0xF6, b'\x3f'),
            ('enemy', 0x29, b'\x80'), ('unaffiliated', 0x29, b'\x10')):
        reject(label, caster['canonical']+offset, changed)
    for label, address, changed in (
            ('foreign-menu-member', menu.context+0x18, MEMBERS.to_bytes(4, 'little') if caster['canonical'] != MEMBERS else (MEMBERS+STRIDE).to_bytes(4,'little')),
            ('manager', menu.context+0x20, b'\0'*4), ('callback', menu.context+0x28, b'\0'*4),
            ('driver-owner', PLAYER_DRIVER+4, b'\0'*4), ('driver-peer', PLAYER_DRIVER+8, b'\0'*4),
            ('target-processor', PLAYER_DRIVER+0x60, b'\x01\x00\x00\x02'),
            ('cached-callback', menu.manager+4, b'\0'*4), ('handler', menu.callback, b'\0'*4),
            ('initializing-list', menu.callback+0x14, b'\0\x01'),
            ('opening-list', menu.callback+0x14, b'\x01\x01'),
            ('final-prompt-mode', menu.context+4, b'\x0b')):
        reject(label, address, changed)
    obj = menu.callback+0x18
    row_pointer = int.from_bytes(memory.read_mem(obj+0x94, 4), 'little')
    enable_pointer = int.from_bytes(memory.read_mem(obj+0x98, 4), 'little')
    for label, address, changed in (
            ('cursor', obj+0x69, b'\xff'), ('count-zero', obj+0x50, b'\0\0'),
            ('scroll', obj+0x52, b'\xff\xff'), ('row-pointer', obj+0x94, b'\0'*4),
            ('enable-pointer', obj+0x98, b'\0'*4), ('disabled-Life', enable_pointer+index, b'\0'),
            ('invalid-enable', enable_pointer+index, b'\x02'), ('foreign-ability-row', row_pointer+index*4, b'\xff'*4)):
        reject(label, address, changed)
    alias = MEMBERS+13*STRIDE
    reject('canonical-name-alias', alias, doc['owner']['name'].to_bytes(4, 'little'))
    reject('canonical-id-alias', alias+0x104, bytes([doc['owner']['id']]))
    result = {'status': 'pass-retained-Life-list-guards', 'scope': __doc__, 'rejected': rejected,
              'life': doc['life'], 'source_sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (
                  'tools/validate_recovery_life_menu.py', 'tools/recovery_menu_list.py',
                  'tools/recovery_menu.py', 'tools/ability_resources.py')},
              'evidence_sha256': {str(directory/name): hashlib.sha256((directory/name).read_bytes()).hexdigest()
                                  for name in ('Life-menu.json', 'ewram.bin')},
              'limitations': ['Retained list guards only; no Life target or final-input authority.']}
    Path(args.out).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(f'PASS retained Life list: {len(rejected)} rejected mutations')


if __name__ == '__main__':
    main()
