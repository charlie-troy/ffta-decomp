typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0xc];
    u8 *unk_0C;
};

#define gUnk_03002710 ((struct Obj *)0x03002710)

void sub_0804E014(u8 a)
{
    u8 *p = gUnk_03002710->unk_0C;
    int seven = 7;
    int zero = 0;
    int v;

    if (a == 0)
        v = seven;
    else
        v = zero;
    *p = v;
}
