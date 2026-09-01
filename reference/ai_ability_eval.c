/* AI ability evaluator - sub_080C32C0, 0x080C32C0, 5352 bytes.
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
typedef signed char s8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef short s16;

/* Only the fields this function touches. Offsets from docs/unit-struct.md. */
struct Unit
{
    const void *nameText; /* +0x00, encoded text rendered by sub_08025688 */
    u8  filler_04[0x14];
    u16 hp;             /* +0x18, stat id 0x13 */
    u16 maxHp;          /* +0x1A, stat id 0x14 */
    u16 mp;             /* +0x1C, stat id 0x15 */
    u8  filler_1E[0xB2];
    s16 chargeTime;       /* +0xD0, stat id 0x23 */
    u8  filler_D2[0x15];
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
struct Ability
{
    u8 filler_00[0x19];
    u8 aiBehaviour;    /* +0x19 */
    u8 filler_1A[2];
};                    /* 28 bytes; see docs/ability-table.md */

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
    s8  unk_10;         /* byte +0x10, passed signed to sub_0812F1DC  */
    u8  flags_11;       /* byte +0x11, bits 0 and 1 reject            */
};

/* Retail reserves a 20-byte frame. This grouped 16-byte prefix places the
 * three helper results at sp+0/+4/+8 and the action at sp+12; the separate
 * candidateIndex local below naturally occupies sp+16. */
struct AiEvaluatorFrame
{
    s16 effectEstimate[2];
    s16 effectEstimateAlt[2];
    s16 effectEstimateMode[2];
    struct Action *action;
};

extern struct Ability gAbilityTable[];       /* 0x0855187C, 347 entries */
extern u8 gEwram[];                          /* 0x02000000 */

extern int  AbilityProp(u16 abilityId, u8 propId);        /* sub_080CCD50 */
extern u16  AbilityMpCost(struct Unit *u, u16 abilityId); /* sub_0812ED98 */
extern int  AbilityMpCostWide(struct Unit *u, u16 abilityId)
    __asm__("AbilityMpCost");
extern int  UnitStat(struct Unit *u, u8 statId);          /* sub_080C7EA4 */
extern int  sub_0812E368(struct Unit *u);                 /* effective Speed */

#define STAT_HP      0x13    /* unit +0x18 */
#define STAT_MAX_HP  0x14    /* unit +0x1A */

/* Unit status/capability getters; see docs/unit-flags.md. */
extern u8 sub_080C8240(struct Unit *u);
extern u8 sub_080C8260(struct Unit *u);
extern u8 sub_080C832C(struct Unit *u);
extern u8 sub_080CDB54(struct Unit *u);
extern u8 sub_080CDB6C(struct Unit *u);
extern u8 sub_080CD8FC(struct Unit *u);
extern u8 sub_080CD8E4(struct Unit *u);
extern u8 sub_080CD8CC(struct Unit *u);
extern u8 sub_080CD914(struct Unit *u);
extern u8 sub_080CD92C(struct Unit *u);
extern u8 sub_080CD944(struct Unit *u);
extern u8 sub_080CD95C(struct Unit *u);
extern u8 sub_080CD974(struct Unit *u);
extern u8 sub_080CD98C(struct Unit *u);
extern u8 sub_080CD9BC(struct Unit *u);
extern u8 sub_080CD9EC(struct Unit *u);
extern u8 sub_080CDA1C(struct Unit *u);
extern u8 sub_080CDA34(struct Unit *u);
extern u8 sub_080CDA4C(struct Unit *u);
extern u8 sub_080CDA64(struct Unit *u);
extern u8 sub_080CDA94(struct Unit *u);
extern u8 sub_080CDAAC(struct Unit *u);
extern u8 sub_080CDAC4(struct Unit *u);
extern u8 sub_080CDADC(struct Unit *u);
extern u8 sub_080CDB24(struct Unit *u);
extern u8 sub_080CDB3C(struct Unit *u);
extern u8 sub_080CDB0C(struct Unit *u);
extern u8 sub_080CDB84(struct Unit *u);
extern u8 sub_080CDB9C(struct Unit *u);
extern u8 sub_080CDBB4(struct Unit *u);
extern u8 sub_080CDBFC(struct Unit *u);
extern u8 sub_080CDBE4(struct Unit *u);
extern u8 sub_080CDC14(struct Unit *u);
extern u8 sub_080CDC2C(struct Unit *u);
extern u8 sub_080CDC44(struct Unit *u);
extern u8 sub_080CDC5C(struct Unit *u);
extern u8 sub_080CDC74(struct Unit *u);
extern u8 sub_080CDC8C(struct Unit *u);
extern u8 sub_080CDAF4(struct Unit *u);
extern u8 sub_0812F154(struct Unit *u);
extern u8 sub_081341BC(struct Unit *a, struct Unit *b); /* recent-target membership */
extern u8 sub_0812F1DC(s16 v);
extern u8 sub_0812F0E4(struct Unit *u, int a, int b);
extern u16 sub_0812E6A4(struct Unit *u);
extern u8 sub_08133A58(struct Unit *u, u16 effectId);
extern u8 sub_08131030(struct Unit *u);
extern void sub_080CDD88(struct Unit *u, u8 v);

