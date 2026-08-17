typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x30];
    u32 unk_30;
};

void sub_080DBEB4(struct Obj *obj, u8 a)
{
    struct Obj *p = obj;
    int notmask = ~1;
    int mask = 1;
    u32 v;

    if (a != 0)
        v = p->unk_30 & notmask;
    else
        v = p->unk_30 | mask;
    p->unk_30 = v;
}
