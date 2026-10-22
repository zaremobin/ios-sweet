#!/usr/bin/env python3
"""Build the minimal Apple Device Tree for the Samsung Galaxy A52s 5G (a52sxq).

Derived from ios-sweet/ios-topaz tools/mkadt.py. Every MMIO address below comes
from the vendor yupik DTS (arch/arm64/boot/dts/vendor/qcom/yupik.dtsi and
samsung/a52/a52sxq/a52sxq_eur_open_w00_r01.dts) — not from guesswork. DRAM
banks are the exception: the bootloader patches the empty yupik memory node, so
the live FDT dump supplies them (LOWBASE/LOWSIZE/HIGHBASE/HIGHSIZE override).

Usage: mkadt.py OUT.adt [--dump] [--qemu] [--native] [--mem=low|high]
"""
import hashlib, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402

# --- DRAM: from the live FDT dump (a52sxq.dtb, 2026-10-21) -------------------
# The bootloader reported four banks totalling 8 GB:
#   0x80000000+0x39700000, 0xb9d00000+0x1e00000, 0xc0000000+0xc0000000,
#   0x180000000+0x100000000
# Every fixed carve-out sits below 0xf0c00000 (highest: ramoops@F0B00000), so
# 'low' is the clean 2.29 GB below 4 GiB and 'high' is the untouched 4 GB bank.
LOW_PHYS_BASE = int(os.environ.get('LOWBASE', '0xf0c00000'), 16)
LOW_MEM_SIZE = int(os.environ.get('LOWSIZE', '0x8f400000'), 16)
HIGH_PHYS_BASE = int(os.environ.get('HIGHBASE', '0x180000000'), 16)
HIGH_MEM_SIZE = int(os.environ.get('HIGHSIZE', '0x100000000'), 16)

# /arm-io children are relative to this; it must not be 0 (serial_init bails)
SOC_BASE = 0x01000000

# intc: interrupt-controller@17a00000, redistributor-stride 0x20000, 8 cores
GICD, GICD_SIZE = 0x17a00000, 0x10000
GICR, GICR_SIZE = 0x17a60000, 0x100000
# splash_memory (label "cont_splash_region") left lit by ABL, panel 1080x2400:
# reg = <0xe1000000 0x2300000> in the live FDT. ABL's cmdline selects the
# S6E3FC3 (AMS646YD01) FHD panel on this unit, not the NT36672E.
FB, FB_SIZE = 0xe1000000, 0x2300000
FB_W, FB_H, FB_STRIDE = 1080, 2400, 1080 * 4
# ufshc@1d84000 "ufs_mem": 2 lanes, 19.2 MHz ref clock, IRQ SPI 265
UFS, UFS_SIZE = 0x01d84000, 0x3000
TIMEBASE = 19200000
# arm,armv8-timer PPI 11 (virtual) -> INTID 16+11 = 27, from the live FDT
VTIMER_INTID = 27
A52S_ECID = 0x4135325300000001  # 'A52S' + 1, synthetic

# QEMU virt (-M virt,gic-version=3): brings the pipeline up without a phone
QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE = 0x08000000, 0x080a0000, 62500000
QEMU_VTIMER_INTID = 27

BOOT_MANIFEST_HASH = hashlib.sha384(b'a52sxq boot manifest').digest()

# Apple artifact, kept out of git: extract from the iPhone X IPSW with
#   tools/remotezip.py URL DeviceTree.d22ap.im4p DIR
#   ipsw img4 im4p extract DIR/Firmware/all_flash/DeviceTree.d22ap.im4p -o d22ap.adt
D22AP_ADT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../research/ipsw-x/d22ap.adt')

u32 = lambda *v: struct.pack('<%dI' % len(v), *v)
u64 = lambda *v: struct.pack('<%dQ' % len(v), *v)
cstr = lambda s: s.encode() + b'\0'


