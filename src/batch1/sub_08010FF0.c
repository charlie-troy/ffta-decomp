typedef unsigned char u8;

struct Obj
{
    u8 unk_00;
};

/* Note: unlike the masked-flag getters, an equality test wants the POSITIVE
 * form here. Negating it mirrors the branch layout. */
u8 sub_08010FF0(struct Obj *obj)
{
    if (obj->unk_00 == 2)
        return 1;
    return 0;
}
