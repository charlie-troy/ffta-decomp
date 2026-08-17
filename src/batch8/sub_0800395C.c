typedef unsigned char u8;

struct Obj
{
    struct Obj *unk_00;
};

extern struct Obj *gUnk_030034B8;

u8 sub_0800395C(void)
{
    struct Obj *p = gUnk_030034B8;

    if (p == 0)
        return 0;
    return p->unk_00 == 0 ? 0 : 1;
}
