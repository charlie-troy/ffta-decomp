typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0xe8];
    u8 flags;
};

u8 sub_080CD92C(struct Obj *obj)
{
    if (!(obj->flags & 0x40))
        return 0;
    return 1;
}
