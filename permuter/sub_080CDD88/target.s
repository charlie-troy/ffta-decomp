@ sub_080CDD88, verbatim from the base ROM at 0x080CDD88 (34 bytes).

	.text
	.code 16
	.align 2, 0
	.globl sub_080CDD88
	.type sub_080CDD88, %function
	.thumb_func
sub_080CDD88:
	push	{lr}
	lsl	r1, r1, #24
	add	r2, r0, #0
	add	r2, #0xe8
	mov	r3, #0x11
	neg	r3, r3
	ldrb	r0, [r2]
	and	r3, r0
	strb	r3, [r2]
	cmp	r1, #0
	beq	.L0
	add	r0, r3, #0
	mov	r1, #0x10
	orr	r0, r1
	strb	r0, [r2]
.L0:
	pop	{r0}
	bx	r0
	.size	sub_080CDD88, . - sub_080CDD88
