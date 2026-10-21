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

## Open items

1. **DRAM banks are placeholders.** The yupik memory node is empty in the
   vendor DTS (bootloader patches it). Run `tools/dump-fdt.sh` on the PC with
   the phone attached, then set `LOWBASE/LOWSIZE/MIDBASE/MIDSIZE`.
2. `VTIMER_INTID` (19) is inherited from sweet — confirm against the live
   timer node before trusting it.
3. Fork + CI: needs the user's GitHub account (`gh` is not installed here).
4. Boot-image header version for a52sxq (likely v2, `unpack_bootv2.py`
   already in tools/) — check against the phone's stock boot image.

