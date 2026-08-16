typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[4];
    u32 unk_04;
};

u8 sub_080DD598(struct Obj *obj)
{
    return obj->unk_04 != 0;
}
