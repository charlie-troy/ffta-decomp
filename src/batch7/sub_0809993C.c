typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x24];
    u32 unk_24;
};

/* Must be a ternary, not an if/else. An if/else puts the loaded value in r1
 * and the constant in r0; the ternary reverses that to match, and also emits
 * the pointer temp before the parameter truncation. Found by probing eight
 * spellings; see docs/matching-notes.md. */
void sub_0809993C(struct Obj *obj, u8 a)
{
    struct Obj *p = obj;

    p->unk_24 = a != 0 ? (p->unk_24 | 0x20) : (p->unk_24 & ~0x20);
}
