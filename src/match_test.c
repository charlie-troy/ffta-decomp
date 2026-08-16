// Match-test candidate for sub_08005BB0 (file offset 0x005bb0, 18 bytes, 55 callers).
//
// Original:
//     push {lr}
//     movs r1, #0
//     ldrh r0, [r0, #0x14]
//     cmp  r0, #2
//     bne  .L
//     movs r1, #1
// .L: adds r0, r1, #0
//     pop  {r1}
//     bx   r1
//
// agbcc is cc1 proper, so this file must not #include anything.

typedef unsigned char u8;
typedef unsigned short u16;

struct Unit
{
    u8 filler_00[0x14];
    u16 state;
};

u8 sub_08005BB0(struct Unit *unit)
{
    return unit->state == 2;
}
