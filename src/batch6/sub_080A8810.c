typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0x2c0];
    u8 unk_2C0;
};

u8 *sub_080A8810(struct Obj *obj, int i)
{
    u8 *p = (u8 *)obj;

    if (obj->unk_2C0 < i)
        return 0;
    return p + 0x20 + i * 0x2c;
}
