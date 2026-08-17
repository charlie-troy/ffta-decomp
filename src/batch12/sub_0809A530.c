typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u8 filler_00[0x44];
    u32 unk_44;
};

extern void sub_08021E28(u32 a);

void sub_0809A530(struct Obj *obj)
{
    sub_08021E28(obj->unk_44);
}
