typedef unsigned char u8;

struct Obj
{
    u8 filler_00[4];
    u8 unk_04;
    u8 filler_05[5];
    u8 unk_0A;
};

void sub_08024ABC(struct Obj *obj, u8 a)
{
    obj->unk_04 = a;
    if (a == 0 || a == 4)
        obj->unk_0A = 1;
}
