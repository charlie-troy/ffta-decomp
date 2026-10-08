"""Execute the native action-set helper on a retained KO-fixture caster.

Synthetic replay only: this does not open a live menu or establish Life legality.
"""
import argparse
import hashlib
import json
from pathlib import Path

from unicorn import UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_PC

from emulate import Gba, STOP


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture', default='outputs/autobattle/a64-life-groups-01')
    ap.add_argument('--rom', default='baserom.gba')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    directory = Path(args.capture)
    doc = json.loads((directory/'Life-menu.json').read_text())
    raw_path = directory/'action-group-ewram.bin'
    raw = raw_path.read_bytes()
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    assert sha(raw_path) == doc['capture_sha256'][raw_path.name]
    assert sha(args.rom) == doc['source_sha256'][args.rom]
    assert len(raw) == 0x40000 and doc['status'] == 'pass-action-group-observation'
    address = doc['menu']['member']
    offset = address-0x02000000
    original = raw[offset:offset+0x108]
    assert original[0x104] == doc['owner']['id'] == 5
    assert original[6:9] == bytes((1, 5, 7)) and original[0x36] == 1
    gba = Gba(args.rom)
    primary_property = gba.call(0x080C8570, [original[5], original[7], 0x0C])
    assert gba.uc.reg_read(UC_ARM_REG_PC) == STOP and primary_property == 24
    assert original[0x35] == 10
    property_value = gba.call(0x080C8570, [7, 7, 0x0C])
    assert gba.uc.reg_read(UC_ARM_REG_PC) == STOP and property_value == 9
    observations = []
    for label, secondary_job, ability_set in (
            ('captured', 7, 1), ('job-only-control', 0, 1),
            ('native-property-synthetic', 7, property_value)):
        unit = bytearray(original)
        unit[8], unit[0x36] = secondary_job, ability_set
        gba.uc.mem_write(address, bytes(unit))
        reads = []
        def observed_read(uc, access, at, size, value, user):
            if address <= at < address+len(unit):
                reads.append({'pc': f'{uc.reg_read(UC_ARM_REG_PC):08x}',
                              'offset': at-address, 'size': size})
        hook = gba.uc.hook_add(UC_HOOK_MEM_READ, observed_read)
        try:
            pointer = gba.call(0x080CCE60, [address, 2, 0x0203E000, 0x0203E001])
        finally:
            gba.uc.hook_del(hook)
        assert gba.uc.reg_read(UC_ARM_REG_PC) == STOP
        bounds = list(gba.uc.mem_read(0x0203E000, 2))
        assert any(r['offset'] == 8 and r['pc'] == '080cceac' for r in reads)
        assert any(r['offset'] == 0x36 and r['pc'] == '080ccecc' for r in reads)
        observations.append({'label': label, 'secondary_job': secondary_job,
            'ability_set': ability_set, 'table_pointer': f'{pointer:08x}',
            'returned_bounds': bounds, 'unit_reads': reads})
    assert observations[0]['returned_bounds'] == observations[1]['returned_bounds'] == [1, 15]
    assert observations[2]['returned_bounds'] == [58, 68]
    assert observations[0]['table_pointer'] == '0851bae4'
    assert observations[2]['table_pointer'] == '0851bb64'
    life_entry = bytes(gba.uc.mem_read(0x0851BB64+62*8, 8))
    assert int.from_bytes(life_entry[4:6], 'little') == 5
    result = {'status': 'pass-synthetic-secondary-action-set-dependency',
        'scope': __doc__, 'helper': '080cce60', 'property_accessor': '080c8570',
        'secondary_job_property_0c': property_value, 'observations': observations,
        'primary_ability_state': {'captured_plus35': original[0x35],
                                 'native_job_property0c': primary_property},
        'Life_entry': {'index': 62, 'global_id': 5},
        'next': 'Prepare disposable canonical and mirror +0x36 using the native property; independently reload and observe the live menu before claiming availability.',
        'limitations': ['Synthetic unit mutation under Unicorn only; no new live inputs.',
                        'The rendered/canonical HP mismatch remains unresolved.',
                        'No enabled Life, target acceptance or revival claim.'],
        'source_sha256': {p: sha(p) for p in ('tools/validate_recovery_action_set.py', 'tools/emulate.py', args.rom)},
        'evidence_sha256': {str(p): sha(p) for p in (raw_path, directory/'Life-menu.json')}}
    Path(args.out).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print('PASS native secondary action-set dependency: 3 isolated cases; live Life UNKNOWN')


if __name__ == '__main__':
    main()
