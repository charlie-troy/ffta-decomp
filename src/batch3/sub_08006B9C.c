typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[3];
    u8 unk_03;
    u8 filler_04[4];
    u32 *unk_08;
};

/* The field is read twice rather than cached before the compare. Caching it
 * first puts the index in r1 and the struct pointer in r0; the original wants
 * the reverse. Found by decomp-permuter. */
void sub_08006B9C(struct Obj *obj)
{
    struct Obj *p = obj;
    u32 *arr;
    u8 i;

    if (p->unk_03 == 0xff)
        return;
    i = p->unk_03;
    arr = p->unk_08;
    arr[i] = 0;
}