extern int sub_08002804(void);              /* battle RNG               */
extern int sub_08142950(int value, int divisor); /* signed remainder       */
extern int sub_0812F0D8(struct Unit *u, s16 outPair[2]);
extern u8 sub_0812EE98(struct Unit *u, u16 value);
extern u8 sub_0812EED0(struct Unit *u, u16 value);
extern int sub_080C13C8(struct Unit *u);
extern int sub_08142AB0(int value, int divisor); /* signed division */
extern int sub_080CA7A4(u16 itemId, u8 propertyId);
extern void *sub_08022840(int size);
extern void sub_08022854(void *p);
extern int sub_081342A8(u16 *out, struct Unit *target);
extern int sub_081342B4(u16 *out, struct Unit *target);
extern int sub_081342C0(u16 *out, struct Unit *target);
extern void sub_08142250(void *dst, const void *src, int size, const void *mode);
extern void sub_08133BB4(struct Unit *copy, u16 effectId);

static __inline__ int AiPassesStatusProbability(struct Unit *user,
                                                 struct Unit *target)
{
    s16 roll;
    register int pass __asm__("r0");

    /* Keep the RNG call inside each arm. Retail duplicates these instruction
     * sequences instead of rolling once and selecting only the threshold. */
    if (user == target)
    {
        roll = (s16)sub_08002804();
        roll = (s16)sub_08142950(roll, 101);
        if (roll > 10)
            pass = 0;
        else
            pass = 1;
    }
    else
    {
        roll = (s16)sub_08002804();
        roll = (s16)sub_08142950(roll, 101);
        if (roll > 49)
            pass = 0;
        else
            pass = 1;
    }
    __asm__ volatile ("" : "+r" (pass));
    return pass;
}

int AiEvaluateAbility(struct Unit *user, struct Unit *target,
                      struct Action *act, int checkCostArg)
{
    u8 checkCost;
    u16 mode;
    u16 currentMp;
    s16 mpThreshold;
    s16 actionValue;
    int e;
    u8 rangeCode;
    u16 estimateValue;
    u32 adjustedRange;
    int isNegative;
    u16 abilityId;
    s16 probabilityRoll;
    int probabilityPass;
    int stateResult;
    register int rawStateResult __asm__("r0");
    u16 *abilityList;
    u16 *effectEntry;
    struct Unit *unitCopy;
    int count, i, found, changed;
    u8 saved;
    register struct Unit *actor __asm__("r10") = user;
    register struct Unit *subject __asm__("r8") = target;
    struct AiEvaluatorFrame frame;
    int candidateIndex;

