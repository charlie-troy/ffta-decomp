typedef unsigned char u8;
typedef unsigned short u16;

struct Obj
{
    u8 filler_00[0xc];
    u16 unk_0C;
};

/* The mask must be an int variable. As a literal, gcc proves (v >> 7) & 1 is
 * already 0 or 1, folds the == 1 away, and emits no branch at all. */
u8 sub_080DD580(struct Obj *obj)
{
    u16 v = obj->unk_0C;
    int mask = 1;
    u8 r = 0;

    if (((v >> 7) & mask) == 1)
        r = 1;
    return r;
}
