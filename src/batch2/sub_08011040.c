typedef unsigned char u8;
typedef unsigned short u16;

struct Obj
{
    u8 filler_00[0x1d];
    u8 unk_1D;
    u16 unk_1E;
    u16 unk_20;
    u16 unk_22;
};

u8 sub_08011040(struct Obj *obj, u16 *a, u16 *b, u16 *c)
{
    *a = obj->unk_1E;
    *b = obj->unk_20;
    *c = obj->unk_22;
    return obj->unk_1D;
}
