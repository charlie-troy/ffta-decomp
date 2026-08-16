typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0x26];
    u8 unk_26;
};

/* The global lives at 0x0200918C. Until a symbol file and linker script exist,
 * addressing it through a macro puts the right constant in the literal pool. */
#define gUnk_0200918C (*(struct Obj **)0x0200918C)

void sub_08013364(void)
{
    struct Obj *p = gUnk_0200918C;

    if (p != 0)
        p->unk_26 = 0;
}
