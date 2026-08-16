typedef unsigned char u8;
typedef unsigned short u16;
typedef short s16;

struct Obj
{
    u8 filler_00[0x16];
    u8 unk_16;
    u8 filler_17[1];
    s16 unk_18;
};

u16 sub_08017B50(struct Obj *obj)
{
    int v = obj->unk_16;
    s16 limit = obj->unk_18;

    if (v > limit)
        v = limit;
    return v;
}
