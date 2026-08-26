/* AI ability evaluator - sub_080C32C0, 0x080C32C0, 5350 bytes.
 *
 * READABLE RECONSTRUCTION, NOT BYTE-MATCHING. This lives in reference/ rather
 * than src/ precisely so it is never fed to the build: everything under src/
 * must reproduce the ROM exactly, and this does not.
 *
 * Purpose is to make the AI's decisions legible enough to change. Names come
 * from docs/unit-struct.md, docs/ability-table.md and docs/unit-flags.md.
 * Anything still unidentified keeps its sub_ or unk_ name so the guesswork is
 * visible rather than hidden behind a confident-looking label.
 */

typedef unsigned char u8;
typedef unsigned short u16;
typedef short s16;

/* Only the fields this function touches. Offsets from docs/unit-struct.md. */
struct Unit
{
    u8  filler_00[0x18];
    u16 hp;             /* +0x18, stat id 0x13 */
    u16 maxHp;          /* +0x1A, stat id 0x14 */
    u16 mp;             /* +0x1C, stat id 0x15 */
    u8  filler_1E[0xC9];
    u8  recentTargetIds; /* +0xE7, two 4-bit unit ids; newest in low nibble */
    u8  filler_E8[0x09];
    u8  koInflictedCount; /* +0xF1 */
    u8  koSufferedCount;  /* +0xF2 */
    u8  otherRemovalCount; /* +0xF3; Wyrmtamer and other removal outcomes */
    u8  parleyRemovalCount; /* +0xF4; also modifies purge hit formulas */
    u8  oustRemovalCount;   /* +0xF5 */
    u8  tileX;           /* +0xF6 */
    u8  tileY;           /* +0xF7 */
    u8  tileHeight;      /* +0xF8 */
    u8  savedTileX;      /* +0xF9; snapshot copied from tileX */
    u8  savedTileY;      /* +0xFA; snapshot copied from tileY */
    u8  battleListIndex; /* +0xFB */
};
struct Ability;   /* 28 bytes; see docs/ability-table.md                       */

/* An in-progress action. u16[] in the original; only some fields are known. */
struct Action
{
    u16 abilityId;      /* [0]  index into the ability table          */
    u16 unk_02[2];      /* [1..2]                                     */
    u16 effectId;       /* [3]  selects the 92-case switch, via +2    */
    u16 unk_08;         /* [4]                                        */
    u16 unk_0A;         /* [5]  must be non-zero                      */
    s16 unk_0C;         /* [6]  sign is tested repeatedly             */
    s16 unk_0E;         /* [7]  compared against 0x1E                 */
    u16 unk_10;         /* [8]  passed to sub_0812F1DC                */
    u8  flags_11;       /* byte at +0x11, bits 0 and 1 reject         */
};

extern struct Ability gAbilityTable[];       /* 0x0855187C, 347 entries */

extern int  AbilityProp(u16 abilityId, u8 propId);        /* sub_080CCD50 */
extern u16  AbilityMpCost(struct Unit *u, u16 abilityId); /* sub_0812ED98 */
extern int  UnitStat(struct Unit *u, u8 statId);          /* sub_080C7EA4 */

#define STAT_HP      0x13    /* unit +0x18 */
#define STAT_MAX_HP  0x14    /* unit +0x1A */

extern void Reject(void);            /* sub_080C478C, the common bail-out */
extern void RejectLate(void);        /* sub_080C477A                      */

/* Unit status/capability getters; see docs/unit-flags.md. */
extern u8 sub_080C8240(struct Unit *u);
extern u8 sub_080C8260(struct Unit *u);
extern u8 sub_080CDB54(struct Unit *u);
extern u8 sub_080CDB6C(struct Unit *u);
extern u8 sub_080CD8FC(struct Unit *u);
extern u8 sub_0812F154(struct Unit *u);
extern u8 sub_081341BC(struct Unit *a, struct Unit *b); /* recent-target membership */
extern u8 sub_0812F1DC(s16 v);
extern u8 sub_0812F0E4(struct Unit *u, int a, int b);
extern u16 sub_0812E6A4(struct Unit *u);
extern u8 sub_08133A58(struct Unit *u, u16 effectId);
extern void sub_080CDD88(struct Unit *u, u8 v);

extern void (*gEffectHandlers[92])(void);   /* 0x080C3624, all internal */
extern void (*gSubHandlers[8])(void);       /* 0x080C347C              */

void AiEvaluateAbility(struct Unit *user, struct Unit *target,
                       struct Action *act, u8 checkCost)
{
    u16 mode;
    s16 c, e;
    u8 saved;

    /* Two action flags veto outright. */
    if (act->flags_11 & 1)
        Reject();
    if (act->flags_11 & 2)
        Reject();

    /* One specific ability additionally requires a user flag. */
    if (act->abilityId == 0x109 && !sub_080C8240(user) && !sub_080C8260(user))
        Reject();

    if (checkCost)
    {
        if (!AbilityProp(act->abilityId, 0x13))     /* flag bit 8 */
            Reject();

        /* Reject when the user cannot afford it. The subtraction is done in
         * 16 bits and tested for sign, so it is an unsigned MP < cost test. */
        if ((s16)(user->mp - AbilityMpCost(user, act->abilityId)) < 0)
            Reject();
    }

    /* AI behaviour 2 means "use on a healthy target". Reject when the target
     * is already below half HP: no point debuffing something about to die.
     * See docs/ability-table.md; this is the rule most worth tuning. */
    if (act->abilityId != 0
        && gAbilityTable[act->abilityId].aiBehaviour == 2
        && UnitStat(target, STAT_HP) < UnitStat(target, STAT_MAX_HP) / 2)
        Reject();

    /* Self-targeting has its own vetoes. */
    if (user == target)
    {
        if (sub_080CDB54(target))
            Reject();
        if (sub_080CDB6C(target))
            Reject();
    }

    if (sub_080CDB54(user) && act->unk_0C < 0)
        Reject();

    if (AbilityProp(act->abilityId, 0x12)           /* flag bit 7, Reflectable */
        && sub_0812F154(target)
        && act->unk_0C < 0)
        Reject();

    e = act->unk_10;
    c = act->unk_0C;

    /* The outer test is vacuous as written (c >= 0 || c < 0), which is how
     * the original compiles; the meaningful part is the inner pair. */
    if (sub_081341BC(user, target) || c < 0)
    {
        if (c >= 0 && act->unk_0E < 0x1E)
            Reject();

        mode = sub_0812E6A4(target) & 0xFFFF;
        if (!sub_0812F0E4(target, (signed char)target->tileX,
                          (signed char)target->tileY))
            mode = 0;
        if (act->abilityId != 0 && AbilityProp(act->abilityId, 0x11))
            mode = 0;                                /* flag bit 6 */

        if (mode - 4 < 8)
        {
            gSubHandlers[mode - 4]();
            return;
        }

        if (act->abilityId != 0 && sub_0812F154(target)
            && AbilityProp(act->abilityId, 0x12))
            Reject();
    }

    if (!sub_0812F1DC((s16)(char)e))
        Reject();
    if (act->unk_0A == 0)
        Reject();

    /* From here the action pointer advances two u16s and the effect id drives
     * the 92-case switch. */
    act = (struct Action *)((u16 *)act + 2);
    if (act->abilityId == 0)
        RejectLate();

    /* A status bit is briefly cleared around the reachability test, then put
     * back, so the test is done as though the unit did not have it. */
    saved = sub_080CD8FC(user);
    sub_080CDD88(user, 0);
    if (!sub_08133A58(target, act->abilityId))
    {
        sub_080CDD88(user, saved);
        RejectLate();
    }
    sub_080CDD88(user, saved);

    if (act->abilityId - 1 > 0x5B)
        RejectLate();

    /* 92 cases, all bodies internal to this function. Most follow the same
     * shape: a scoring helper, a status getter for the effect in question,
     * then a shared tail. See docs/ai-evaluator-cases.md. */
    gEffectHandlers[act->abilityId - 1]();
}
