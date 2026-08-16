@ sub_080CD92C, verbatim from the base ROM at 0x080CD92C (24 bytes).
@ prelude.inc is MIPS-only and is deliberately not included.

	.text
	.code 16
	.align 2, 0
	.globl sub_080CD92C
	.type sub_080CD92C, %function
	.thumb_func
sub_080CD92C:
	push	{lr}
	add	r0, #0xe8
	mov	r1, #0x40
	ldrb	r0, [r0]
	and	r0, r1
	cmp	r0, #0
	beq	.L0
	mov	r0, #1
	b	.L1
.L0:
	mov	r0, #0
.L1:
	pop	{r1}
	bx	r1
	.size	sub_080CD92C, . - sub_080CD92C
