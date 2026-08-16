typedef unsigned char u8;
typedef unsigned int u32;

struct Obj
{
    u32 unk_00;
};

/* Walks backwards from obj+0x90 in steps of 12, clearing byte 8 of each.
 * The loop bound is a signed compare (bge), so the operands must be ints:
 * comparing the pointers directly gives an unsigned bhs instead. */
void sub_080BA7FC(struct Obj *obj)
{
    u8 z;
    u8 *p;

    obj->unk_00 = 0;
    z = 0;
    p = (u8 *)obj + 0x90;
    do
    {
        p[8] = z;
        p -= 12;
    } while ((int)p >= (int)obj);
}
