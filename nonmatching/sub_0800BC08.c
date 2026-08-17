typedef unsigned char u8;
typedef unsigned short u16;

struct Entry
{
    u8 filler_00[0x18];
    u16 unk_18;
    u16 unk_1A;
    u8 filler_1C[0xc];
};

#define gUnk_02009000 ((struct Entry *)0x02009000)

void sub_0800BC08(u8 i, u16 a, u16 b)
{
    gUnk_02009000[i].unk_18 = a;
    gUnk_02009000[i].unk_1A = b;
}
