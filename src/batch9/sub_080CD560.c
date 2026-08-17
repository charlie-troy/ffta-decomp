typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0x40];
    u8 unk_40[1];
};

u8 sub_080CD560(struct Obj *obj, u8 i)
{
    if (obj == 0)
        return 0;
    if ((obj->unk_40[i] & 0x80) == 0)
        return 0;
    return 1;
}
