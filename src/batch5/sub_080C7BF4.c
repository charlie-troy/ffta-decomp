typedef unsigned char u8;
typedef unsigned int u32;

struct Node
{
    u32 unk_00;
    u8 filler_04[4];
    struct Node *unk_08;
};

struct Obj
{
    u8 filler_00[4];
    struct Node *unk_04;
};

struct Node *sub_080C7BF4(struct Obj *obj, u32 key)
{
    struct Node *node = obj->unk_04;

    if (node != 0)
    {
        do
        {
            if (key == node->unk_00)
                return node;
            node = node->unk_08;
        } while (node != 0);
    }
    return 0;
}
