typedef unsigned char u8;
typedef short s16;

void sub_08092084(u8 *p, s16 i, u8 a, u8 b)
{
    u8 *q = &p[i * 2];

    *q = a;
    p++;
    q = &p[i * 2];
    *q = b;
}
