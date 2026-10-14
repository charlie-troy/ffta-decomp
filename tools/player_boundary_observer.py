"""Read-only native pick and adapter history for the bounded eight-unit player fixture."""
import json
from pathlib import Path

from fixture_guard import BATTLE_STRUCT, ROSTER, STRIDE
from probe_control_handoff import Probe
from recovery_menu import MEMBERS, MENU_ROOT, PLAYER_DRIVER, exact, integer, require

PICK_SITE=0x08093018


def unit_record(address,raw):
    return {'address':address,'raw':raw.hex(),'name':integer(raw,0),'id':raw[0x104],
        'type':raw[4],'race':raw[6],'job':raw[7],'level':raw[9],
        'hp':integer(raw,0x18,2),'max_hp':integer(raw,0x1A,2),
        'mp':integer(raw,0x1C,2),'max_mp':integer(raw,0x1E,2),
        'ct':integer(raw,0xD0,2),'tile':list(raw[0xF6:0xF8]),
        'side_raw':integer(raw,0x28,2),'status_flags':list(raw[0xE8:0xEE]),
        'sleep':bool(raw[0xEB]&4),'sleep_duration':raw[0xDF]}


def pointer(value,size):
    return type(value)==int and 0x02000000<=value<=0x02040000-size


class PlayerBoundaryProbe(Probe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.observer_path=None;self.observer_context=lambda:{}
        self.observer_errors=[];self.observer_hits=0

    def arm(self,strict=False):
        super().arm(strict=strict)
        response=self.set_bp(PICK_SITE)
        require(not strict or response=='OK','native player-pick observer hook rejected')

    def disarm(self,strict=False):
        super().disarm(strict=strict)
        self.clear_bp(PICK_SITE,strict=strict)

    def _record(self,phase,*,regs=None,adapter=None):
        record={'phase':phase,'t':self.now(),'context':self.observer_context()}
        try:
            count_raw=exact(self.g,BATTLE_STRUCT,4)
            record['structure']={'raw':count_raw.hex(),'count':integer(count_raw,0)}
            record['party']={'canonical':[unit_record(a,exact(self.g,a,STRIDE)) for a in (MEMBERS,MEMBERS+STRIDE)],
                'mirror':[unit_record(ROSTER+i*STRIDE,exact(self.g,ROSTER+i*STRIDE,STRIDE)) for i in (5,7)]}
            driver=exact(self.g,PLAYER_DRIVER,0xE0)
            record['driver']={'address':PLAYER_DRIVER,'raw':driver.hex(),'wrapper':integer(driver,4),
                'peer_wrapper':integer(driver,8),'state':integer(driver,0xDC,2),'control':integer(driver,0xD0)}
            wrapper=integer(driver,4)
            if pointer(wrapper,4):
                member=integer(exact(self.g,wrapper,4),0)
                record['driver']['member']=member
                if pointer(member,STRIDE):record['driver']['unit']=unit_record(member,exact(self.g,member,STRIDE))
            context=integer(exact(self.g,MENU_ROOT,4),0)
            record['menu']={'context':context}
            if pointer(context,0x30):
                root=exact(self.g,context,0x30);callback=integer(root,0x28)
                record['menu'].update(raw=root.hex(),mode=root[4],member=integer(root,0x18),callback=callback)
                if pointer(callback,0x18):
                    cb=exact(self.g,callback,0x18)
                    record['menu'].update(callback_raw=cb.hex(),handler=integer(cb,0),state=integer(cb,0x14,2))
            record['cursor']={'target':self.read_target_cursor(),'command':self.read_cmd_cursor()}
            if regs is not None:
                wrapper=regs[0];require(pointer(wrapper,4),'invalid native picked wrapper')
                member=integer(exact(self.g,wrapper,4),0);require(pointer(member,STRIDE),'invalid native picked member')
                record['pick']={'wrapper':wrapper,'member':member,'driver_register':regs[6],
                    'unit':unit_record(member,exact(self.g,member,STRIDE))}
            if adapter is not None:record['adapter']=adapter
        except (ValueError,OSError,ConnectionError) as exc:
            record['error']=str(exc);self.observer_errors.append({'phase':phase,'t':record['t'],'error':str(exc)})
        self.observer_hits+=1
        if self.observer_path:
            with Path(self.observer_path).open('a',encoding='utf-8',newline='\n') as stream:
                stream.write(json.dumps(record)+'\n')
        return record

    def observe_adapter_attempt(self,rows,owner,error):
        return self._record('adapter-attempt',adapter={'rows':rows,'owner':owner,'error':error})

    def handle_stop(self,during=''):
        if self.g.read_pc()!=PICK_SITE:return super().handle_stop(during)
        regs=self.g.read_registers()
        if regs is None:
            self.observer_errors.append({'phase':'native-pick','t':self.now(),'error':'missing native registers'})
            return None
        self._record('native-pick',regs=regs)
        return regs
