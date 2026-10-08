"""Bounded Life effect and native level-up attribution; no input authority."""
import hashlib

from fixture_guard import STRIDE
from recovery_menu import integer, require


def validate_life_fixture(party,units):
    """Reject a different research family before opening Action or sending input."""
    require(len(party)==2 and {p['id'] for p in party}=={5,7},'Life fixture party differs')
    roles={p['id']:p for p in party}
    require(roles[5]['canonical']==0x02000188 and roles[7]['canonical']==0x02000080
            and roles[5]['tile']==[5,10] and roles[7]['tile']==[4,10], 'Life fixture identity/tile differs')
    require(set(units)=={0x02000188,0x02000080} and all(len(u)==STRIDE for u in units.values()),
            'Life fixture unit captures differ')
    c,t=units[0x02000188],units[0x02000080]
    for pin in party:
        u=units[pin['canonical']]
        require(integer(u,0)==pin['name'] and u[0x104]==pin['id'] and u[5:8]==bytes((5,1,5))
                and integer(u,0x28,2)&0x9000==0 and list(u[0xF6:0xF8])==pin['tile']
                and not any(pin['statuses'].values()), 'Life fixture raw identity/status differs')
    require(c[4]==8 and c[8:11]==bytes((7,40,99)) and c[0x35:0x37]==bytes((24,9))
            and c[0x3B]==30 and c[0xF2]==0
            and [integer(c,o,2) for o in (0x18,0x1A,0x1C,0x1E)]==[241,241,221,221],
            'Life fixture caster resources/level/ability-state differ')
    require(t[4]==2 and t[9]==50 and t[0xF2]==2
            and [integer(t,o,2) for o in (0x18,0x1A,0x1C,0x1E)]==[0,442,85,85],
            'Life fixture genuine KO counter/resources/level differ')
    return {'status':'accepted-exact-Life-fixture','caster':5,'target':7,'cost':10,
            'level':40,'exp':99,'ability_sets':[24,9]}


def verify_life_effect(before, after, hits, caster, target):
    """Accept this EXP-99 fixture only with a paired native level-up witness."""
    require(set(before) == set(after), 'Life canonical capture set differs')
    c, t = caster['canonical'], target['canonical']
    cb, ca, tb, ta = before[c], after[c], before[t], after[t]
    require(all(len(u) == STRIDE for u in (*before.values(), *after.values())), 'short Life unit')
    require(cb[9] == 40 and cb[10] == 99 and integer(tb,0x18,2) == 0,
            'Life effect fixture differs')
    relevant = lambda phase: [h for h in hits if h['phase']==phase and h.get('unit',{}).get('canonical')==c]
    awards, starts, ends = [relevant(p) for p in ('EXP-award','level-up-before','level-up-after')]
    require(len(awards)==len(starts)==len(ends)==1, 'Life level-up witness missing or repeated')
    award, start, end = awards[0], starts[0], ends[0]
    require(award['t'] <= start['t'] <= end['t'] and award['old_exp']==99
            and 0 < award['awarded_exp'] <= 100 and 99+award['awarded_exp']>99,
            'Life EXP award attribution differs')
    require(start['caller_lr']=='080a71c5' and end['level_up_result']==1,
            'Life level-up call/return differs')
    entry, returned = bytes.fromhex(start['unit_hex']), bytes.fromhex(end['unit_hex'])
    require(len(entry)==len(returned)==STRIDE, 'short native level-up witness')
    expected = bytearray(cb)
    expected[10] = 0  # reward caller resets EXP before 080C9B8C
    expected[0x1C:0x1E] = (integer(cb,0x1C,2)-10).to_bytes(2,'little')
    require(entry[0xF8] in (cb[0xF8],1), 'unobserved caster height transition')
    expected[0xF8] = entry[0xF8]
    require(entry == bytes(expected), 'pre-level-up unit changed outside Life cost/EXP/height')
    awarded_unit=bytearray(entry);awarded_unit[10]=99
    require(bytes.fromhex(award['unit_hex'])==bytes(awarded_unit),'EXP award unit differs from level-up entry')
    growth = {9,10,*range(0x1A,0x1C),*range(0x1E,0x28),0xD2,0xD3}
    differences = [i for i,(a,b) in enumerate(zip(entry,returned)) if a!=b]
    require(set(differences) <= growth and returned[9]==41 and returned[10]==0,
            'native level-up changed an unexpected field')
    for offset in (0x1A,0x1E,0x20,0x22,0x24,0x26,0xD2):
        require(integer(entry,offset,2) <= integer(returned,offset,2) <= 999,
                'native growth resource/stat bounds differ')
    require(ca == returned, 'caster changed after native level-up return')
    hp_before = [h for h in hits if h['phase']=='HP-store-before' and h.get('unit',{}).get('canonical')==t]
    hp_after = [h for h in hits if h['phase']=='HP-store-after' and h.get('unit',{}).get('canonical')==t]
    require(len(hp_before)==len(hp_after)==1, 'Life target HP store pair missing/repeated')
    first, last = hp_before[0],hp_after[0]
    require(first['t'] <= last['t'] <= award['t'] and first['unit']['hp']==0
            and first['stored_hp']==last['stored_hp']==last['unit']['hp']==221,
            'Life target HP attribution differs')
    for witness in (first,last):
        require(all(witness['unit'][key]==value for key,value in
                    [('id',tb[0x104]),('name',integer(tb,0)),('mp',integer(tb,0x1C,2)),
                     ('ko_suffered',tb[0xF2])]),'Life target HP-store identity differs')
    effects=[h for h in hits if h['phase'] in ('Life-effect-entry','Life-effect-flags-written')]
    require(len(effects)==2 and [h['phase'] for h in effects]==['Life-effect-entry','Life-effect-flags-written']
            and effects[0]['flags'] & 0x20 == 0
            and effects[1]['flags'] == effects[0]['flags'] | 0x20
            and all(h['context_words']==[c,t,t] for h in effects)
            and last['t']<=effects[0]['t']<=effects[1]['t']<=award['t'],
            'native Life result context/flags attribution differs')
    expected_target = bytearray(tb); expected_target[0x18:0x1A]=(221).to_bytes(2,'little')
    require(ta == bytes(expected_target), 'Life target changed outside attributed HP store')
    for address, unit in before.items():
        if address not in (c,t):
            require(after[address] == unit, 'Life changed another canonical unit')
    return {'status':'bounded-Life-effect-and-native-level-up', 'target_hp':[0,221],
            'caster_mp':[integer(cb,0x1C,2),integer(ca,0x1C,2)],
            'level':[40,41], 'awarded_exp':award['awarded_exp'],
            'native_growth_offsets':differences,
            'caster_after_sha256':hashlib.sha256(ca).hexdigest(),
            'target_after_sha256':hashlib.sha256(ta).hexdigest()}
