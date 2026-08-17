/* Returns through r1 (`pop {r1}; bx r1`), which keeps r0 live across the
 * epilogue: the callee's return value is passed back. */
extern int sub_0812E55C(void);

int sub_0812F0D8(void)
{
    return sub_0812E55C();
}
