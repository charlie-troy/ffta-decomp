typedef unsigned char u8;

struct Obj
{
    u8 unk_00;
    u8 unk_01;
    u8 unk_02;
};

/* A store in each arm rather than a shared temp, which keeps both arms and the
 * unconditional branch the target has. */
u8 sub_08018C94(struct Obj *obj, u8 a)
{
    obj->unk_00 = 0x40;
    obj->unk_01 = 0x6c;
    if (a == 3)
        obj->unk_02 = a;
    else
        obj->unk_02 = 0;
    return 3;
}
