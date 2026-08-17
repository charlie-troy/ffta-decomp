typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x24];
    u32 unk_24;
};

void sub_0809993C(struct Obj *obj, u8 a)
{
    struct Obj *p = obj;
    u32 v;

    if (a != 0)
        v = p->unk_24 | 0x20;
    else
        v = p->unk_24 & ~0x20;
    p->unk_24 = v;
}
