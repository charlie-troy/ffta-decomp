typedef unsigned char u8;
typedef unsigned short u16;

struct Obj
{
    u8 filler_00[0xa0];
    u16 unk_A0;
    u16 unk_A2;
};

#define gUnk_020020D0 ((struct Obj *)0x020020D0)

u16 sub_0800A024(void)
{
    u16 v = gUnk_020020D0->unk_A2;

    if (v == 0)
        v = gUnk_020020D0->unk_A0;
    return v;
}
