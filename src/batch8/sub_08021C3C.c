typedef unsigned char u8;

struct Obj
{
    u8 filler_00[0x1e];
    u8 unk_1E;
};

/* The field is read twice, once for the test and once for the masked return,
 * which is what the second ldrb in the target reflects. */
int sub_08021C3C(struct Obj *obj)
{
    struct Obj *p = obj;

    if ((p->unk_1E & 0x80) != 0)
        return p->unk_1E & ~0x80;
    return -1;
}
