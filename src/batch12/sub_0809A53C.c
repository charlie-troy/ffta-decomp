typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x44];
    u32 unk_44;
};

extern u32 sub_08021E3C(u32 a);

u32 sub_0809A53C(struct Obj *obj)
{
    return sub_08021E3C(obj->unk_44);
}
