typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0xe8];
    u8 flags;
};

void sub_080CDD88(struct Obj *obj, u8 set)
{
    int v = obj->flags & ~0x10;

    obj->flags = v;
    if (set)
        obj->flags = v | 0x10;
}
