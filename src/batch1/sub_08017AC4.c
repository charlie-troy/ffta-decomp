typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

struct Obj
{
    u32 unk_00;
    u32 unk_04;
    u8 filler_08[8];
    u16 unk_10;
};

void sub_08017AC4(struct Obj *obj, u32 a, u32 b)
{
    obj->unk_10 |= 2;
    obj->unk_00 = a;
    obj->unk_04 = b;
}
