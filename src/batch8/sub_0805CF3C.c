typedef unsigned char u8;
typedef unsigned short u16;

void sub_0805CF3C(u8 a, u8 b, u16 *px, u16 *py)
{
    *px = (a + b) * 16 - 0x26;
    *py = (a - b) * 8 + 0x4b;
}