    frame.action = act;
    checkCost = checkCostArg;

#define user actor
#define target subject
#define act frame.action
#define effectEstimate frame.effectEstimate
#define effectEstimateAlt frame.effectEstimateAlt
#define effectEstimateMode frame.effectEstimateMode
#define Reject() goto reject_all
#define RejectLate() goto reject_current

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
        currentMp = AbilityMpCostWide(user, act->abilityId);
        if ((s16)(user->mp - currentMp) < 0)
            Reject();
    }

    /* AI behaviour 2 means "use on a healthy target". Reject when the target
     * is already below half HP: no point debuffing something about to die.
     * See docs/ability-table.md; this is the rule most worth tuning. */
    if (act->abilityId != 0
        && gAbilityTable[act->abilityId].aiBehaviour == 2
        && UnitStat(target, STAT_HP) <
           ((u32)UnitStat(target, STAT_MAX_HP) >> 1))
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
    actionValue = act->unk_0C;
    isNegative = actionValue < 0;

    if (actionValue >= 0 || isNegative)
    {
        if (!(sub_081341BC(user, target) || isNegative))
            goto check_final_value;

        if (!isNegative && act->unk_0E < 0x1E)
            Reject();

        mode = sub_0812E6A4(target) & 0xFFFF;
        if (!sub_0812F0E4(target, (signed char)target->tileX,
                          (signed char)target->tileY))
            mode = 0;
        if (act->abilityId != 0 && AbilityProp(act->abilityId, 0x11))
            mode = 0;                                /* flag bit 6 */

        switch (mode)
        {
        case 4:
            if (act->abilityId == 0)
                goto check_final_value;
            if (!AbilityProp(act->abilityId, 0x1B))
                goto check_reflect;
            Reject();
        case 5:
            abilityId = act->abilityId;
            if (abilityId != 0)
                goto check_reflect;
            Reject();
        case 6:
            if (act->abilityId != 0 && !AbilityProp(act->abilityId, 3))
                goto check_reflect;
            sub_0812F0D8(user, effectEstimate);
            estimateValue = (u16)effectEstimate[0];
check_range_code:
            rangeCode = sub_0812EE98(user, estimateValue);
            adjustedRange = ((u32)rangeCode << 24) >> 8;
            adjustedRange += 0xFFF30000;
            if ((u16)(adjustedRange >> 16) > 1)
                goto check_reflect;
            Reject();
        case 9:
            abilityId = act->abilityId;
            if (abilityId != 0)
                goto check_reflect;
            sub_0812F0D8(user, effectEstimateAlt);
            estimateValue = (u16)effectEstimateAlt[0];
            goto check_range_code;
        case 7:
        case 8:
        case 10:
            abilityId = act->abilityId;
            if (abilityId != 0)
                goto check_reflect;
            sub_0812F0D8(user, effectEstimateMode);
            rangeCode = sub_0812EED0(user, (u16)effectEstimateMode[0]);
            if (mode == 7 && rangeCode <= 1)
                Reject();
            if (rangeCode <= 2)
                e >>= 1;
            if (isNegative == 1)
                Reject();
            goto check_reflect;
        case 11:
            abilityId = act->abilityId;
            if (abilityId == 0)
                goto check_final_value;
            if (AbilityProp(abilityId, 0x1A))
            {
                s16 cost = (s16)AbilityMpCost(target, abilityId);
                if (cost <= UnitStat(target, 0x15))
                    e >>= 1;
            }
            goto check_reflect;
        default:
            break;
        }

check_reflect:
        if (act->abilityId != 0 && sub_0812F154(target)
            && AbilityProp(act->abilityId, 0x12))
            Reject();
    }

check_final_value:
    if (!sub_0812F1DC(e))
        Reject();
    candidateIndex = 0;
    if (candidateIndex >= act->unk_0A)
        Reject();

next_effect:
    /* The candidate effects are the u16 list at action +4. Failed entries
     * advance through the list; successful entries return immediately. */
    effectEntry = (u16 *)((u8 *)act + 4) + candidateIndex;
    if (*effectEntry == 0)
        RejectLate();

    /* A status bit is briefly cleared around the reachability test, then put
     * back, so the test is done as though the unit did not have it. */
    saved = sub_080CD8FC(user);
    sub_080CDD88(user, 0);
    if (!sub_08133A58(target, *effectEntry))
    {
        sub_080CDD88(user, saved);
        RejectLate();
    }
    sub_080CDD88(user, saved);

    if ((u16)(*effectEntry - 1) > 0x5B)
        RejectLate();

