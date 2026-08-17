typedef unsigned char u8;
typedef unsigned short u16;

u8 sub_08013AAC(u8 a, u16 b)
{
    if ((b & 2) != 0)
        return a;
    return a + 2;
}
