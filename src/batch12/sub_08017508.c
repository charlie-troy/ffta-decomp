typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0x1f];
    u8 unk_1F;
};

extern void sub_08016D64(struct Obj *obj);

void sub_08017508(struct Obj *obj, u8 a)
{
    obj->unk_1F = a;
    sub_08016D64(obj);
}
