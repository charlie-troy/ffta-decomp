typedef unsigned char u8;
typedef unsigned int u32;

struct Entry
{
    u8 filler_00[4];
    u32 unk_04;
};

#define gUnk_03000890 ((struct Entry *)0x03000890)

u8 sub_080099A4(int i)
{
    u8 r = 0;

    if (gUnk_03000890[i].unk_04 == 0)
        r = 1;
    return r;
}
