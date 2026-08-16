typedef unsigned char u8;
typedef int s32;

struct Obj
{
    u8 filler_00[0x28];
    s32 unk_28;
};

u8 sub_08007880(struct Obj *obj)
{
    return obj->unk_28 <= 0;
}
