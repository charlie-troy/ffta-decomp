"""Read-only completion witness for Wait followed by an owned next ally command menu."""
import hashlib
import math

from fixture_guard import BATTLE_STRUCT, ROSTER, STRIDE, read_roster
from recovery_menu import MEMBERS, MENU_ROOT, PLAYER_DRIVER, exact, integer, require
from recovery_menu_list import ResearchMenuList
from recovery_party_continuation import observe_party_continuation

WAIT_COMMAND_ROW=10  # Native table8/9/10/11; cursor index2 is not its row ID.


class CaptureReads:
    def __init__(self,g):self.g,self.reads=g,{}
    def read_mem(self,address,size):
        raw=self.g.read_mem(address,size)
        if raw is not None:
            key=f'{address:08x}:{size:x}';value=bytes(raw).hex()
            require(key not in self.reads or self.reads[key]==value,'Wait continuation changed during observation')
            self.reads[key]=value
        return raw


def capture_wait_origin(session,owner,players,*,clock):
    if len(players)!=2 or {r['id'] for r in players}!={5,7} or any(r['hp']<=0 for r in players):return None
    g=CaptureReads(session.g);rom=session.read_rom_bytes();baseline=read_roster(g,rom=rom)
    require(baseline['struct_count']==baseline['live_count']==8 and baseline['ids_distinct'],
            'Wait origin roster not restored')
    units={a:exact(g,a,STRIDE) for a in (MEMBERS,MEMBERS+STRIDE)};pins=[]
    for address,unit in units.items():
        row=next((r for r in players if r['id']==unit[0x104]),None)
        require(row is not None and row['name']==integer(unit,0) and row['race']==unit[6]
                and row['job']==unit[7] and row['level']==unit[9] and integer(unit,0x28,2)&0x9000==0,
                'Wait origin canonical identity differs')
        name=integer(unit,0);name_bytes=(rom[name-0x08000000:name-0x08000000+32]
            if 0x08000000<=name<=0x08000000+len(rom)-32 else exact(g,name,32))
        pins.append({'canonical':address,'id':unit[0x104],'name':name,
            'name_sha256':hashlib.sha256(name_bytes).hexdigest(),'tile':list(unit[0xF6:0xF8]),
            'hp':integer(unit,0x18,2),'max_hp':integer(unit,0x1A,2),
            'mp':integer(unit,0x1C,2),'max_mp':integer(unit,0x1E,2)})
    require({p['id'] for p in pins}=={5,7},'Wait origin canonical aliases')
    member=next(p['canonical'] for p in pins if p['id']==owner['id'])
    menu=ResearchMenuList(g,rom,owner,member);command=menu.snapshot()
    require(command.state=='command' and command.rows.count(WAIT_COMMAND_ROW)==1
            and command.enabled[command.rows.index(WAIT_COMMAND_ROW)]==1,
            'Wait origin command unavailable')
    return {'captured_t':round(clock(),3),'facing':{'actor_wrapper':menu.wrapper,'member':member},
        'pins':pins,'units':{str(a):u.hex() for a,u in units.items()},'baseline':baseline['slots'],
        'command':command.receipt(),'reads':g.reads}


def inspect_next_ally(session,owner,origin,*,clock):
    require(origin is not None,'no pinned Wait origin')
    g=CaptureReads(session.g);rom=session.read_rom_bytes()
    units={int(a):bytes.fromhex(raw) for a,raw in origin['units'].items()}
    later=observe_party_continuation(g,rom,owner,origin['facing'],origin['pins'],units,origin['baseline'])
    require(later['relation']=='ally','next actor is not another ally')
    menu=ResearchMenuList(g,rom,later['actor'],later['canonical']);command=menu.snapshot()
    require(command.state=='command' and command.rows.count(WAIT_COMMAND_ROW)==1
            and command.enabled[command.rows.index(WAIT_COMMAND_ROW)]==1,
            'next ally command menu not accepting legal Wait')
    current=exact(g,later['canonical'],STRIDE)
    require(not current[0xEB]&4 and not current[0xEA]&0x80 and not current[0xE8]&0x40,
            'next ally has a blocking status')
    for i in range(8):exact(g,ROSTER+i*STRIDE,STRIDE)
    proof={'schema':'ffta-wait-next-ally/1','kind':'next-ally-command-menu','captured_t':round(clock(),3),
        'origin':origin,'next':later,'command':command.receipt(),'reads':g.reads}
    validate_next_ally_progress(proof,owner,None)
    return proof


