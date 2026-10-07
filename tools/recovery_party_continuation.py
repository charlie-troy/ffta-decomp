"""Read-only next-actor attribution for the bounded eight-unit recovery fixture.

Requires restored roster, canonical driver/wrapper and actor-owned cursor.
Party identities remain pinned; subsequent enemy damage is reported separately
from the already observed Cure effect. No input or transport control lives here.
"""
import hashlib

from fixture_guard import read_roster, ROSTER, STRIDE
from recovery_menu import exact, integer, require, PLAYER_DRIVER
from recovery_ally_target import canonical_facts

IDENTITY_FIELDS = ('name','id','type','base_job','race','job','level','side_raw')


def observe_party_continuation(g,rom,owner,facing,pins,units,baseline):
    roster=read_roster(g,rom=rom)
    rows=[r for r in roster['slots'] if r['live']]
    require(roster['struct_count'] == roster['live_count'] == 8
            and roster['ids_distinct'] and roster['live_contiguous']
            and {r['id'] for r in rows} == set(range(8)), 'party continuation roster not restored')
    require(len(baseline) == 8 and len({r['id'] for r in baseline}) == 8, 'missing baseline roster')
    originals={r['id']:r for r in baseline}
    for row in rows:
        require(all(row[f] == originals[row['id']][f] for f in IDENTITY_FIELDS),
                'continuation roster identity drift')
    driver=exact(g,PLAYER_DRIVER,0x64)
    wrapper=integer(driver,4)
    require(wrapper == integer(driver,8) and wrapper != facing['actor_wrapper'], 'actor not independently changed')
    wrapper_bytes=exact(g,wrapper,4)
    member=integer(wrapper_bytes,0)
    require(member != facing['member'], 'completed caster still active')
    unit=exact(g,member,STRIDE)
    matches=[r for r in rows if r['id'] == unit[0x104] and r['name'] == integer(unit,0)]
    require(len(matches) == 1, 'next actor missing or ambiguous')
    actor=matches[0]
    reads=[(PLAYER_DRIVER,driver),(wrapper,wrapper_bytes),(member,unit)]
    fields=[('type',4,1),('base_job',5,1),('race',6,1),('job',7,1),('level',9,1),
            ('hp',0x18,2),('max_hp',0x1A,2),('mp',0x1C,2),('max_mp',0x1E,2),('side_raw',0x28,2)]
    require(all(actor[f] == integer(unit,o,s) for f,o,s in fields), 'next canonical/mirror mismatch')
    tile=exact(g,ROSTER+STRIDE*actor['slot']+0xF6,2)
    cursor=exact(g,0x0200FFC9,2)
    require(tile == unit[0xF6:0xF8] == cursor and all(v<64 for v in tile), 'next actor cursor mismatch')
    require(actor['id'] != owner['id'] and not actor['unaffiliated']
            and 0 < actor['hp'] <= actor['max_hp'] <= 999
            and 0 <= actor['mp'] <= actor['max_mp'] <= 999, 'next actor outside bounds')
    reads.extend([(ROSTER+STRIDE*actor['slot']+0xF6,tile),(0x0200FFC9,cursor)])
    party=[]
    for pin in pins:
        address=pin['canonical'];current=exact(g,address,STRIDE)
        facts,original=canonical_facts(current),canonical_facts(units[address])
        require(all(a == b for i,(a,b) in enumerate(zip(facts,original)) if i not in (7,9)),
                'completed party identity changed')
        row=next(r for r in rows if r['id'] == pin['id'])
        require(all(row[f] == integer(current,o,s) for f,o,s in fields), 'party canonical/mirror mismatch')
        require(list(current[0xF6:0xF8]) == pin['tile']
                and 0 < integer(current,0x18,2) <= pin['max_hp']
                and 0 <= integer(current,0x1C,2) <= pin['max_mp'], 'party resources or tile outside bounds')
        name_address=integer(current,0)
        name=(rom[name_address-0x08000000:name_address-0x08000000+32]
              if 0x08000000 <= name_address < 0x08000000+len(rom) else exact(g,name_address,32))
        require(hashlib.sha256(name).hexdigest() == pin['name_sha256'], 'party name content changed')
        reads.append((address,current))
        party.append({'id':pin['id'],'canonical':address,'hp':integer(current,0x18,2),
                      'mp':integer(current,0x1C,2),'tile':pin['tile']})
    require(all(exact(g,a,len(data)) == data for a,data in reads), 'next actor changed during observation')
    repeated=read_roster(g,rom=rom)
    require(repeated == roster, 'restored roster changed during observation')
    return {'source':'canonical driver / restored eight-unit roster / own cursor',
            'wrapper':wrapper,'canonical':member,'actor':actor | {'tile':list(tile)},
            'relation':'enemy' if actor['side_bit'] else 'ally','party_after':party}
