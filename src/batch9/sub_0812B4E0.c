typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0x2f4];
    u8 unk_2F4;
};

/* Returns a pointer to the next 28-byte slot and bumps the count. */
u8 *sub_0812B4E0(struct Obj *obj)
{
    u8 count = obj->unk_2F4;
    u8 *p = (u8 *)obj + 0x2a0 + count * 28;

    obj->unk_2F4 = count + 1;
    return p;
}
