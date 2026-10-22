# NEXT — a52sxq / XNU bring-up

Read `PORT-NOTES.md` for the full log; this file is the "what to do now".

## Where we are (2026-10-22)

The shim runs on the real phone and prints its state to the panel. With
`SHIM_DEFS=-DSHIM_NOJUMP` it stops before jumping into XNU and powers off after
60 s. Last captured screen:

    SHIM    sweet milestone 4: xnu loader
    INITRD  lo=AE7C2000 hi=AFFFEB10
    PHYS    base=F0C00000 size=8F400000
    VIRT    FFFFFE0006000000
    ENTRY   FFFFFE000748B488
    SEGS    n=0000000A end=F30CB000
    BOOTARG pa=F30CC000 top=F30D0000
    JUMP    00000000F208B488

## Next step

Drop `SHIM_NOJUMP`, rebuild, repack in TWRP, boot, and photograph the panel.
The XNU kernel is expected to die early (no drivers for yupik); the goal is its
first output — that output decides which driver comes first.

## Build and flash (all verified today)

    # in /root/ios-a52s/a52sxq
    SHIM_DEFS= SKIP_IMAGE=1 bash shim/build.sh
    cat shim/out/Image out/payload.bin > /root/k.bin
    python3 - <<'EOF'
    import struct
    b=bytearray(open('/root/k.bin','rb').read()); struct.pack_into('<Q',b,16,len(b))
    open('/root/k.bin','wb').write(bytes(b)); print('image_size set')
    EOF

On the phone (TWRP shell, no `su`, `/sdcard` is noexec so use `/tmp`):

    adb push k.bin /sdcard/k.bin
    adb shell "cd /tmp && cp /sdcard/magiskboot mb && chmod 755 mb && \
      dd if=/dev/block/by-name/recovery of=w.img && ./mb unpack w.img && \
      cp /sdcard/k.bin kernel && ./mb repack w.img shim.img && \
      dd if=shim.img of=/dev/block/by-name/recovery && sync && reboot recovery"

Escape hatch if the panel freezes: hold all three buttons ~20 s → Download mode
→ Odin → `recovery-restore.tar` (TWRP). Backups of boot/recovery/vendor_boot sit
on the user's PC and the hashes are in `PORT-NOTES.md`.

## Rules that keep costing time

- `shim/console.h` must keep `FB_BASE 0xe1000000` (a52sxq splash), not sweet's.
- After appending the payload to the kernel Image, rewrite `image_size` at
  offset 16 — ABL otherwise copies only the old size.
- Never ship a probe that cannot be interrupted: leave the 20 s PSCI power-off
  path in place.
- Everything device-specific comes from `data/a52sxq.dtb` + the TWRP image;
  `tools/selftest.sh` re-checks the constants against the dump.
