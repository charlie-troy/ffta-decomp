typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[3];
    u8 unk_03;
    u8 filler_04[4];
    u32 *unk_08;
};

void sub_08006BE0(struct Obj *obj, u8 i)
{
    struct Obj *p = obj;
    u32 *arr;

    if (p->unk_03 == 0xff)
        return;
    arr = p->unk_08;
    arr[i] |= 0x80000000;
}
