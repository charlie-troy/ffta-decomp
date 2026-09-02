/* sub_080DBD5C (file offset 0x0dbd5c, 20 bytes, 21 callers), byte-matched.
 *
 * Original:
 *     push {r4, lr}
 *     ldrh r4, [r0, #8]
 *     strh r4, [r1]
 *     ldrh r1, [r0, #0xa]
 *     strh r1, [r2]
 *     ldrh r0, [r0, #0xc]
 *     strh r0, [r3]
 *     pop  {r4}
 *     pop  {r0}
 *     bx   r0
 *
 * Reads three consecutive u16 fields out of a struct into three out-params.
 */

typedef unsigned char u8;
typedef unsigned short u16;

struct Entity
{
    u8 filler_00[8];
    u16 x;
    u16 y;
    u16 z;
};

void sub_080DBD5C(struct Entity *entity, u16 *x, u16 *y, u16 *z)
{
    *x = entity->x;
    *y = entity->y;
    *z = entity->z;
}
