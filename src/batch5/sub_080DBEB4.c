typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x30];
    u32 unk_30;
};

/* Ternary rather than if/else, for the same reason as sub_0809993C. */
void sub_080DBEB4(struct Obj *obj, u8 a)
{
    struct Obj *p = obj;

    p->unk_30 = a != 0 ? (p->unk_30 & ~1) : (p->unk_30 | 1);
}
