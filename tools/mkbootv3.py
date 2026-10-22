#!/usr/bin/env python3
"""Write an Android boot image for a52sxq.

Two layouts, both measured from the phone (2026-10-22):

  boot      header v3: header_size 1580, kernel 45,021,696, ramdisk 892,339,
            cmdline at +44. No load addresses; DTB stays in vendor_boot.
  recovery  header v2, as the working TWRP image here: kernel 0x8000,
            ramdisk 0x02000000, tags 0x01e00000, page 4096, name SRPUE26A001.
            ABL refused a v3 image on the recovery partition and dropped to
            Download mode, so use --v2 there. No SEANDROIDENFORCE trailer: the
            TWRP image ends in zeros, so that magic was a red herring.

Usage: mkbootv3.py OUT.img --kernel Image [--ramdisk f] [--v2] [--check]
"""
import argparse, hashlib, struct, sys

PAGE = 4096
HEADER_SIZE = 1580
MAGIC = b'ANDROID!'
SAMSUNG_TRAILER = b'SEANDROIDENFORCE'

# Measured from the phone's TWRP recovery header
V2 = dict(kernel_addr=0x00008000, ramdisk_addr=0x02000000, tags_addr=0x01e00000,
          os_version=0x18000164, name=b'SRPUE26A001')


def pad(b, page=PAGE):
    return b + b'\0' * (-len(b) % page)


def build_v2(kernel, ramdisk=b'', cmdline='console=null', **kw):
    v = dict(V2, **kw)
    h = bytearray(PAGE)
    h[0:8] = MAGIC
    struct.pack_into('<10I', h, 8, len(kernel), v['kernel_addr'],
                     len(ramdisk), v['ramdisk_addr'], 0, 0, v['tags_addr'],
                     PAGE, 2, v['os_version'])
    h[48:64] = bytes(v['name']).ljust(16, b'\0')[:16]
    cb = cmdline.encode() if isinstance(cmdline, str) else cmdline
    assert len(cb) < 512, 'v2 cmdline is limited to 511 bytes'
    h[64:64 + len(cb)] = cb
    if kw.get('sha1_id'):
        # AOSP mkbootimg's id field: SHA1(kernel, kernel_size, ramdisk, ramdisk_size)
        d = hashlib.sha1(kernel + struct.pack('<I', len(kernel))
                         + ramdisk + struct.pack('<I', len(ramdisk))).digest()
        h[576:584] = d[:8]
    return pad(bytes(h)) + pad(kernel) + (pad(ramdisk) if ramdisk else b'')


def build_v3(kernel, ramdisk=b'', cmdline='console=null', os_version=0x16000199,
             samsung=False):
    h = bytearray(HEADER_SIZE)
    h[0:8] = MAGIC
    struct.pack_into('<IIII', h, 8, len(kernel), len(ramdisk), os_version, HEADER_SIZE)
    struct.pack_into('<I', h, 40, 3)
    cb = cmdline.encode() if isinstance(cmdline, str) else cmdline
    assert len(cb) < 1536, 'cmdline too long for the v3 header'
    h[44:44 + len(cb)] = cb
    body = pad(bytes(h)) + pad(kernel) + (pad(ramdisk) if ramdisk else b'')
    return body + SAMSUNG_TRAILER if samsung else body


def parse(blob):
    assert blob[:8] == MAGIC, 'not a boot image'
    ver = struct.unpack_from('<I', blob, 40)[0]
    if ver == 3:
        ks, rs, osv, hs = struct.unpack_from('<IIII', blob, 8)
        return {'kernel_size': ks, 'ramdisk_size': rs, 'os_version': hex(osv),
                'header_size': hs, 'header_version': 3,
                'cmdline': blob[44:HEADER_SIZE].split(b'\0')[0].decode(errors='replace')}
    ks, ka, rs, ra, _ss, _sa, ta, ps = struct.unpack_from('<8I', blob, 8)
    return {'kernel_size': ks, 'kernel_addr': hex(ka), 'ramdisk_size': rs,
            'ramdisk_addr': hex(ra), 'tags_addr': hex(ta), 'page_size': ps,
            'os_version': hex(struct.unpack_from('<I', blob, 44)[0]),
            'header_version': 2,
            'name': blob[48:64].rstrip(b'\0').decode(errors='replace'),
            'cmdline': blob[64:576].split(b'\0')[0].decode(errors='replace')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--kernel', required=True)
    ap.add_argument('--ramdisk', default=None)
    ap.add_argument('--cmdline', default='console=null')
    ap.add_argument('--v2', action='store_true', help='v2 layout (recovery partition)')
    ap.add_argument('--id', action='store_true', help='fill the v2 SHA1 id field like mkbootimg')
    ap.add_argument('--samsung', action='store_true', help='v3: append SEANDROIDENFORCE')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    kernel = open(a.kernel, 'rb').read()
    ramdisk = open(a.ramdisk, 'rb').read() if a.ramdisk else b''
    blob = (build_v2(kernel, ramdisk, a.cmdline, sha1_id=a.id) if a.v2
            else build_v3(kernel, ramdisk, a.cmdline, samsung=a.samsung))
    open(a.out, 'wb').write(blob)
    info = parse(blob)
    print(f'{a.out}: {len(blob)} bytes, header v{info["header_version"]}, '
          f'kernel {info["kernel_size"]}, ramdisk {info["ramdisk_size"]}', file=sys.stderr)
    if a.check:
        assert info['kernel_size'] == len(kernel) and info['ramdisk_size'] == len(ramdisk)
        assert len(blob) % PAGE == 0
        assert blob[PAGE:PAGE + 8] == kernel[:8], 'kernel does not start at page 1'
        assert info['cmdline'] == a.cmdline
        if a.v2:
            assert info['kernel_addr'] == '0x8000' and info['ramdisk_addr'] == '0x2000000'
            assert info['tags_addr'] == '0x1e00000' and info['page_size'] == 4096
            assert info['name'] == 'SRPUE26A001'
        else:
            assert info['header_size'] == HEADER_SIZE
        print('self-check: OK', file=sys.stderr)


if __name__ == '__main__':
    main()
