typedef unsigned char u8;
typedef unsigned short u16;

struct Obj
{
    u8 unk_00;
    u8 filler_01[0xb];
    u16 unk_0C;
    u16 unk_0E;
    u16 unk_10;
};

void sub_08011014(struct Obj *obj, u16 a)
{
    obj->unk_0C = a;
    obj->unk_0E = 0;
    obj->unk_10 = 0;
    if (obj->unk_00 == 2)
        obj->unk_00 = 1;
}
