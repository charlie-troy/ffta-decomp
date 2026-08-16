typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0x40];
    u8 unk_40[1];
};

void sub_080CD544(struct Obj *obj, u8 i)
{
    if (obj != 0)
        obj->unk_40[i] |= 0x80;
}
