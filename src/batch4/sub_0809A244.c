typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x24];
    u32 unk_24;
};

void sub_0809A244(struct Obj *obj, int set)
{
    struct Obj *p = obj;
    u32 v = p->unk_24;
    int notmask = ~0x10;
    int mask = 0x10;

    v = v & notmask;
    p->unk_24 = v;
    if (!set)
        p->unk_24 = v | mask;
}
