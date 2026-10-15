"""Schema2 candidate from the revalidated bounded native self-Potion context."""
from recovery_menu import exact,integer,require
from tactics_policy import validate_snapshot

POTION_CANDIDATE='item:Potion:self'


def potion_snapshot(reader,token,owner):
    reader.revalidate(token)
    unit=exact(reader.g,token.source,0x108)
    require(owner['id']==unit[0x104]==5 and integer(unit,0)==owner['name']
            and token.source==token.target==0x02000188,'Potion policy source differs')
    return validate_snapshot({'schema':'ffta-tactics-snapshot/2','identity':'verified','age_seconds':0,
        'actor':{'name':owner['name_text'],'id':5,'job_id':unit[7],'side':'player','hp':token.hp,
                 'max_hp':integer(unit,0x1A,2),'mp':integer(unit,0x1C,2),'max_mp':integer(unit,0x1E,2),'tile':list(token.tile)},
        'candidates':[{'id':POTION_CANDIDATE,'kind':'item','action_id':1,'legal':True,'cost':0,
            'relation':'self','target':{'kind':'unit','id':5},'target_hp':token.hp,'target_max_hp':integer(unit,0x1A,2),
            'target_mp':integer(unit,0x1C,2),'item_name':'Potion','count':token.count}]})
