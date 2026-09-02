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
extern int  AbilityPropWide(int abilityId, int propId)
    __asm__("AbilityProp");
extern u16  AbilityMpCost(struct Unit *u, u16 abilityId); /* sub_0812ED98 */
extern int  AbilityMpCostWide(struct Unit *u, int abilityId)
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
extern u8 sub_0812F1DCWide(int v) __asm__("sub_0812F1DC");
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
extern void sub_08133BB4Wide(struct Unit *copy, int effectId)
    __asm__("sub_08133BB4");

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

static __inline__ int AbilityMpCostForAi(struct Unit *user, int abilityId)
{
    register int cost __asm__("r0");

    AbilityMpCostWide(user, abilityId);
    __asm__ volatile (
        "lsl %0, %0, #16\n"
        "lsr %0, %0, #16"
        : "=r" (cost));
    return cost;
}

static __inline__ int AbilityAiBehaviourForAi(int abilityId)
{
    register u32 offset __asm__("r0");

    __asm__ volatile (
        "mov r1, %1\n\t"
        "lsl %0, r1, #3\n\t"
        "sub %0, %0, r1\n\t"
        "lsl %0, %0, #2"
        : "=r" (offset)
        : "r" (abilityId)
        : "r1", "memory");
    offset = (u32)((u8 *)gAbilityTable + offset);
    __asm__ volatile (
        "ldrb %0, [%0, #25]"
        : "+r" (offset));
    return offset;
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
    s16 probabilityRoll;
    int probabilityPass;
    int stateResult;
    register int rawStateResult __asm__("r0");
    u16 *abilityList;
    register u16 *effectEntry __asm__("r6");
    struct Unit *unitCopy;
    int count, i, found, changed;
    u8 saved;
    register struct Unit *actor __asm__("r10") = user;
    register struct Unit *subject __asm__("r8") = target;
    register u32 effectOffset __asm__("r9");
    register u16 *effectBase __asm__("r7");
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
    {
        register int firstAbility __asm__("r1");
        __asm__ volatile (
            "ldr r0, [sp, #12]\n\t"
            "ldrh %0, [r0]"
            : "=r" (firstAbility)
            :
            : "r0");
        if (firstAbility == 0x109 &&
            !sub_080C8240(user) && !sub_080C8260(user))
            Reject();
    }

    if (checkCost)
    {
        register int propertyAbility __asm__("r0");
        register int costAbility __asm__("r1");
        register int mpDifference __asm__("r1");

        __asm__ volatile (
            "ldr r1, [sp, #12]\n\t"
            "ldrh %0, [r1]"
            : "=r" (propertyAbility)
            :
            : "r1");
        if (!AbilityPropWide(propertyAbility, 0x13)) /* flag bit 8 */
            Reject();

        /* Reject when the user cannot afford it. The subtraction is done in
         * 16 bits and tested for sign, so it is an unsigned MP < cost test. */
        __asm__ volatile (
            "ldr r2, [sp, #12]\n\t"
            "ldrh %0, [r2]"
            : "=r" (costAbility)
            :
            : "r2");
        AbilityMpCostForAi(user, costAbility);
        __asm__ volatile (
            "mov r2, r10\n\t"
            "ldrh %0, [r2, #28]\n\t"
            "sub %0, %0, r0\n\t"
            "lsl %0, %0, #16"
            : "=r" (mpDifference)
            :
            : "r0", "r2");
        if (mpDifference < 0)
            Reject();
    }

    /* AI behaviour 2 means "use on a healthy target". Reject when the target
     * is already below half HP: no point debuffing something about to die.
     * See docs/ability-table.md; this is the rule most worth tuning. */
    if (act->abilityId != 0
        && AbilityAiBehaviourForAi(act->abilityId) == 2
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

    if (sub_080CDB54(user))
    {
        register int userActionValue __asm__("r0");
        __asm__ volatile (
            "ldr r2, [sp, #12]\n\t"
            "mov r1, #12\n\t"
            "ldrsh %0, [r2, r1]"
            : "=r" (userActionValue)
            :
            : "r1", "r2");
        if (userActionValue < 0)
            Reject();
    }

    {
        register int reflectAbility __asm__("r0");
        __asm__ volatile (
            "ldr r2, [sp, #12]\n\t"
            "ldrh %0, [r2]"
            : "=r" (reflectAbility)
            :
            : "r2");
        if (AbilityPropWide(reflectAbility, 0x12) && /* flag bit 7 */
            sub_0812F154(target))
        {
            register int reflectActionValue __asm__("r0");
            __asm__ volatile (
                "ldr r1, [sp, #12]\n\t"
                "mov r2, #12\n\t"
                "ldrsh %0, [r1, r2]"
                : "=r" (reflectActionValue)
                :
                : "r1", "r2");
            if (reflectActionValue < 0)
                Reject();
        }
    }

    e = act->unk_10;
    actionValue = act->unk_0C;
    isNegative = actionValue < 0;

    if (actionValue >= 0 || isNegative)
    {
        if (!(sub_081341BC(user, target) || isNegative))
            goto check_final_value;

        if (!isNegative)
        {
            register int actionThreshold __asm__("r0");
            __asm__ volatile (
                "ldr r2, [sp, #12]\n\t"
                "mov r1, #14\n\t"
                "ldrsh %0, [r2, r1]"
                : "=r" (actionThreshold)
                :
                : "r1", "r2");
            if (actionThreshold < 0x1E)
                Reject();
        }

        mode = sub_0812E6A4(target) & 0xFFFF;
        if (!sub_0812F0E4(target, (signed char)target->tileX,
                          (signed char)target->tileY))
            mode = 0;
        {
            register int modeAbility __asm__("r0");
            __asm__ volatile (
                "ldr r2, [sp, #12]\n\t"
                "ldrh %0, [r2]"
                : "=r" (modeAbility)
                :
                : "r2");
            if (modeAbility != 0 && AbilityPropWide(modeAbility, 0x11))
                mode = 0;                            /* flag bit 6 */
        }

        switch (mode)
        {
        case 4:
            if (act->abilityId == 0)
                goto check_final_value;
            if (!AbilityProp(act->abilityId, 0x1B))
                goto check_reflect;
            Reject();
        case 5:
        {
            register int modeAbilityId __asm__("r0");
            __asm__ volatile (
                "ldr r2, [sp, #12]\n\t"
                "ldrh %0, [r2]"
                : "=r" (modeAbilityId)
                :
                : "r2");
            if (modeAbilityId != 0)
                goto check_reflect_nonzero;
            Reject();
        }
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
        {
            register int modeAbilityId __asm__("r0");
            register s16 *estimatePtr __asm__("r4");
            __asm__ volatile (
                "ldr r1, [sp, #12]\n\t"
                "ldrh %0, [r1]"
                : "=r" (modeAbilityId)
                :
                : "r1");
            if (modeAbilityId != 0)
                goto check_reflect_nonzero;
            estimatePtr = effectEstimateAlt;
            sub_0812F0D8(user, estimatePtr);
            estimateValue = (u16)estimatePtr[0];
            goto check_range_code;
        }
        case 7:
        case 8:
        case 10:
        {
            register int modeAbilityId __asm__("r0");
            register s16 *estimatePtr __asm__("r4");
            __asm__ volatile (
                "ldr r1, [sp, #12]\n\t"
                "ldrh %0, [r1]"
                : "=r" (modeAbilityId)
                :
                : "r1");
            if (modeAbilityId != 0)
                goto check_reflect_nonzero;
            estimatePtr = effectEstimateMode;
            sub_0812F0D8(user, estimatePtr);
            rangeCode = sub_0812EED0(user, (u16)estimatePtr[0]);
            if (mode == 7 && rangeCode <= 1)
                Reject();
            if (rangeCode <= 2)
                e >>= 1;
            if (isNegative != 1)
                goto check_reflect;
            Reject();
        }
        case 11:
        {
            register int modeAbilityId __asm__("r0");
            __asm__ volatile (
                "ldr r2, [sp, #12]\n\t"
                "ldrh %0, [r2]"
                : "=r" (modeAbilityId)
                :
                : "r2");
            if (modeAbilityId == 0)
                goto check_final_value;
            if (AbilityPropWide(modeAbilityId, 0x1A))
            {
                s16 cost = (s16)AbilityMpCost(target, act->abilityId);
                if ((u32)cost <= (u32)UnitStat(target, 0x15))
                    e >>= 1;
            }
            goto check_reflect;
        }
        default:
            break;
        }

check_reflect:
    {
        register int reflectAbilityId __asm__("r0");
        __asm__ volatile (
            "ldr r1, [sp, #12]\n\t"
            "ldrh %0, [r1]"
            : "=r" (reflectAbilityId)
            :
            : "r1");
        if (reflectAbilityId == 0)
            goto check_final_value;
    }
check_reflect_nonzero:
        if (!sub_0812F154(target))
            goto check_final_value;
    {
        register int reflectAbilityId __asm__("r0");
        __asm__ volatile (
            "ldr r2, [sp, #12]\n\t"
            "ldrh %0, [r2]"
            : "=r" (reflectAbilityId)
            :
            : "r2");
        if (AbilityPropWide(reflectAbilityId, 0x12))
            Reject();
    }
    }

check_final_value:
    if (!sub_0812F1DCWide((u16)e))
        Reject();
    __asm__ volatile (
        "mov r0, #0\n\t"
        "str r0, %0\n\t"
        "ldr r1, [sp, #12]\n\t"
        "ldrh r1, [r1, #10]\n\t"
        "cmp r0, r1\n\t"
        "blt 1f\n\t"
        "bl AiEvaluateAbility_reject_all\n"
        "1:"
        : "=m" (candidateIndex)
        :
        : "r0", "r1", "cc");

next_effect:
    __asm__ volatile ("AiEvaluateAbility_next_effect:");
    {
    register int effectId __asm__("r2");
    int reachable;

    /* The candidate effects are the u16 list at action +4. Failed entries
     * advance through the list; successful entries return immediately. */
    __asm__ volatile (
        "ldr r2, [sp, #16]\n\t"
        "lsl r0, r2, #1\n\t"
        "ldr r1, [sp, #12]\n\t"
        "add r1, #4\n\t"
        "add %0, r1, r0\n\t"
        "ldrh %1, [%0]\n\t"
        "mov %2, r0\n\t"
        "mov %3, r1"
        : "=r" (effectEntry), "=r" (effectId),
          "=r" (effectOffset), "=r" (effectBase)
        :
        : "r0", "r1");
    if (effectId == 0)
        RejectLate();

    /* A status bit is briefly cleared around the reachability test, then put
     * back, so the test is done as though the unit did not have it. */
    saved = sub_080CD8FC(target);
    sub_080CDD88(target, 0);
    reachable = sub_08133A58(target, *effectEntry);
    sub_080CDD88(target, saved);
    if (!reachable)
        RejectLate();

    }

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
    {
        register int simulatedEffect __asm__("r1");
        register int simulatedChanged __asm__("r4");
        unitCopy = (struct Unit *)sub_08022840(0x108);
        sub_08142250(unitCopy, target, 0x108,
                     *(const void **)0x0836D4BC);
        __asm__ volatile (
            "mov %0, r9\n\t"
            "add r0, r7, %0\n\t"
            "ldrh %0, [r0]"
            : "=r" (simulatedEffect)
            :
            : "r0");
        sub_08133BB4Wide(unitCopy, simulatedEffect);
        __asm__ volatile (
            "mov r0, r8\n\t"
            "add r0, #232\n\t"
            "mov r1, %1\n\t"
            "add r1, #232\n\t"
            "ldr r2, [r0]\n\t"
            "ldr r0, [r1]\n\t"
            "mov %0, #1\n\t"
            "cmp r2, r0\n\t"
            "bne 1f\n\t"
            "mov r0, r8\n\t"
            "add r0, #236\n\t"
            "mov r2, %1\n\t"
            "add r2, #236\n\t"
            "ldr r1, [r0]\n\t"
            "ldr r0, [r2]\n\t"
            "eor r1, r0\n\t"
            "neg r0, r1\n\t"
            "orr r0, r1\n\t"
            "lsr %0, r0, #31\n"
            "1:"
            : "=r" (simulatedChanged)
            : "r" (unitCopy)
            : "r0", "r1", "r2", "cc");
        sub_08022854(unitCopy);
        return simulatedChanged;
    }
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
        if (user != target)
            RejectLate();
        if ((u16)sub_080C13C8(target) == 0)
            goto probability_fail;
        goto probability_pass;
    ABSENT_STATE_CASE(17, sub_080CDA1C);
    ABSENT_STATE_CASE(19, sub_080CDADC);
    ABSENT_STATE_CASE(20, sub_080CDA34);
    case 4:
    case 6:
    case 21:
    {
        register int positiveActionValue __asm__("r0");
        __asm__ volatile (
            "ldr r2, [sp, #12]\n\t"
            "mov r1, #12\n\t"
            "ldrsh %0, [r2, r1]"
            : "=r" (positiveActionValue)
            :
            : "r1", "r2");
        if (positiveActionValue <= 0)
            RejectLate();
        return 1;
    }
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
    {
        register int negativeActionValue __asm__("r0");
        register int currentHpForThird __asm__("r4");
        __asm__ volatile (
            "ldr r2, [sp, #12]\n\t"
            "mov r1, #12\n\t"
            "ldrsh %0, [r2, r1]"
            : "=r" (negativeActionValue)
            :
            : "r1", "r2");
        if (negativeActionValue >= 0)
            Reject();
        currentHpForThird = UnitStat(target, STAT_HP);
        sub_08142AB0(UnitStat(target, STAT_MAX_HP), 3);
        __asm__ volatile (
            "cmp r4, r0\n\t"
            "bgt 1f\n\t"
            "b AiEvaluateAbility_accept_current\n"
            "1:\n\t"
            "bl AiEvaluateAbility_reject_all"
            :
            : "r" (currentHpForThird)
            : "cc");
    }
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
            !sub_080CD95C(target) || !sub_080CD974(target))
            return 1;
        sub_080CDB24(target);
        __asm__ volatile (
            "lsl r0, r0, #24\n\t"
            "cmp r0, #0\n\t"
            "beq 1f\n\t"
            "b AiEvaluateAbility_reject_current\n"
            "1:\n\t"
            "bl AiEvaluateAbility_accept_current"
            :
            :
            : "r0", "cc");
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
    {
        register int itemIndex __asm__("r5");
        itemIndex = 0;
        adjustedRange = 0x1D000000;
        do
        {
            sub_080CA7A4(
                (u16)UnitStat(target, (u8)(adjustedRange >> 24)), 3);
            __asm__ volatile (
                "cmp r0, #26\n\t"
                "bhi 1f\n\t"
                "cmp r0, #24\n\t"
                "bcc 1f\n\t"
                "bl AiEvaluateAbility_accept_current\n"
                "1:"
                :
                :
                : "cc");
            __asm__ volatile (
                "mov r2, #128\n\t"
                "lsl r2, r2, #17\n\t"
                "add %0, %0, r2"
                : "+r" (adjustedRange)
                :
                : "r2");
            itemIndex++;
        }
        while (itemIndex <= 4);
        RejectLate();
        break;
    }
    ABSENT_STATE_CASE(51, sub_080CDAC4);
    ABSENT_STATE_CASE(52, sub_080CDAAC);
    case 55:
    {
        register int currentHpForThird __asm__("r4");
        if (!AiPassesStatusProbability(user, target))
            RejectLate();
        if (sub_080CDA4C(target))
            RejectLate();
        currentHpForThird = UnitStat(target, STAT_HP);
        if (currentHpForThird >
            sub_08142AB0(UnitStat(target, STAT_MAX_HP), 3))
            RejectLate();
        return 1;
    }
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
    {
        register int yellowCardEnabled __asm__("r0");
        __asm__ volatile (
            "ldr %0, AiEvaluateAbility_case92_literals\n\t"
            "ldr r1, AiEvaluateAbility_case92_literals + 4\n\t"
            "add %0, %0, r1\n\t"
            "ldrb %0, [%0]"
            : "=r" (yellowCardEnabled)
            :
            : "r1");
        if (yellowCardEnabled == 0)
            RejectLate();
        sub_080C832C(target);
        __asm__ volatile ("lsl %0, %0, #24" : "=r" (rawStateResult));
        if (rawStateResult)
            RejectLate();
        __asm__ volatile ("" ::: "memory");
        return 1;
    }
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
    __asm__ volatile (
        "ldr r2, [sp, #16]\n\t"
        "add r2, #1\n\t"
        "str r2, [sp, #16]\n\t"
        "ldr r0, [sp, #12]\n\t"
        "ldrh r0, [r0, #10]\n\t"
        "cmp r2, r0\n\t"
        "bge AiEvaluateAbility_reject_all\n\t"
        "bl AiEvaluateAbility_next_effect"
        :
        :
        : "r0", "r2", "cc", "memory");
reject_all:
    __asm__ volatile ("AiEvaluateAbility_reject_all:");
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

__asm__(
    ".align 2, 0\n"
    "AiEvaluateAbility_case92_literals:\n"
    ".word gEwram\n"
    ".word 15411\n"
    ".size AiEvaluateAbility, .-AiEvaluateAbility");