def raw_frame(reads):
    memory={}
    for key,hexdata in reads.items():
        address,size=(int(v,16) for v in key.split(':'));data=bytes.fromhex(hexdata)
        require(0x02000000<=address<=0x02040000-size and 0<size<=512 and len(data)==size,
                'Wait continuation raw read invalid')
        for offset,value in enumerate(data):
            where=address+offset
            require(where not in memory or memory[where]==value,'Wait continuation overlapping raw reads disagree')
            memory[where]=value
    def read(address,size):
        require(all(address+i in memory for i in range(size)),'Wait continuation raw read missing')
        return bytes(memory[address+i] for i in range(size))
    return read


def validate_next_ally_progress(proof,owner,post_players):
    require(proof['schema']=='ffta-wait-next-ally/1' and proof['kind']=='next-ally-command-menu',
            'Wait next ally evidence schema differs')
    origin=proof['origin'];later=proof['next'];command=proof['command']
    require(all(type(t) in (float,int) and math.isfinite(t) and t>=0 for t in
                (origin['captured_t'],proof['captured_t'])) and origin['captured_t']<=proof['captured_t'],
            'Wait continuation clock differs')
    before=raw_frame(origin['reads']);read=raw_frame(proof['reads'])
    old_member=origin['facing']['member'];old=before(old_member,STRIDE)
    old_driver=before(PLAYER_DRIVER,0xE0);old_wrapper=integer(old_driver,4)
    require(old_wrapper==integer(old_driver,8)==origin['facing']['actor_wrapper']
            and integer(before(old_wrapper,4),0)==old_member
            and old[0x104]==owner['id'] and integer(old,0)==owner['name'],
            'Wait origin wrapper/member not owned')
    for field,offset,size in [('race',6,1),('job',7,1),('level',9,1),('hp',0x18,2),('mp',0x1C,2)]:
        require(owner[field]==integer(old,offset,size),'Wait origin actor fields differ from selection')
    require(bytes.fromhex(origin['units'][str(old_member)])==old,'Wait origin canonical raw differs')
    old_context=integer(before(MENU_ROOT,4),0);old_root=before(old_context,0x30)
    old_callback=integer(old_root,0x28);old_cb=before(old_callback,0x18)
    old_obj=before(old_callback+0x18,0x9C);old_command=origin['command']
    require(old_root[4]==4 and integer(old_root,0x18)==old_member
            and integer(old_cb,0)==0x08028DE1 and integer(old_cb,0x14,2)==0x102
            and integer(old_driver,0xDC,2)==0x25 and integer(old_driver,0x60)==0
            and integer(before(integer(old_root,0x20)+4,4),0)==old_callback,
            'Wait origin command menu not accepting')
    old_count=integer(old_obj,0x50,2);require(0<old_count<=32,'Wait origin command count invalid')
    old_rows_raw=before(integer(old_obj,0x94),old_count*4)
    old_rows=[integer(old_rows_raw,i*4) for i in range(old_count)]
    old_enabled=before(integer(old_obj,0x98),old_count)
    require(old_command['state']=='command' and old_command['member']==old_member
            and old_command['context']==old_context and old_command['callback']==old_callback
            and list(old_command['rows'])==old_rows and list(old_command['enabled'])==list(old_enabled)
            and old_rows.count(WAIT_COMMAND_ROW)==1 and old_enabled[old_rows.index(WAIT_COMMAND_ROW)]==1
            and old_command['unit_sha256']==hashlib.sha256(old).hexdigest(),
            'Wait origin command receipt/availability differs')
    require(integer(read(BATTLE_STRUCT,4),0)==8,'Wait continuation roster not restored')
    mirror=[read(ROSTER+i*STRIDE,STRIDE) for i in range(8)]
    require({r[0x104] for r in mirror}==set(range(8)),'Wait continuation mirror reused/ambiguous')
    require(len(origin['pins'])==2 and {p['id'] for p in origin['pins']}=={5,7}
            and len(origin['baseline'])==8,'Wait continuation origin identities missing')
    baseline={r['id']:r for r in origin['baseline']}
    for raw in mirror:
        original=baseline[raw[0x104]]
        require(integer(raw,0)==original['name'] and raw[4:8]==bytes(original[k] for k in ('type','base_job','race','job'))
                and raw[9]==original['level'] and integer(raw,0x28,2)==original['side_raw'],
                'Wait continuation full roster identity drift')
    old_units={int(a):bytes.fromhex(h) for a,h in origin['units'].items()}
    old_member=origin['facing']['member'];old=old_units[old_member]
    require(old[0x104]==owner['id'] and integer(old,0)==owner['name'], 'Wait origin names another actor')
    driver=read(PLAYER_DRIVER,0xE0);wrapper=integer(driver,4)
    require(wrapper==integer(driver,8) and wrapper!=origin['facing']['actor_wrapper'],
            'Wait continuation wrapper is unchanged/ambiguous')
    member=integer(read(wrapper,4),0);current=read(member,STRIDE)
    require(member!=old_member and current[0x104]!=owner['id'] and current[0x104] in (5,7)
            and integer(current,0x28,2)&0x9000==0 and not current[0xEB]&4
            and not current[0xEA]&0x80 and not current[0xE8]&0x40,'Wait next ally is invalid or blocked')
    pins={p['id']:p for p in origin['pins']};pin=pins[current[0x104]]
    require(pin['canonical']==member and pin['name']==integer(current,0),'Wait next canonical identity differs')
    for party_pin in pins.values():
        previous=old_units[party_pin['canonical']];party=read(party_pin['canonical'],STRIDE)
        require(party[:10]==previous[:10] and party[0x1A:0x1C]==previous[0x1A:0x1C]
                and party[0x1E:0x20]==previous[0x1E:0x20] and party[0x28:0x2A]==previous[0x28:0x2A]
                and party[0xF6:0xF8]==previous[0xF6:0xF8] and party[0x104]==previous[0x104],
                'Wait continuation canonical party identity drift')
    actor=later['actor']
    require(later['relation']=='ally' and later['canonical']==member and later['wrapper']==wrapper
            and actor['id']==current[0x104] and actor['name']==integer(current,0), 'Wait next actor metadata differs')
    require(actor['side_bit'] is False and actor['unaffiliated'] is False,'Wait next actor side metadata differs')
    row=mirror[actor['slot']]
    for field,offset,size in [('type',4,1),('base_job',5,1),('race',6,1),('job',7,1),('level',9,1),
                            ('hp',0x18,2),('max_hp',0x1A,2),('mp',0x1C,2),('max_mp',0x1E,2),('side_raw',0x28,2)]:
        require(actor[field]==integer(current,offset,size)==integer(row,offset,size),'Wait next canonical/mirror differs')
    require(0<actor['hp']<=actor['max_hp']<=999 and 0<=actor['mp']<=actor['max_mp']<=999,
            'Wait next actor resources invalid')
    tile=current[0xF6:0xF8]
    require(tile==row[0xF6:0xF8]==read(0x0200FFC9,2) and all(v<64 for v in tile), 'Wait next actor cursor differs')
    context=integer(read(MENU_ROOT,4),0);root=read(context,0x30);callback=integer(root,0x28)
    cb=read(callback,0x18);obj=read(callback+0x18,0x9C)
    require(root[4]==4 and integer(root,0x18)==member and integer(cb,0)==0x08028DE1
            and integer(cb,0x14,2)==0x102 and integer(driver,0xDC,2)==0x25
            and integer(driver,0x60)==0 and integer(read(integer(root,0x20)+4,4),0)==callback,
            'Wait next command menu is not owned/accepting')
    count,scroll,cursor=integer(obj,0x50,2),integer(obj,0x52,2),obj[0x69]
    require(0<count<=32 and cursor<count and scroll+cursor<count,'Wait next command bounds invalid')
    rows_raw=read(integer(obj,0x94),count*4);enabled=read(integer(obj,0x98),count)
    rows=[integer(rows_raw,i*4) for i in range(count)]
    require(all(v in (0,1) for v in enabled) and rows.count(WAIT_COMMAND_ROW)==1
            and enabled[rows.index(WAIT_COMMAND_ROW)]==1,
            'Wait next command unavailable')
    require(command['state']=='command' and command['member']==member and command['mode']==4
            and command['context']==context and command['callback']==callback and command['active']==callback
            and list(command['rows'])==rows and list(command['enabled'])==list(enabled)
            and command['cursor']==cursor and command['scroll']==scroll
            and command['unit_sha256']==hashlib.sha256(current).hexdigest(), 'Wait next command receipt differs')
    if post_players is not None:
        require({p['id'] for p in post_players}=={5,7},'Wait result party identities differ')
        for player in post_players:
            r=mirror[player['slot']]
            require(r[0x104]==player['id'] and integer(r,0)==player['name']
                    and list(r[0xF6:0xF8])==[player['x'],player['y']]
                    and integer(r,0x18,2)==player['hp'] and integer(r,0x1C,2)==player['mp'],
                    'Wait result mirror identity/tile/resources differ')
    return later
