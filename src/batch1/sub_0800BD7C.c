typedef unsigned char u8;

struct Obj
{
    u8 filler_00[1];
    u8 unk_01;
};

void sub_0800BD7C(struct Obj *obj)
{
    if (obj->unk_01 == 0)
        obj->unk_01 = 2;
}
