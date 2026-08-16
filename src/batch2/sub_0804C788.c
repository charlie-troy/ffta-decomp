typedef unsigned char u8;
typedef unsigned short u16;

struct Entry
{
    u8 filler_00[0x10];
    u8 unk_10;
    u8 unk_11;
    u8 filler_12[0xa];
};

void sub_0804C788(struct Entry *base, u16 i, u8 a, u8 b)
{
    base[i].unk_10 = a;
    base[i].unk_11 = b;
}
