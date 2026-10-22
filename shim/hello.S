/*
 * a52sxq bring-up probe v2.
 *
 * Paints the splash framebuffer, then waits ~20 s on the arch timer and powers
 * the phone off through PSCI. A probe has no USB and no drivers, so without
 * this a hung probe leaves the panel painted and the buttons unresponsive.
 *
 * Position independent: only movz/movk, no literal pool.
 */
	.section .text, "ax"
	.globl _head
_head:
	b	_start			/* code0 */
	.long	0			/* code1 */
	.quad	0			/* text_offset */
	.quad	_end			/* image_size */
	.quad	0xa			/* flags: LE, 4K pages */
	.quad	0			/* res2 */
	.quad	0			/* res3 */
	.quad	0			/* res4 */
	.ascii	"ARM\x64"
	.long	0			/* res5 */

_start:
	/* x0 = 0xe1000000 (splash_memory from the live FDT) */
	movz	x0, #0xe100, lsl #16
	movz	w1, #0x001f		/* ABGR: lands as deep blue on this panel */
	movz	w2, #0x0080, lsl #16	/* 8 MiB of pixels */
1:	str	w1, [x0], #4
	subs	w2, w2, #1
	b.ne	1b

	/* --- 20 s timeout on CNTPCT ----------------------------------------- */
	mrs	x3, cntfrq_el0
	movz	x4, #20
	mul	x3, x3, x4
	mrs	x5, cntpct_el0
	add	x3, x3, x5
2:	mrs	x6, cntpct_el0
	cmp	x6, x3
	b.hs	3f
	wfi
	b	2b

	/* --- PSCI SYSTEM_OFF, else SYSTEM_RESET, else park ------------------- */
3:	movz	w0, #0x8400, lsl #16
	movk	w0, #0x0008		/* 0x84000008 PSCI_SYSTEM_OFF */
	smc	#0
	hvc	#0
	movz	w0, #0x8400, lsl #16
	movk	w0, #0x0009		/* 0x84000009 PSCI_SYSTEM_RESET */
	smc	#0
	hvc	#0
4:	wfi
	b	4b

	. = 0x1000
_end:
