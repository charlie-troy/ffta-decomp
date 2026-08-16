typedef unsigned char u8;
typedef short s16;

struct Obj
{
    u8 filler_00[2];
    s16 unk_02;
};

u8 sub_080E0690(struct Obj *obj)
{
    return obj->unk_02 == 0;
}
