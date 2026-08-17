typedef unsigned short u16;
typedef short s16;

/* Six parameters: the last two arrive on the stack, which is why the prologue
 * loads from sp after pushing r4/r5/lr. */
void sub_0801CA78(s16 a, int b, s16 c, u16 *pa, u16 *pb, u16 *pc)
{
    *pa = a * 32 + 0x10;
    *pb = b * 16;
    *pc = c * 32 + 0x10;
}
