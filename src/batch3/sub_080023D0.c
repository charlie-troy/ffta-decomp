typedef unsigned char u8;
typedef unsigned short u16;

struct Obj
{
    u8 filler_00[4];
    u16 unk_04;
    u8 filler_06[1];
    u8 unk_07;
    u8 filler_08[3];
    u8 unk_0B;
    u8 filler_0C[2];
    u8 unk_0E;
};

void sub_080023D0(struct Obj *obj)
{
    if (obj->unk_07 & 0x80)
        obj->unk_0E = obj->unk_0B;
    obj->unk_04 = 0;
}
