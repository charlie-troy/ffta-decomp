typedef unsigned char u8;

#define gUnk_020091A0 ((u8 *)0x020091A0)

/* The offset must be an int variable. As a literal, gcc folds base + 0x2000
 * into a second literal-pool constant instead of materialising 0x2000 in a
 * register and adding at runtime. */
u8 *sub_0801AD1C(u8 a)
{
    u8 *p = gUnk_020091A0;
    int off = 0x2000;

    if (a != 0)
        p += off;
    return p;
}
