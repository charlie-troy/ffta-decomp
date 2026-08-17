typedef unsigned char u8;

extern u8 gUnk_03000028;

/* A pure leaf: no push, returns with bx lr. tools/find_leaf_funcs.py requires
 * a push {..., lr} prologue and was blind to this whole class; luvdis found it.
 * Ghidra's decompilation was a single line. */
void sub_08001CD0(void)
{
    gUnk_03000028 ^= 1;
}
