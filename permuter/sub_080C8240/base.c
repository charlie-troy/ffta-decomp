typedef unsigned char u8;
typedef unsigned short u16;

struct Obj
{
    u8 filler_00[0x28];
    u16 flags;
};

u8 sub_080C8240(struct Obj *obj)
{
    u16 v;

    if (obj == 0)
        return 0;
    v = obj->flags & 0x8000;
    return v != 0;
}
