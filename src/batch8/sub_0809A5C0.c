typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x24];
    u32 unk_24;
};

/* Same shape as sub_0809993C; ternary rather than if/else. */
void sub_0809A5C0(struct Obj *obj, u8 a)
{
    struct Obj *p = obj;

    p->unk_24 = a != 0 ? (p->unk_24 | 8) : (p->unk_24 & ~8);
}
