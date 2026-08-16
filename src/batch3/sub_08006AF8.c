typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[8];
    u32 *unk_08;
    u8 *unk_0C;
};

void sub_08006AF8(struct Obj *obj, u8 i, u32 a, u8 b)
{
    obj->unk_08[i] = a;
    obj->unk_0C[i] = b;
}
