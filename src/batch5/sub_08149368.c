typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0x980];
    u8 unk_980;
};

u8 sub_08149368(struct Obj *obj)
{
    if ((obj->unk_980 & 0x7f) == 4)
        return 1;
    return 0;
}
