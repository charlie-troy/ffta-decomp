typedef unsigned char u8;

struct Obj
{
    u8 filler_00[6];
    u8 unk_06;
};

/* The result variable is initialised after the load, not at its declaration:
 * the target emits ldrb, then movs r1 #0, then the subtract. */
u8 sub_080C8384(struct Obj *obj)
{
    u8 v;
    u8 r;

    if (obj == 0)
        return 0;
    v = obj->unk_06;
    r = 0;
    v -= 6;
    if (v <= 0xc)
        r = 1;
    return r;
}
