# iOS on a52sxq (Samsung Galaxy A52s 5G) — port of ios-sweet

Working notes for porting Apple XNU + iOS 16 userland (ios-sweet approach) to
the Samsung Galaxy A52s 5G (`a52sxq`, Qualcomm SM7325 / Snapdragon 778G).

## What exists already (2026-10-20)

- `/root/ios-a52s/ios-sweet` — base repo, SM7150 (Redmi Note 10 Pro). 84 patches,
  boots to home screen on that phone.
- `/root/ios-a52s/ios-topaz` — second port, SM6225 (Redmi Note 12 4G). 47
  additional patches (0081–0128), reaches lock screen. **Its device-specific
  diff is the porting template.**

## Device-specific surface (what must change for a52sxq)

1. **shim/** — every file differs between the two ports (build.sh, loader.c,
   mmu.c, shim.c, ufs.c). Device tree addresses, memory map, boot-image header
   version, UFS controller base.
2. **tools/mkadt.py** — Apple Device Tree: CPU nodes, MMIO map, framebuffer
   address, touch controller, iPhone10,3 identity.
3. **patches 0081+** — device bring-up (touch, panel, buttons).
4. Generic patches 0001–0080 (clang, pmap, HFS+, AMFI, mockfs...) should carry
   over mostly unchanged.

## a52sxq hardware facts (extracted from Samsung OneUI kernel DTS, 2026-10-20)

Source: `kernel-a52sxq/arch/arm64/boot/dts/vendor/qcom/yupik.dtsi` + overlays in
`arch/arm64/boot/dts/samsung/a52/a52sxq/`. SoC internal codename: **yupik**.

- UFS host controller: `0x01d84000` size 0x3000 (+ ICE 0x1d88000, HWKM 0x1d90000),
  2 lanes, IRQ SPI 265, ref clock 19.2 MHz
- GICv3 (`intc`): `0x17a00000`; PDC: `0x0b220000`
- Panel (EUR variant): Novatek NT36672E FHD+ (1080x2400) video-mode 60/90/120/144Hz
  (DSI NT panel driver @ I2C 0x62); secondary panel S6E3FC3 (AMS646YD01) cmd-mode
- Touch: Samsung SEC TSP @ I2C addr 0x49 (sec-ts driver, `touchscreen@49`),
  powered by pm8350c_l7 (tsp_avdd_ldo)
- PMIC: PM7325 + PM8350(+C) family; charger/fuelgauge SM5714 @ I2C 0x49-0x33
- CPU: 4x Cortex-A78 + 4x Cortex-A55 (A78 = 16K-page capable, unlike sweet's A76)
- qcom,msm-id = <0x1db 0x10000 ...> (= SM7325)
- EUR model file: `a52sxq_eur_open_w00_r01.dts` (overlays on yupik-idp base)

**User's actual device: SM-A528B/DS** (global dual-SIM) — confirmed from phone
settings screenshot 2026-10-20. Use the `eur_open` overlays. Serial R5CR9071XVV.

## Samsung-specific risk (IMPORTANT — differs from Xiaomi base)

- No `fastboot boot` RAM-boot on Samsung. Flash path = download mode (Vol Up+Vol
  Down + USB) + samloader-rs/heimdall/Odin. Custom recovery flash works the same
  way (LineageOS wiki a52sxq install = samloader flash --partition RECOVERY).
- This means: unlike ios-sweet/ios-topaz, our shim image must be FLASHED to a
  partition (e.g. over RECOVERY first) instead of RAM-booted. A bad image =
  bootloop recoverable only via download mode (Vol Up+Vol Down+USB from off).
- Download mode is always reachable unless the bootloader chain is damaged.
  NEVER touch BL partitions. vbmeta flashing (disable verification) known-good
  from LineageOS guide.

## Boot chain target

download mode -> flash shim-boot.img to RECOVERY (or BOOT) partition -> Samsung
SBL/ABL -> our shim -> XNU -> HFS+ root in userdata -> SpringBoard

## Milestones

- [x] M0: repo forked, CI kernel build green on GitHub Actions (macOS runner)
      run 39695861609, 7m01s, artifacts xnu-kernel 57 MB + xnu-buildtree 22 MB (2026-10-21)
- [ ] M1: shim boots XNU on a52sxq — Apple logo on screen (biggest risk: Samsung
      ABL handoff + framebuffer address)
- [ ] M2: touch + SpringBoard lock screen
- [ ] M3: userdata HFS+ root + full userland

## Rules

- No personal data on the phone while security is off.
- Flash only BOOT/RECOVERY/userdata experiments; BL/CP/modem/persist untouched.
- Keep every successful image; tag git commits with what booted how far.
- Tools: adb/fastboot useless for flashing Samsung — use samloader-rs or
  heimdall. User's PC has the phone connected.

## Porting checklist (from the ios-sweet → ios-topaz diff, 2026-10-21)

The whole device-specific surface is small and lives in three places; topaz
added 47 patches but only these files carry addresses:

| File | sweet → topaz change | What a52sxq needs |
|---|---|---|
| `shim/shim.c` | 155 changed lines: MMIO, memory map, boot handoff | same sites, yupik values |
| `shim/loader.c` | 49 lines: boot-image header, where the payload lands | a52sxq header version |
| `shim/build.sh` | 19 lines: device name, page size, target | rename + a52sxq |
| `shim/mmu.c`, `shim/ufs.c` | 4 and 2 lines: constants only | constants |
| `shim/fdt.c` | identical | none |
| `tools/mkadt.py` | 84 lines: GIC, FB, UFS, ECID, CPU nodes, clocks | **done** (below) |
| `.github/workflows/xnu.yml` | runner + matrix | a52sxq job |

Patches 0001–0080 (clang, pmap, HFS+, AMFI, mockfs) are device-independent and
carry over from sweet unchanged. Patches 0081+ are the device bring-up set.

## Done so far for a52sxq (2026-10-21)

- `/root/ios-a52s/a52sxq` — working tree copied from ios-sweet (not yet a fork).
- `tools/mkadt.py` rewritten with yupik/a52sxq values from the vendor DTS:
  GICD `0x17a00000` / GICR `0x17a60000` (stride `0x20000`, 8 cores), splash
  framebuffer `0xe1000000` size `0x2400000` (1080×2400, stride 4320), UFS
  `0x1d84000`, timebase 19.2 MHz, gold-cluster MPIDRs `0x400-0x403`, ECID
  `'A52S'+1`, identity `samsung,a52sxq`/`qcom,yupik`.
- `tools/fdtmem.py` — parses the live FDT: memory banks, GIC, UFS, timebase,
  bootargs. `tools/dump-fdt.sh` pulls `/sys/firmware/fdt` off the rooted phone.
- `tools/selftest.sh` — asserts the ADT builds with the right identity and
  that fdtmem reads memory/GIC/UFS from a compiled sample DTB. Currently green.

## Live FDT facts (a52sxq.dtb from the phone, 2026-10-22)

Dumped with `tools/dump-fdt.sh` over adb (root/Magisk), parsed with
`tools/fdtmem.py`. These replace every placeholder.

- **DRAM (bootloader-patched, 8 GB total, `androidboot.dram_info=01,07,01,8G`):**
  `0x80000000+0x39700000`, `0xb9d00000+0x1e00000`, `0xc0000000+0xc0000000`,
  `0x180000000+0x100000000`
- **Highest fixed carve-out below 4 GiB:** `ramoops@0xF0B00000` (end `0xf0c00000`)
  → kernel-managed low region `0xf0c00000+0x8f400000`, high region
  `0x180000000+0x100000000` (untouched 4 GB bank)
- **GIC:** GICD `0x17a00000`, GICR `0x17a60000`; **UFS** `0x1d84000` (+ICE
  `0x1d88000`, HWKM `0x1d90000`)
- **Timer:** `clock-frequency` 19,200,000; `arm,armv8-timer` PPIs 13/14/11/12 →
  virtual timer INTID **27** (sweet's 19 was wrong for this SoC)
- **Framebuffer:** `cont_splash_region` `0xe1000000+0x2300000`
- **Active panel:** ABL cmdline selects `ss_dsi_panel_S6E3FC3_AMS646YD01_LO_FHD`
  (the cmd-mode panel), not the NT36672E — matters for M2 presentation
- **Bootloader:** `A528BXXSBGYI3`, `verifiedbootstate=orange`, `warranty_bit=1`,
  serial `R5CR9071XVV`, `androidboot.dtbo_idx=2`, `dtb_idx=0`
- Samsung log regions: `sec_dbg 0x1FF000@0xF0000000`, `sec_log 0x200000@0xF0200000`
  (RAM-as-console candidates for a persistent log ring)

Untracked dump lives at `data/a52sxq.dtb` (git-ignored: it carries the serial).

## Shim status for a52sxq (2026-10-22)

sweet's shim was already 90% right for yupik — IMEM restart reason
`0x146aa65c`, GICD `0x17a00000` / GICR `0x17a60000`, and PSCI `CPU_ON` with
`mpidr = i << 8` all match this SoC. Only the timer PPIs were wrong.

- `VTIMER_INTID` 19 → **27**, `PTIMER_INTID` 18 → **30** (live FDT
  `arm,armv8-timer`: PPIs 11 and 14 → INTIDs 16+11, 16+14)
- No gold-cluster switch needed: the A55 cores (0x000-0x300) also have a 16K
  granule, unlike topaz's A53 silver cluster. The boot core ABL hands us runs
  the loader directly.
- yupik has no `qcom,pshold` node; `reset()` already calls `PSCI_SYSTEM_RESET`
  first, so PSHOLD stays as a harmless last resort.
- `shim/build.sh` gained `SKIP_IMAGE=1` (build the Image without the Android
  boot wrapper) and lost `--no-warn-rwx-segments` (binutils 2.38 rejects it).
- Verified locally: 7 objects compile, **0 ABS64 relocations**, `out/Image` =
  180,224 bytes, entry 0x0. `tools/selftest.sh` now covers it.

**Boot image wrapper — solved (2026-10-22).** The phone's `boot` header parses
as **v3** (header_size 1580, kernel 45,021,696 bytes, ramdisk 892,339, cmdline
at +44, `header_version=3`), page size 4096. v3 carries no load addresses: ABL
uses kernel 0x8000 / ramdisk 0x1000000 / tags 0x100, and the DTB stays in
`vendor_boot` (sda21), which we leave untouched. `tools/mkbootv3.py` writes that
wrapper and self-checks the round-trip.

Partition map (a52sxq): boot sda19, recovery sda20, vendor_boot sda21,
vbmeta sde19, vbmeta_system sda24.

Payload path: boot v3 has no addresses, so ABL concatenates boot's ramdisk with
vendor_boot's; `shim/loader.c` now scans the initrd for the `SWEETXNU` magic and
slides it to an 8-byte boundary (the same trick ios-topaz needed).

## Bring-up log — first flash attempts (2026-10-22)

Partitions: boot sda19, recovery sda20, vendor_boot sda21 (96/78/96 MiB; dumps
kept in `data/`, SHA256 of each recorded and re-checked on the PC).

| attempt | image | result |
|---|---|---|
| 1 | v3 header, shim + payload, dd → recovery | Download mode |
| 2 | v2 header matching TWRP exactly (kernel 0x8000, ramdisk 0x02000000, tags 0x01e00000, name SRPUE26A001) | Download mode |
| 3 | 4 KiB probe (`shim/hello.S`) that only paints 0xe1000000 red, same v2 header | Download mode |

Facts learned:
- The recovery partition holds TWRP and parses as **v2**; its tail is zeros, so
  `SEANDROIDENFORCE` is not required (red herring — dropped from the v2 path).
- TWRP boots fine, so ABL is not rejecting images merely for lacking a
  signature; even a 4 KiB position-independent kernel is rejected.
- Suspicion now: something in the header beyond the fields we copy, or the boot
  mode handshake (`androidboot.boot_recovery=1`, `sec_dbg`, `sec_log`,
  `androidboot.kg.*` are injected by ABL).
- Working restore: Odin → AP → tar holding `recovery.img` (`tar -cf
  recovery-restore.tar recovery.img`), PASS in ~5 s, TWRP boots again.

Next diagnostic: after a failed boot, `cat /proc/last_kmsg` from TWRP holds the
ABL log — grep it for the reject reason. Never captured (phone went back to
daily use), so that is step 1 when work resumes.

## Research round (2026-10-22): why ABL refuses our image

Sources that matter:

- **LineageOS `sm7325-common` BoardConfigCommon.mk** — the authoritative layout
  for this SoC: `BOARD_BOOT_HEADER_VERSION := 3`, kernel base 0x0, kernel offset
  0x8000, ramdisk offset **0x02000000**, tags 0x01e00000, **dtb offset
  0x01f00000**, page 4096, `BOARD_KERNEL_SEPARATED_DTBO := true`,
  `BOARD_AVB_MAKE_VBMETA_IMAGE_ARGS += --flags 3` (verity + verification
  disabled → unsigned boot/recovery images are expected to boot).
- **Ghostess/ghost_kernel_a52s_5g + bone-machine's A52s kernel** — they never
  build a boot image from scratch: `build_kernel_zip.sh` repacks a *base image*
  with **magiskboot**, which carries every Samsung-specific header byte
  (`extra_cmdline` is random-looking bytes, the 1620+ block, the SHA1 `id`)
  through untouched. Confidence boost for the template idea below.
- **TWRP header (measured, 64 KiB dump)** — id `bd40652ab1822957`, `text_offset
  0x80000`, `image_size 0x2b260`, and bytes 1620-1664 hold six more u32/u64-ish
  values (`0x000babf1, 0x0410b000, 0, 0x67c, 0x071e0f, 0x01f00000…`) that are
  not in the AOSP header. Which of these ABL actually reads is unknown.
- **kernel.org arm64 booting** — a Linux `Image` must sit `text_offset` bytes
  from a 2 MiB aligned base, so a header with `text_offset 0` and code at offset
  0 is legal; ABL, however, may jump to `kernel_addr + text_offset` regardless,
  which is exactly what TWRP's 0x80000 implies.
- **pmaports** has no `device-samsung-a52sxq` (checked all of device/main,
  device/community, device/testing), so no ready-made mainline boot recipe.
  Mainline does have SM7325 DTs (`sm7325-nothing-spacewar`, `-motorola-dubai`,
  `-xiaomi-taoyao`) — same SoC family, no yupik DT yet.

Hypotheses, in order of cheapness:

1. **`id` field**: TWRP's header has it non-zero; both images we flashed left it
   zero. An image with a correct SHA1 `id` was built (`hello-b.img`) but never
   flashed.
2. **Entry address**: ABL may jump to `kernel_addr + text_offset`. Splice test:
   write our 4 KiB probe into an untouched copy of the TWRP image at
   `4096 + 0x80000` and change nothing else (`probe.img` recipe). If the screen
   turns red, ABL honours `text_offset` and arbitrary kernel bytes are fine.
3. **Samsung header extras** (bytes 1620-1664). Fix: build from TWRP's page 0 as
   a template, patch only the size/address/cmdline fields, recompute `id`.
4. **Boot-failure fallback**: Samsung drops to Download mode when the kernel
   dies. If (2) shows red but the shim still fails, the shim itself is crashing,
   not ABL rejecting the image.

Cheapest next session, in this order: `hello-b.img` (id) → `probe.img` (splice)
→ template-based image. All three are already built or documented here.

## SOLVED: the boot path (2026-10-22)

`magiskboot unpack` on the TWRP image printed the missing pieces:

    RECOV_DTBO_SZ [764913]   DTB_SZ [466447]
    SAMSUNG_SEANDROID        VBMETA

A from-scratch image has none of these, which is why every hand-built variant
fell to Download mode. Repacking the real image with `magiskboot` (which keeps
the DTB, recovery DTBO, the `SEANDROIDENFORCE` marker and the embedded vbmeta)
**boots**: a 4 KiB probe kernel painted the panel deep blue on the first try.

Recipe that works (in TWRP, `/tmp`):

    cp /sdcard/magiskboot mb && chmod 755 mb
    dd if=/dev/block/by-name/recovery of=w.img
    ./mb unpack w.img                 # keeps kernel/ramdisk.cpio/dtb/... on disk
    cp <new-kernel> kernel
    ./mb repack w.img new.img
    dd if=new.img of=/dev/block/by-name/recovery

Gotchas learned the hard way:

- `/sdcard` is noexec and SELinux forbids `chmod`/`cd` under `/data` from a
  Magisk `su` shell — do this work inside TWRP, whose shell is unrestricted.
- A probe with no USB cannot be interrupted: the phone has to be reset by
  holding Vol Down + Power (>7 s) or run until the battery dies. `shim/hello.S`
  now waits 20 s on CNTPCT and issues PSCI `SYSTEM_OFF`, then `SYSTEM_RESET`, so
  a bad probe shuts the phone down instead of stranding it.
- The panel renders `0x0000001f` as **deep blue**, not red: this framebuffer is
  BGRA, not RGBA.

## First light: the shim runs and parses the payload (2026-10-22)

Recovery image = TWRP repacked by magiskboot with our kernel appended payload,
`SHIM_NOJUMP=1`. Screen text captured from the panel:

    SHIM    sweet milestone 4: xnu loader
    INITRD  lo=AE7C2000 hi=AFFFEB10
    PHYS    base=F0C00000 size=8F400000
    VIRT    FFFFFE0006000000
    ENTRY   FFFFFE000748B488
    SEGS    n=0000000A end=F30CB000
    BOOTARG pa=F30CC000 top=F30D0000
    JUMP    00000000F208B488
    XNU     jumping (fbcon clears screen)
    STOP    not jumping (SHIM_NOJUMP), power off

Landmines cleared on the way:

- `shim/console.h` still had sweet's `FB_BASE 0x9c000000`; a52sxq's splash is at
  **0xe1000000**. With the wrong base the shim looked hung — it was drawing into
  nothing. The early-paint probe in `start.S` (16 KiB at 0xe1000000) is what
  proved execution reached our entry point.
- The kernel Image header's `image_size` (offset 16) must be updated after the
  payload is appended, otherwise ABL copies only the original size.
- Wrong FB base also meant the first "black screen + one blue line" reading: the
  blue line was the early paint, the black was everything else.
- `SHIM_NOJUMP` (`SHIM_DEFS=-DSHIM_NOJUMP` in `shim/build.sh`) is the debug switch
  that stops before the kernel jump, holds the screen for 60 s and powers off.

Next: drop `SHIM_NOJUMP` and let it jump; the panel should then show XNU's own
early output (fbcon), which is the next thing to capture.

## Upstream status check (2026-10-22)

`dipa-studio/ios-sweet` is **3 commits ahead** of our fork only, and as of
2026-10-18 it boots **iOS 16.7.16 (iPhone X userland) to the home screen** on the
Redmi Note 10 Pro. So the tree we forked already contains the mature parts we
would otherwise have to write: own UFS host driver, HFS+ root inside `userdata`,
`IOMobileFramebuffer`/`AppleCLCD` + software CoreAnimation, Goodix touch over
GENI-I²C, PMIC buttons via SPMI, `IOPMPowerSource`, and the activation path.

What upstream still does not have (so it is out of scope here too): Wi-Fi,
Bluetooth, cellular, audio, camera, sensors, GPS, SEP/Face ID, GPU
acceleration (~20-30 fps CPU rendering), App Store/Apple ID, and any real
security (permissive AMFI, stub AppleKeyStore). Boot takes ~4 minutes. Installing
the iOS root **wipes Android userdata**.

Consequence for a52sxq: the milestone ladder is
M1 XNU prints → M2 framebuffer text → M3 UFS + HFS+ root → M4 touch +
SpringBoard. All the code for M2-M4 exists; what is missing is our device's
constants and driver bring-up (UFS `0x1d84000` on yupik, GIC `0x17a00000`, timer
19.2 MHz, panel S6E3FC3).

## Open items

1. ~~DRAM banks~~ **done** — live banks in `mkadt.py`; `selftest.sh` re-checks
   them against the dump whenever `data/a52sxq.dtb` is present.
2. ~~VTIMER_INTID~~ **done** — 27, from the live FDT.
3. ~~Fork + CI~~ **done** — `zaremobin/ios-sweet` branch `a52sxq`, CI green.
4. Boot-image wrapper: pull the phone's `boot` partition and unpack it
   (`tools/unpack_bootv2.py`) to fix header version, offsets and the DTB.

