typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x24];
    u32 unk_24;
};

/* Cluster-B setter shape on a u32 field, with the condition inverted: the bit
 * is set when the argument is zero. Unlike cluster B this one needs no
 * duplicated branch, but the field must be loaded before the mask constants
 * are declared. */
void sub_0809A260(struct Obj *obj, int set)
{
    struct Obj *p = obj;
    u32 v = p->unk_24;
    int notmask = ~1;
    int mask = 1;

    v = v & notmask;
    p->unk_24 = v;
    if (!set)
        p->unk_24 = v | mask;
}
