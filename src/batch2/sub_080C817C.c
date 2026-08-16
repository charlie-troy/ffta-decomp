typedef unsigned char u8;

struct Obj
{
    u8 filler_00[4];
    u8 unk_04;
};

u8 sub_080C817C(struct Obj *obj)
{
    u8 r = 0;

    if (obj != 0 && obj->unk_04 > 1)
        r = 1;
    return r;
}
