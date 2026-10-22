/*
 * a52sxq bring-up probe: paint the splash framebuffer red, then spin.
 * Nothing else — no MMU, no GIC, no console. If the panel turns red, ABL
 * accepted the image and our code ran; if the phone lands in Download mode
 * instead, the image layout (not the payload) is what ABL rejects.
 *
 * Position independent: only movz/movk, no literal pool, no absolute relocs.
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
	movz	w1, #0x001f		/* ABGR red-ish */
	movz	w2, #0x0080, lsl #16	/* 8 MiB of pixels */
1:	str	w1, [x0], #4
	subs	w2, w2, #1
	b.ne	1b
2:	wfi
	b	2b

	. = 0x1000
_end:
