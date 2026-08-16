typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x10];
    u32 unk_10;
};

u8 sub_08068810(struct Obj *obj)
{
    return obj->unk_10 != 0;
}
