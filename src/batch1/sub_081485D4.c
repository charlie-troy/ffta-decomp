typedef unsigned char u8;
typedef unsigned short u16;

struct Obj
{
    u16 unk_00;
};

u8 sub_081485D4(struct Obj *obj)
{
    return obj->unk_00 == 0;
}
