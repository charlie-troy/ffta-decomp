typedef unsigned char u8;
typedef unsigned short u16;
typedef short s16;

struct Obj
{
    u8 filler_00[0x16];
    u8 unk_16;
    u8 filler_17[1];
    s16 unk_18;
};

/* Both temps must be int. Declaring limit as s16 to match the field type
 * allocates the two loads to the opposite registers. Found by decomp-permuter,
 * and it cleaned up without losing the match. */
u16 sub_08017B50(struct Obj *obj)
{
    int limit = obj->unk_18;
    int v = obj->unk_16;

    if (v > limit)
        v = limit;
    return v;
}
