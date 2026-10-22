#!/usr/bin/env python3
"""Build a boot image on top of an existing Samsung header page.

ABL happily boots TWRP, whose page 0 carries fields the AOSP header does not
(bytes 1620-1664, a non-zero SHA1 `id`, random-looking `extra_cmdline`). Rather
than guess which of them ABL reads, keep page 0 byte-for-byte and patch only
kernel_size / ramdisk_size / cmdline / id.

Usage: mktemplate.py TEMPLATE_HEAD.bin OUT.img --kernel Image [--ramdisk f]
       (TEMPLATE_HEAD.bin = first 4096 bytes of a known-good image)
"""
import argparse, hashlib, struct, sys

PAGE = 4096
MAGIC = b'ANDROID!'


def pad(b):
    return b + b'\0' * (-len(b) % PAGE)


def build(header, kernel, ramdisk=b'', cmdline=None):
    assert header[:8] == MAGIC and len(header) == PAGE, 'need the first 4096 bytes of a boot image'
    ver = struct.unpack_from('<I', header, 40)[0]
    assert ver == 2, f'only header v2 templates are patched (got v{ver})'
    h = bytearray(header)
    struct.pack_into('<I', h, 8, len(kernel))
    struct.pack_into('<I', h, 16, len(ramdisk))
    if cmdline is not None:
        cb = cmdline.encode()
        assert len(cb) < 512
        h[64:576] = b'\0' * 512
        h[64:64 + len(cb)] = cb
    d = hashlib.sha1(kernel + struct.pack('<I', len(kernel))
                     + ramdisk + struct.pack('<I', len(ramdisk))).digest()
    h[576:584] = d[:8]
    return pad(bytes(h)) + pad(kernel) + (pad(ramdisk) if ramdisk else b'')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('template')
    ap.add_argument('out')
    ap.add_argument('--kernel', required=True)
    ap.add_argument('--ramdisk', default=None)
    ap.add_argument('--cmdline', default=None)
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    header = open(a.template, 'rb').read()[:PAGE]
    kernel = open(a.kernel, 'rb').read()
    ramdisk = open(a.ramdisk, 'rb').read() if a.ramdisk else b''
    blob = build(header, kernel, ramdisk, a.cmdline)
    open(a.out, 'wb').write(blob)
    ks, ka, rs, ra = struct.unpack_from('<4I', blob, 8)
    print(f'{a.out}: {len(blob)} bytes, kernel {ks} @ {hex(ka)}, ramdisk {rs} @ {hex(ra)}, '
          f'id {blob[576:584].hex()}', file=sys.stderr)
    if a.check:
        assert ks == len(kernel) and rs == len(ramdisk)
        assert len(blob) % PAGE == 0 and blob[PAGE:PAGE + 4] == kernel[:4]
        assert blob[1620:1664] == header[1620:1664], 'Samsung header extras must survive'
        assert blob[576:584] != b'\0' * 8
        print('self-check: OK', file=sys.stderr)


if __name__ == '__main__':
    main()
