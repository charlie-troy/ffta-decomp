@ sub_080C8240, verbatim from the base ROM at 0x080C8240 (30 bytes).

	.text
	.code 16
	.align 2, 0
	.globl sub_080C8240
	.type sub_080C8240, %function
	.thumb_func
sub_080C8240:
	push	{lr}
	mov	r1, #0
	cmp	r0, #0
	beq	.L0
	ldrh	r1, [r0, #0x28]
	mov	r0, #0x80
	lsl	r0, r0, #8
	and	r0, r1
	lsl	r0, r0, #16
	lsr	r0, r0, #16
	neg	r0, r0
	lsr	r1, r0, #31
.L0:
	add	r0, r1, #0
	pop	{r1}
	bx	r1
	.size	sub_080C8240, . - sub_080C8240