def d22ap_product(path=D22AP_ADT):
    """/product properties of the real D22AP tree, without the syscfg
    placeholders iBoot would fill in (flag bit set) and the node bookkeeping."""
    if not os.path.exists(path):
        print(f'warning: {path} missing, no /product node', file=sys.stderr)
        return None
    root, _ = adt.parse(open(path, 'rb').read())
    for c in root.children:
        if dict((k, v) for k, f, v in c.props).get('name') == b'product\0':
            return [(k, v) for k, f, v in c.props if not f and k not in ('name', 'AAPL,phandle')]
    raise SystemExit(f'{path}: no /product node')


def node(name, props=(), children=()):
    n = adt.Node()
    n.props = [('name', 0, cstr(name))] + [(k, 0, v) for k, v in props]
    n.children = list(children)
    return n


def build(seed=None, qemu=False, native=False, mem='low'):
    phys_base, mem_size = {'low': (LOW_PHYS_BASE, LOW_MEM_SIZE),
                           'high': (HIGH_PHYS_BASE, HIGH_MEM_SIZE)}[mem]
    gicd, gicr, timebase = (QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE) if qemu else (GICD, GICR, TIMEBASE)
    seed = seed if seed is not None else os.urandom(64)
    phandle = iter(range(1, 1000))
    ph = lambda: ('AAPL,phandle', u32(next(phandle)))

    chosen = node('chosen', [
        ph(),
        ('dram-base', u64(phys_base)),
        ('dram-size', u64(mem_size)),
        ('random-seed', seed),
        ('debug-enabled', u32(1)),
        ('firmware-version', cstr('a52sxq-shim')),
        ('system-firmware-version', cstr('a52sxq-shim')),
        # iBoot's SHA-384 of the boot manifest; /sbin/mount -P 1 exits without it.
        ('boot-manifest-hash', BOOT_MANIFEST_HASH),
        # libimg4 (cryptexd) aborts "failed to get crypto algorithm" without it.
        ('crypto-hash-method', cstr('sha2-384')),
        # 1080x2400 @3x = 360x800 points (iPhone X class).
        ('display-scale', u32(3)),
        # IOPlatformUUID source; chip-id of the A11 the userland expects.
        ('unique-chip-id', struct.pack('<Q', A52S_ECID)),
        ('chip-id', u32(0x8015)),
        # Dev-fused, undemoted security status (tuple 0,0,1,1) → mobileactivationd
        # takes the native "Hactivation" branch: no SEP, no baseband here.
        ('certificate-production-status', u32(0)),
        ('effective-production-status-ap', u32(0)),
        ('certificate-security-mode', u32(1)),
        ('effective-security-mode-sep', u32(1)),
    ], [node('memory-map', [ph()]),
        # Same relaxed SIP as `csrutil disable`; lp-sip1: unauthenticated root.
        node('asmb', [ph(), ('lp-sip0', u64(0x6f)), ('lp-sip1', u32(1))])])

    # SMP: gold cluster only — MPIDR 0x400-0x403 (yupik.dtsi CPU4-CPU7, the
    # 4x Cortex-A78, capacity 1946/1985). The A55 cluster sits at 0x000-0x300;
    # A55 also has a 16K granule, so silver can be added later if it helps.
    cpu_nodes = []
    for core in range(1 if qemu else 4):
        cpu_nodes.append(node(f'cpu{core}', [
            ph(),
            ('device_type', cstr('cpu')),
            ('compatible', cstr('qcom,kryo670') + cstr('ARM,v8')),
            ('reg', u32(core if qemu else 0x400 | core)),  # real MPIDR Aff1:Aff0
            ('cpu-id', u32(core)),   # descriptive: XNU assigns IDs by DT order
            ('cluster-id', u32(0)),
            ('cluster-type', u32(0)),  # homogeneous CLUSTER_TYPE_SMP, not AMP
            ('die-cluster-id', u32(0)),
            ('cluster-core-id', u32(core)),
            ('l2-cache-id', u32(core)),  # per-core L2 in the live FDT
            ('l3-cache-id', u32(0)),
            ('state', cstr('running' if core == 0 else 'stopped')),
            ('timebase-frequency', u32(timebase)),
            ('clock-frequency', u32(2400000000)),
            ('bus-frequency', u32(100000000)),
            ('memory-frequency', u32(2133000000)),  # LPDDR4X-4266
            ('peripheral-frequency', u32(timebase)),
            ('fixed-frequency', u32(timebase)),
        ]))
    cpus = node('cpus', [ph(), ('#address-cells', u32(1)),
                         ('#size-cells', u32(0))], cpu_nodes)

    gic = node('gic', [
        ph(),
        ('compatible', cstr('arm,gic-v3')),
        ('interrupt-controller', b''),
        ('virtual-timer-intid', u32(QEMU_VTIMER_INTID if qemu else VTIMER_INTID)),
        ('reg', u64(gicd - SOC_BASE, GICD_SIZE, gicr - SOC_BASE, GICR_SIZE)),
    ])
    arm_io = node('arm-io', [
        ph(),
        ('device_type', cstr('sweet-io')),
        ('compatible', cstr('sweet-io') + cstr('arm-io')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
        ('ranges', u64(0, SOC_BASE, 0x100000000 - SOC_BASE)),
    ], [gic,
        # watchdogd crashes setting the PMU boot stage unless no-pmu is present.
        node('wdt', [ph(), ('no-pmu', u32(1))]),
        # launchd starts wifid only when a "wlan" node exists.
        node('wlan', [ph(), ('device_type', cstr('wlan')),
                      ('compatible', cstr('a52sxq,wcn6750'))]),
        # IOMobileFramebuffer counts /arm-io children with this device_type.
        node('disp0', [
            ph(),
            ('device_type', cstr('display-subsystem')),
            ('compatible', cstr('sweet,display')),
            # --native: present the real 1080x2400 panel (direct MDP scanout must
            # match the canvas; a 1125x2436 canvas needs a scaler we do not have)
            ('canvas-width', u32(1080 if native else 1125)),
            ('canvas-height', u32(2400 if native else 2436)),
        ])])

    fbcon = node('sweet-fbcon', [
        ph(),
        ('reg', u64(FB, FB_SIZE)),
        ('width', u32(FB_W)),
        ('height', u32(FB_H)),
        ('stride', u32(FB_STRIDE)),
    ])

    # bsd/dev/sweet_ufs.c: the UFS host ABL leaves running (absolute physical reg).
    ufs = node('sweet-ufs', [
        ph(),
        ('compatible', cstr('qcom,ufshc')),
        ('reg', u64(UFS, UFS_SIZE)),
    ])

    # pmap_compute_max_asids needs the node; no effaceable storage → keybagd
    # reads systembag.kb as a plain plist instead of decrypting it.
    defaults = node('defaults', [ph(), ('no-effaceable-storage', u32(1))])

    # MobileGestalt HomeButtonType (D22AP: 2 = no Home button).
    buttons = node('buttons', [
        ph(),
        ('button-names', cstr('volup') + cstr('voldown') + cstr('hold')),
        ('home-button-type', u32(2)),
        ('opposed-power-vol-buttons', u32(1)),
    ])

    product_props = d22ap_product()
    product = [node('product', [ph()] + product_props)] if product_props else []

    # compatible[0] is hw.model/hw.target (D22AP), model is hw.machine
    # (iPhone10,3); 'samsung,a52sxq'/'qcom,yupik' stay for platform matching.
    return node('device-tree', [
        ph(),
        ('compatible', cstr('D22AP') + cstr('iPhone10,3') + cstr('samsung,a52sxq') +
         cstr('qcom,yupik') + cstr('AppleARM')),
        ('model', cstr('iPhone10,3')),
        ('target-type', cstr('D22')),
        ('target-sub-type', cstr('D22AP')),
        ('manufacturer', cstr('Apple Inc.')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
    ], [chosen, defaults, cpus, arm_io, fbcon, buttons] + product + ([] if qemu else [ufs]))


if __name__ == '__main__':
    mem = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--mem=')), 'low')
    root = build(qemu='--qemu' in sys.argv, native='--native' in sys.argv, mem=mem)
    blob = adt.serialize(root)
    open(sys.argv[1], 'wb').write(blob)
    if '--dump' in sys.argv:
        adt.dump(adt.parse(blob)[0])
    print(f'{sys.argv[1]}: {len(blob)} bytes', file=sys.stderr)
