typedef unsigned int u32;

struct Obj
{
    u32 unk_00;
};

u32 sub_080DD4C4(struct Obj *obj)
{
    u32 r = 0;

    if (obj != 0)
        r = obj->unk_00;
    return r;
}
