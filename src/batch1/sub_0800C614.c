typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x10];
    u16 unk_10;
    u8 filler_12[2];
    u32 unk_14;
};

u32 sub_0800C614(struct Obj *obj)
{
    u16 v = obj->unk_10;
    u32 r = 0;

    if (v != 0)
        r = obj->unk_14;
    return r;
}
