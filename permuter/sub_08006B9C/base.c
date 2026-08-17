typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[3];
    u8 unk_03;
    u8 filler_04[4];
    u32 *unk_08;
};

void sub_08006B9C(struct Obj *obj)
{
    struct Obj *p = obj;
    int i = p->unk_03;
    u32 *arr;

    if (i == 0xff)
        return;
    arr = p->unk_08;
    arr[i] = 0;
}
