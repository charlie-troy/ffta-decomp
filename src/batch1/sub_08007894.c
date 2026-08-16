typedef unsigned char u8;
typedef short s16;

struct Obj
{
    u8 filler_00[0x14];
    s16 unk_14;
};

u8 sub_08007894(struct Obj *obj)
{
    return obj->unk_14 <= 0;
}
