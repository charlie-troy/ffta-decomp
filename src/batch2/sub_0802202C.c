typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u32 unk_00;
};

/* Positive form here: the target branches `bne` to the return-1 arm, the
 * mirror of the cluster-A flag getters. Polarity is per-function. */
u8 sub_0802202C(struct Obj *obj)
{
    if (obj->unk_00 & 0x10000)
        return 1;
    return 0;
}
