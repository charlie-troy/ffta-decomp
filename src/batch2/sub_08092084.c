typedef unsigned char u8;
typedef short s16;

/* The intermediate `q2` is load-bearing: assigning &p[i * 2] straight into q
 * makes gcc compute `offset + p` for the second store instead of `p + offset`,
 * a 2-byte difference. Found by decomp-permuter. */
void sub_08092084(u8 *p, s16 i, u8 a, u8 b)
{
    u8 *q = &p[i * 2];
    u8 *q2;

    *q = a;
    p++;
    q2 = &p[i * 2];
    q = q2;
    *q = b;
}
