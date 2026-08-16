typedef unsigned char u8;
typedef unsigned short u16;

struct Obj
{
    u8 filler_00[0x18];
    u16 unk_18;
};

u8 sub_080C8280(struct Obj *obj)
{
    u8 r = 0;

    if (obj != 0 && obj->unk_18 == 0)
        r = 1;
    return r;
}
