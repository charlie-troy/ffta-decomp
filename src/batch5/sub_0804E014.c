typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0xc];
    u8 *unk_0C;
};

extern struct Obj gUnk_03002710;

/* Ternary, not if/else. An if/else with a shared temp collapses to
 * init-then-conditional-set, which removes the unconditional branch. gcc dumps
 * a pending literal pool at a barrier, and that branch is the barrier, so
 * losing it also moves the pool to the end of the function. The mid-function
 * pool in the target is a consequence of the two-armed structure, not a
 * separate behaviour. */
void sub_0804E014(u8 a)
{
    u8 *p = gUnk_03002710.unk_0C;

    *p = a == 0 ? 7 : 0;
}
