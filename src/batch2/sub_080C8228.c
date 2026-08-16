typedef unsigned char u8;

struct Obj
{
    u8 filler_00[7];
    u8 unk_07;
};

u8 sub_080C8228(struct Obj *obj)
{
    u8 r = 0;

    if (obj != 0 && obj->unk_07 == 0x18)
        r = 1;
    return r;
}
