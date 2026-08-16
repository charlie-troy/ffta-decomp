/* Best hand-found spelling: 20 bytes off. The complement kept as its own int
 * variable is worth 3 bytes over writing `& ~mask` inline. */
typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0xe8];
    u8 flags;
};

void sub_080CDD88(struct Obj *obj, u8 set)
{
    u8 *p = &obj->flags;
    int notmask = ~0x10;
    int mask = 0x10;
    int v;

    v = *p & notmask;
    *p = v;
    if (set)
        *p = v | mask;
}
