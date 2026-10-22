#!/usr/bin/env python3
"""Write an Android boot image with header v3 (what a52sxq's ABL accepts).

The phone's stock boot partition parses as v3: header_size 1580,
kernel 45,021,696 bytes, ramdisk 892,339, cmdline at +44, page size 4096.
v3 carries no load addresses — ABL uses the fixed layout every Qualcomm
bootloader expects: kernel 0x8000, ramdisk 0x1000000, tags 0x100, and the DTB
stays in vendor_boot (untouched, sda21).

Usage: mkbootv3.py OUT.img --kernel Image [--ramdisk file] [--cmdline "..."]
"""
import argparse, os, struct

PAGE = 4096
HEADER_SIZE = 1580
MAGIC = b'ANDROID!'


def pad(b, page=PAGE):
    return b + b'\0' * (-len(b) % page)


def build(kernel, ramdisk=b'', cmdline='console=null', os_version=0x16000199):
    h = bytearray(HEADER_SIZE)
    h[0:8] = MAGIC
    struct.pack_into('<IIII', h, 8, len(kernel), len(ramdisk), os_version, HEADER_SIZE)
    struct.pack_into('<I', h, 24, 0)   # reserved[0..3] stay zero
    struct.pack_into('<I', h, 40, 3)   # header_version
    cb = cmdline.encode() if isinstance(cmdline, str) else cmdline
    assert len(cb) < 1536, 'cmdline too long for the v3 header'
    h[44:44 + len(cb)] = cb
    return pad(bytes(h)) + pad(kernel) + (pad(ramdisk) if ramdisk else b'')


def parse(blob):
    assert blob[:8] == MAGIC, 'not a boot image'
    ks, rs, osv, hs = struct.unpack_from('<IIII', blob, 8)
    ver = struct.unpack_from('<I', blob, 40)[0]
    cmdline = blob[44:HEADER_SIZE].split(b'\0')[0].decode(errors='replace')
    return {'kernel_size': ks, 'ramdisk_size': rs, 'os_version': hex(osv),
            'header_size': hs, 'header_version': ver, 'cmdline': cmdline}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--kernel', required=True)
    ap.add_argument('--ramdisk', default=None)
    ap.add_argument('--cmdline', default='console=null')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    kernel = open(a.kernel, 'rb').read()
    ramdisk = open(a.ramdisk, 'rb').read() if a.ramdisk else b''
    blob = build(kernel, ramdisk, a.cmdline)
    open(a.out, 'wb').write(blob)
    info = parse(blob)
    print(f'{a.out}: {len(blob)} bytes, header v{info["header_version"]}, '
          f'kernel {info["kernel_size"]}, ramdisk {info["ramdisk_size"]}', file=__import__('sys').stderr)
    if a.check:
        assert info['kernel_size'] == len(kernel)
        assert info['ramdisk_size'] == len(ramdisk)
        assert info['header_version'] == 3 and info['header_size'] == HEADER_SIZE
        assert blob[PAGE:PAGE + 8] == kernel[:8], 'kernel does not start at the first page'
        assert info['cmdline'] == a.cmdline
        print('self-check: OK', file=__import__('sys').stderr)


if __name__ == '__main__':
    main()
