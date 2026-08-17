/* Thunk. The `pop {r0}; bx r0` return clobbers r0, so nothing is passed back:
 * a void wrapper. Contrast sub_0812F0D8, which returns through r1 to keep r0
 * live. */
extern void sub_08005B58(void);

void sub_080DBA50(void)
{
    sub_08005B58();
}
