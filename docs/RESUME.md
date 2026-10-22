# RESUME — pick this up in 5 minutes

Everything needed to continue the a52sxq (Galaxy A52s 5G) XNU port after a pause.

## What is already true

- Bootloader unlocked, Magisk root, TWRP in the recovery slot. Android untouched.
- A shim image boots on the phone from RECOVERY and prints its state on the panel.
- All device constants come from the phone's own FDT dump: GICD `0x17a00000`,
  GICR `0x17a60000`, UFS `0x1d84000`, timer 19.2 MHz with VTIMER INTID 27,
  splash framebuffer `0xe1000000` (1080x2400, BGRA), panel S6E3FC3,
  DRAM `0xf0c00000 + 0x8f400000` below 4 GiB and `0x180000000 + 0x100000000`.
- Last captured screen (SHIM_NOJUMP build):

      SHIM    sweet milestone 4: xnu loader
      INITRD  lo=AE7C2000 hi=AFFFEB10
      PHYS    base=F0C00000 size=8F400000
      SEGS    n=0000000A end=F30CB000
      BOOTARG pa=F30CC000 top=F30D0000
      JUMP    00000000F208B488

## Rebuild + flash, exactly

    cd /root/ios-a52s/a52sxq
    SHIM_DEFS=-DSHIM_NOJUMP SKIP_IMAGE=1 bash shim/build.sh   # debug build: stops before XNU
    cat shim/out/Image out/payload.bin > /root/k.bin
    python3 -c "import struct;b=bytearray(open('/root/k.bin','rb').read());struct.pack_into('<Q',b,16,len(b));open('/root/k.bin','wb').write(bytes(b))"

On the phone in TWRP (shell is root, `/sdcard` is noexec, so work in `/tmp`):

    adb push k.bin /sdcard/k.bin
    adb shell "cd /tmp && cp /sdcard/magiskboot mb && chmod 755 mb && \
      dd if=/dev/block/by-name/recovery of=w.img && ./mb unpack w.img && \
      cp /sdcard/k.bin kernel && ./mb repack w.img shim.img && \
      dd if=shim.img of=/dev/block/by-name/recovery && sync && reboot recovery"

Drop `SHIM_DEFS=-DSHIM_NOJUMP` to let it jump into XNU (that is M1).

## Escape hatch, if the panel freezes

Hold **Power + Vol Up + Vol Down** ~20 s → Download mode → Odin → AP →
`recovery-restore.tar` (built earlier from `recovery-backup.img`). Partition
dumps live on the user's PC; SHA256s are in `PORT-NOTES.md`. Every probe built
after 2026-10-22 also powers the phone off by itself after 20-60 s.

## The one rule that cost the most time

Repack the image that already boots with `magiskboot`. Hand-built boot images
lose the DTB/DTBO/SEANDROID/vbmeta sections and ABL answers with Download mode.
Full detail and every other landmine: `PORT-NOTES.md`, `NEXT.md`, and the
`ios-on-android-port` skill.