#define ABSENT_STATE_CASE(id, test) \
    case id: \
        if (!AiPassesStatusProbability(user, target)) \
            RejectLate(); \
        test(target); \
        __asm__ volatile ("" : "=r" (rawStateResult)); \
        goto absent_state_result
#define PRESENT_STATE_CASE(id, test) \
    case id: \
        stateResult = test(target); \
        goto present_state_result
    /* Keep case bodies in retail's physical root order. */
    switch (*effectEntry)
    {
    case 1:
        if (sub_0812E368(target) == 0)
            RejectLate();
        if ((s16)target->chargeTime <= 499)
            RejectLate();
        __asm__ volatile ("AiEvaluateAbility_accept_current:");
        return 1;
    case 5:
    case 18:
    case 26:
    case 39:
    case 40:
    case 44:
    case 68:
    case 81:
        return 1;
    case 2:
        if (sub_0812E368(target) == 0)
            RejectLate();
        if ((s16)target->chargeTime > 699)
            RejectLate();
        return 1;
    case 3:
        if (!AiPassesStatusProbability(user, target))
            RejectLate();
        if (sub_080CDBE4(target) && sub_080CDC14(target) &&
            sub_080CDC44(target) && sub_080CDC74(target))
            RejectLate();
        return 1;
    case 7:
        if (UnitStat(target, 0x26) <= 1)
            RejectLate();
        return 1;
    case 8:
        abilityList = (u16 *)sub_08022840(0x50);
        count = sub_081342A8(abilityList, target);
        count += sub_081342B4(abilityList + count, target);
        count += sub_081342C0(abilityList + count, target);
        found = 0;
        for (i = 0; i < count; i++)
        {
            if (AbilityProp(abilityList[i], 2))
            {
                found = 1;
                break;
            }
        }
        sub_08022854(abilityList);
        if (!found || UnitStat(target, 0x15) == 0)
            RejectLate();
        return 1;
    case 9:
        currentMp = (u16)UnitStat(target, 0x15);
        mpThreshold = (s16)sub_08142AB0(UnitStat(target, 0x16), 3);
        if (mpThreshold == 0 || (s16)currentMp > mpThreshold)
            RejectLate();
        return 1;
    ABSENT_STATE_CASE(10, sub_080CD8FC);
    case 11:
    case 53:
    case 54:
    case 58:
    case 79:
        unitCopy = (struct Unit *)sub_08022840(0x108);
        sub_08142250(unitCopy, target, 0x108,
                     *(const void **)0x0836D4BC);
        sub_08133BB4(unitCopy, *effectEntry);
        changed = (*(unsigned int *)((u8 *)target + 0xE8) !=
                   *(unsigned int *)((u8 *)unitCopy + 0xE8));
        if (!changed)
            changed = (*(unsigned int *)((u8 *)target + 0xEC) !=
                       *(unsigned int *)((u8 *)unitCopy + 0xEC));
        sub_08022854(unitCopy);
        return changed;
    ABSENT_STATE_CASE(12, sub_080CD95C);
    PRESENT_STATE_CASE(13, sub_080CD95C);
    case 15:
    case 50:
        if (user == target)
            goto probability_self;
        probabilityRoll = (s16)sub_08002804();
        probabilityRoll = (s16)sub_08142950(probabilityRoll, 101);
        __asm__ volatile ("");
        if (probabilityRoll > 49)
            goto probability_fail;
        goto probability_pass;
    case 16:
        if (user != target || (u16)sub_080C13C8(target) == 0)
            goto probability_fail;
        goto probability_pass;
    ABSENT_STATE_CASE(17, sub_080CDA1C);
    ABSENT_STATE_CASE(19, sub_080CDADC);
    ABSENT_STATE_CASE(20, sub_080CDA34);
    case 4:
    case 6:
    case 21:
        if (act->unk_0C <= 0)
            RejectLate();
        return 1;
    ABSENT_STATE_CASE(22, sub_080CDB9C);
    PRESENT_STATE_CASE(23, sub_080CDB9C);
    ABSENT_STATE_CASE(24, sub_080CDB84);
    PRESENT_STATE_CASE(25, sub_080CDB84);
    ABSENT_STATE_CASE(27, sub_080CD944);
    case 28:
        if (!AiPassesStatusProbability(user, target))
            RejectLate();
        if (sub_080CDAAC(target) == 1)
        {
            sub_080CDADC(target);
            __asm__ volatile ("" : "=r" (rawStateResult));
            goto absent_state_result;
        }
        else
        {
            sub_080CDAC4(target);
            __asm__ volatile ("" : "=r" (rawStateResult));
            goto absent_state_result;
        }
    case 29:
        if (sub_080CDB9C(target) && sub_080CDB84(target) &&
            sub_080CD98C(target) && sub_080CD944(target) &&
            UnitStat(target, STAT_HP) == 1)
            RejectLate();
        return 1;
    case 30:
        if (sub_080CDB9C(target) && sub_080CDB84(target) &&
            sub_080CDAC4(target) && sub_080CDADC(target))
            RejectLate();
        return 1;
    ABSENT_STATE_CASE(31, sub_080CD8E4);
    ABSENT_STATE_CASE(32, sub_080CD914);
    ABSENT_STATE_CASE(33, sub_080CD8CC);
    ABSENT_STATE_CASE(35, sub_080CD98C);
    PRESENT_STATE_CASE(36, sub_080CD98C);
    ABSENT_STATE_CASE(37, sub_080CDA64);
    case 38:
        if (act->unk_0C >= 0)
            Reject();
        e = UnitStat(target, STAT_HP);
        if (e > sub_08142AB0(UnitStat(target, STAT_MAX_HP), 3))
            Reject();
        return 1;
    case 41:
        if (!AiPassesStatusProbability(user, target))
            RejectLate();
        if (!sub_080CDB6C(target))
            return 1;
        sub_080CDB54(target);
        __asm__ volatile ("" : "=r" (rawStateResult));
        goto absent_state_result;
    ABSENT_STATE_CASE(42, sub_080CDA94);
    case 43:
        if (!AiPassesStatusProbability(user, target))
            __asm__ volatile ("b AiEvaluateAbility_reject_current");
        if (!sub_080CDAC4(target))
            __asm__ volatile ("b AiEvaluateAbility_accept_current");
        if (!sub_080CD98C(target))
            __asm__ volatile ("b AiEvaluateAbility_accept_current");
        if (!sub_080CDB54(target) || !sub_080CDB3C(target) ||
            !sub_080CD95C(target) || !sub_080CD974(target) ||
            !sub_080CDB24(target))
            return 1;
case43_reject:
        __asm__ volatile ("" ::: "memory");
        RejectLate();
        return 1;
    ABSENT_STATE_CASE(45, sub_080CDB24);
    ABSENT_STATE_CASE(46, sub_080CD92C);
    PRESENT_STATE_CASE(47, sub_080CD92C);
    case 48:
        if (!AiPassesStatusProbability(user, target))
            RejectLate();
        if (sub_080CDC5C(target) && sub_080CDC8C(target))
            RejectLate();
        return 1;
    case 49:
        i = 0;
        adjustedRange = 0x1D000000;
        do
        {
            int itemType = sub_080CA7A4(
                (u16)UnitStat(target, (u8)(adjustedRange >> 24)), 3);
            if (itemType <= 0x1A)
            {
                __asm__ volatile ("");
                if (itemType >= 0x18)
                    return 1;
            }
            adjustedRange += 0x01000000;
            i++;
        }
        while (i <= 4);
        RejectLate();
        break;
    ABSENT_STATE_CASE(51, sub_080CDAC4);
    ABSENT_STATE_CASE(52, sub_080CDAAC);
    case 55:
        if (!AiPassesStatusProbability(user, target))
            RejectLate();
        if (sub_080CDA4C(target))
            RejectLate();
        e = UnitStat(target, STAT_HP);
        if (e > sub_08142AB0(UnitStat(target, STAT_MAX_HP), 3))
            RejectLate();
        return 1;
    ABSENT_STATE_CASE(56, sub_080CDB3C);
    PRESENT_STATE_CASE(57, sub_080CDB3C);
    case 59:
        if (user != target)
            goto probability_other;
probability_self:
        probabilityRoll = (s16)sub_08002804();
        probabilityRoll = (s16)sub_08142950(probabilityRoll, 101);
        if (probabilityRoll > 10)
            goto probability_fail;
        goto probability_pass;
probability_other:
        probabilityRoll = (s16)sub_08002804();
        probabilityRoll = (s16)sub_08142950(probabilityRoll, 101);
        if (probabilityRoll <= 49)
            goto probability_pass;
probability_fail:
        probabilityPass = 0;
        goto probability_done;
probability_pass:
        probabilityPass = 1;
probability_done:
        __asm__ volatile ("" : "+r" (probabilityPass));
        if (!probabilityPass)
            RejectLate();
        return 1;
    ABSENT_STATE_CASE(60, sub_080CD9BC);
    ABSENT_STATE_CASE(61, sub_080CD974);
    case 62:
        if (!AiPassesStatusProbability(user, target))
            RejectLate();
        stateResult = sub_080CD974(target);
        goto present_state_result;
    case 63:
        if (!AiPassesStatusProbability(user, target))
            RejectLate();
        if (UnitStat(target, 0x1B) & 0x0800)
            RejectLate();
        sub_08131030(target);
        __asm__ volatile ("" : "=r" (rawStateResult));
        goto absent_state_result;
    PRESENT_STATE_CASE(64, sub_08131030);
present_state_result:
        if (stateResult != 1)
            RejectLate();
        return 1;
    case 65:
    case 66:
    case 67:
        if (!AiPassesStatusProbability(user, target))
            RejectLate();
        if (sub_0812F0D8(target, effectEstimate) <= 0)
            RejectLate();
        return 1;
    ABSENT_STATE_CASE(69, sub_080CDBFC);
    ABSENT_STATE_CASE(70, sub_080CD9EC);
    ABSENT_STATE_CASE(71, sub_080CDBB4);
    ABSENT_STATE_CASE(72, sub_080CDC5C);
    ABSENT_STATE_CASE(73, sub_080CDC44);
    case 75:
        if (UnitStat(target, STAT_HP) <= 1)
            RejectLate();
        return 1;
    ABSENT_STATE_CASE(76, sub_080CDC2C);
    ABSENT_STATE_CASE(77, sub_080CDC8C);
    ABSENT_STATE_CASE(78, sub_080CDC74);
    case 80:
        if (!AiPassesStatusProbability(user, target))
            RejectLate();
        if (!sub_080CDB54(target))
            return 1;
        sub_080CDB6C(target);
        __asm__ volatile ("" : "=r" (rawStateResult));
        goto absent_state_result;
    ABSENT_STATE_CASE(82, sub_080CDB0C);
    ABSENT_STATE_CASE(83, sub_080CDAF4);
absent_state_result:
        __asm__ volatile ("lsl %0, %0, #24" : "+r" (rawStateResult));
        if (rawStateResult)
            RejectLate();
        return 1;
    case 92:
        if (gEwram[0x3C33] == 0)
            RejectLate();
        sub_080C832C(target);
        __asm__ volatile ("lsl %0, %0, #24" : "=r" (rawStateResult));
        if (rawStateResult)
            RejectLate();
        __asm__ volatile ("" ::: "memory");
        return 1;
    case 14:
    case 34:
    case 74:
    case 84:
    case 85:
    case 86:
    case 87:
    case 88:
    case 89:
    case 90:
    case 91:
        RejectLate();
        break;
    default:
        RejectLate(); /* unreachable after the 1..92 range check */
        return 1;
    }
#undef PRESENT_STATE_CASE
#undef ABSENT_STATE_CASE
reject_current:
    __asm__ volatile ("AiEvaluateAbility_reject_current:");
    candidateIndex++;
    if (candidateIndex < act->unk_0A)
        goto next_effect;
reject_all:
    return 0;
#undef RejectLate
#undef Reject
#undef effectEstimateMode
#undef effectEstimateAlt
#undef effectEstimate
#undef act
#undef target
#undef user
}
