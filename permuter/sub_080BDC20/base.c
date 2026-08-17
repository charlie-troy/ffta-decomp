typedef unsigned char u8;
typedef unsigned int u32;

/* Best so far: 13 bytes off.
 *
 * The index arithmetic matches exactly with a 2D array, which folds each
 * index's scale into its own truncation shift (b << 2, c << 6). Writing it as
 * explicit byte-offset arithmetic on a u8* is worse, 17 off, so that is not it.
 *
 * Remaining: the target sums both offsets and adds the base last
 * (adds r1,r1,r2 then adds r0,r0,r1) while agbcc folds the base in earlier,
 * and the ternary routes the result through an extra temp instead of moving
 * straight into r0. Structure is right, allocation is not: a permuter case. */
u32 sub_080BDC20(u32 (*arr)[16], u8 b, u8 c)
{
    u32 v = arr[c][b];

    return v == -1 ? 0 : v;
}
