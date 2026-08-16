typedef unsigned char u8;

struct Node
{
    u8 filler_00[8];
    struct Node *unk_08;
};

struct Obj
{
    u8 filler_00[4];
    struct Node *unk_04;
};

int sub_080C7B08(struct Obj *obj)
{
    struct Node *node = obj->unk_04;
    int count = 0;

    while (node != 0)
    {
        node = node->unk_08;
        count++;
    }
    return count;
}
