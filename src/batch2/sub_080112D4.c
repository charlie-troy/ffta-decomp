typedef unsigned char u8;
typedef unsigned short u16;

struct Obj
{
    u8 filler_00[0x32];
    u16 unk_32;
    u16 unk_34;
    u16 unk_36;
};

void sub_080112D4(struct Obj *obj, u16 *a, u16 *b, u16 *c)
{
    *a = obj->unk_32;
    *b = obj->unk_34;
    *c = obj->unk_36;
}
