typedef unsigned char u8;

struct Obj
{
    u8 filler_00[1];
    u8 unk_01;
};

u8 sub_0800C148(struct Obj *obj)
{
    return obj->unk_01 == 1;
}
