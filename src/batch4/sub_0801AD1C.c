typedef unsigned char u8;

/* Must be a real extern symbol, not a cast literal address. With a literal,
 * gcc folds base + 0x2000 into a second literal-pool word; with a symbol it
 * materialises 0x2000 in a register and adds at runtime, as the ROM does.
 * The address is supplied by data/symbols.txt via the linker script. */
extern u8 gUnk_020091A0[];

u8 *sub_0801AD1C(u8 a)
{
    u8 *p = gUnk_020091A0;

    if (a != 0)
        p += 0x2000;
    return p;
}
