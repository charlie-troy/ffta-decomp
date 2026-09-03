/* FFTA shared type and struct registry, pret/SA3 style.
 *
 * agbcc is cc1 proper, so NOTHING may #include this file: every source is
 * self-contained by construction and must stay byte-matching. This header is
 * the registry of the project's agreed fixed-width typedefs and documented
 * struct layouts - a single place to copy definitions from and to keep the
 * projections in each source honest against, not a compile-time dependency.
 *
 * Structs here are the UNION of known fields from docs/*.md, with filler
 * covering what is not yet named. Sources that only touch part of a struct
 * keep a smaller projection with the same field names; when a projection and
 * this registry disagree, this registry is wrong or stale - fix it in the
 * same change.
 *
 * Evidence pointers live in docs/unit-struct.md, docs/ability-table.md and
 * docs/ai-evaluator-cases.md.
 */

#ifndef FFTA_H
#define FFTA_H

/* -- fixed-width base types (identical in every self-contained source) -- */

typedef unsigned char  u8;
typedef unsigned short u16;
typedef unsigned int   u32;
typedef signed   char  s8;
typedef signed   short s16;
typedef signed   int   s32;

/* -- Unit: the battle actor. Offsets are stat-id 0x00..0x44, exactly the
 * layout in docs/unit-struct.md; the "+0x.." comments are ROM offsets. -- */

struct Unit
{
    const void *nameText;        /* +0x00, encoded text rendered by sub_08025688 */
    u8 unitType;                 /* +0x04, stat id 0x01 */
    u8 baseJob;                  /* +0x05, stat id 0x02 */
    u8 race;                     /* +0x06, stat id 0x03 */
    u8 activeJob;                /* +0x07, stat id 0x04 */
    u8 secondaryJob;             /* +0x08, stat id 0x05 */
    u8 level;                    /* +0x09, stat id 0x06 */
    u8 experience;               /* +0x0A, stat id 0x07 */
    u8 innateElement;            /* +0x0B, stat id 0x08 */
    u8 resistances[9];           /* +0x0C..+0x14, stat ids 0x0A..0x12:
                                  * neutral, Fire, Wind, Earth, Water, Ice,
                                  * Lightning, Holy, Dark; 0 weak, 1 normal,
                                  * 2 nullify, 3 absorb, 4 resist */
    u8 pad_15[3];                /* +0x15..+0x17 */
    u16 hp;                      /* +0x18, stat id 0x13 */
    u16 maxHp;                   /* +0x1A, stat id 0x14 */
    u16 mp;                      /* +0x1C, stat id 0x15 */
    u16 maxMp;                   /* +0x1E, stat id 0x16 */
    u16 attack;                  /* +0x20, stat id 0x17 */
    u16 defense;                 /* +0x22, stat id 0x18 */
    u16 magicPower;              /* +0x24, stat id 0x19 */
    u16 resistance;              /* +0x26, stat id 0x1A */
    u16 persistentStatus;        /* +0x28, stat id 0x1B; bit 0x0040 Yellow
                                  * Card, bit 0x0800 persistent Zombie */
    u16 equipped[5];             /* +0x2A..+0x32, stat ids 0x1D..0x21 */
    u8 filler_34[0x9C];          /* +0x34: ability-state array, 12-byte header
                                  * plus one byte per race ability
                                  * (docs/unit-struct.md) */
    s16 chargeTime;              /* +0xD0, stat id 0x23 */
    s16 speed;                   /* +0xD2, stat id 0x24 */
    s16 ctCarry;                 /* +0xD4, stat id 0x25 */
    u16 judgePoints;             /* +0xD6, stat id 0x26 */
    u8 filler_D8[0x0F];          /* +0xD8: status-state pointer and the named
                                  * status countdowns, added here as matched */
    u8 recentTargetIds;          /* +0xE7, stat id 0x37; two 4-bit unit ids,
                                  * newest in the low nibble */
    u8 filler_E8[0xF1 - 0xE8];
    u8 koInflictedCount;         /* +0xF1 */
    u8 koSufferedCount;          /* +0xF2 */
    u8 otherRemovalCount;        /* +0xF3; Wyrmtamer and other removal outcomes */
    u8 parleyRemovalCount;       /* +0xF4; also modifies purge hit formulas */
    u8 oustRemovalCount;         /* +0xF5 */
    u8 tileX;                    /* +0xF6 */
    u8 tileY;                    /* +0xF7 */
    u8 tileHeight;               /* +0xF8 */
    u8 savedTileX;               /* +0xF9; snapshot copied from tileX */
    u8 savedTileY;               /* +0xFA; snapshot copied from tileY */
    u8 battleListIndex;          /* +0xFB */
    u8 filler_FC[4];             /* movement profile pointer at +0xFC */
};

/* -- Ability: one 28-byte ability-table entry, docs/ability-table.md. -- */

struct Ability
{
    u8 filler_00[0x18];
    u8 aiCondition;              /* +0x18: 0 normal, 1 judge, 2 mug, 3 sensor,
                                  * ...; 306 of 347 retail abilities are 0 */
    u8 aiBehaviour;              /* +0x19: 0 unknown, 1 low HP, 2 healthy,
                                  * 3 last resort */
    u8 aiPriority;               /* +0x1A: higher means MORE likely; the
                                  * direction was proven against published docs */
    u8 pad_1B;                   /* always 0 in retail */
};

/* -- Action: an in-progress action, u16[] in the original; only some fields
 * are known. Used by the AI evaluator, sub_080C32C0. -- */

struct Action
{
    u16 abilityId;               /* [0] index into the ability table */
    u16 unk_02[2];               /* [1..2] */
    u16 effectId;                /* [3] selects the 92-case switch, via +2 */
    u16 unk_08;                  /* [4] */
    u16 unk_0A;                  /* [5] must be non-zero */
    s16 unk_0C;                  /* [6] sign is tested repeatedly */
    s16 unk_0E;                  /* [7] compared against 0x1E */
    s8  unk_10;                  /* byte +0x10, passed signed to sub_0812F1DC */
    u8  flags_11;                /* byte +0x11, bits 0 and 1 reject */
};

/* -- AI evaluator working frame (retail reserves 20 bytes). -- */

struct AiEvaluatorFrame
{
    s16 effectEstimate[2];
    s16 effectEstimateAlt[2];
    s16 effectEstimateMode[2];
    struct Action *action;
};

/* -- AI strategy profile knobs compiled into the evaluator. Retail values
 * are 10 and 49; the proof mod sets 100/101 (make mod-ai-always-pass). -- */

#ifndef FFTA_AI_SELF_STATUS_THRESHOLD
#define FFTA_AI_SELF_STATUS_THRESHOLD 10
#endif
#ifndef FFTA_AI_OTHER_STATUS_THRESHOLD
#define FFTA_AI_OTHER_STATUS_THRESHOLD 49
#endif

#endif /* FFTA_H */
