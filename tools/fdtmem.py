#!/usr/bin/env python3
"""Pull the few facts mkadt.py needs out of the LIVE device tree.

Usage: fdtmem.py /sys/firmware/fdt-dump.dtb [--json]

Run on the PC after tools/dump-fdt.sh; prints the memory banks plus the
interrupt-controller, UFS and timer facts so nothing here is guessed.
"""
import json, struct, sys

FDT_MAGIC = 0xd00dfeed


def parse(blob):
    magic, totalsize, off_struct, off_strings, _off_rsv, _ver, _lcv, _boot, size_strings, size_struct = \
        struct.unpack('>10I', blob[:40])
    if magic != FDT_MAGIC:
        raise SystemExit('not an FDT blob')
    strings = blob[off_strings:off_strings + size_strings]
    end = off_struct + size_struct
    p, path, nodes = off_struct, [], {}
    while p < end:
        tok, = struct.unpack('>I', blob[p:p + 4]); p += 4
        if tok == 1:  # BEGIN_NODE
            e = blob.index(b'\0', p)
            name, p = blob[p:e].decode(), (e + 1 + 3) & ~3  # name is NUL-padded to 4 bytes
            path.append(name)
            nodes['/'.join(path)] = {}
        elif tok == 2:  # END_NODE
            path.pop()
        elif tok == 3:  # PROP
            ln, nameoff = struct.unpack('>II', blob[p:p + 8]); p += 8
            name = strings[nameoff:strings.index(b'\0', nameoff)].decode()
            nodes['/'.join(path)][name] = blob[p:p + ln]; p += ln
            p = (p + 3) & ~3
        elif tok == 9:  # END
            break
    return nodes


def words(v):
    return list(struct.unpack('>%dI' % (len(v) // 4), v[:len(v) // 4 * 4]))


def main():
    nodes = parse(open(sys.argv[1], 'rb').read())
    out = {'memory': [], 'gic': None, 'ufs': None, 'timebase': None, 'bootargs': None}
    for path, props in nodes.items():
        leaf = path.rsplit('/', 1)[-1]
        reg = props.get('reg')
        if leaf.startswith('memory@') and reg:
            w = words(reg)
            for i in range(0, len(w) - 3, 4):  # 2 address cells + 2 size cells
                base = (w[i] << 32) | w[i + 1]
                size = (w[i + 2] << 32) | w[i + 3]
                if size:
                    out['memory'].append([hex(base), hex(size)])
        elif leaf.startswith('interrupt-controller@') and b'arm,gic-v3' in props.get('compatible', b''):
            out['gic'] = [hex(x) for x in words(reg)]
        elif leaf.startswith('ufshc@') and b'qcom,ufshc' in props.get('compatible', b''):
            out['ufs'] = [hex(x) for x in words(reg)]
        elif props.get('timebase-frequency'):
            out['timebase'] = words(props['timebase-frequency'])[0]
        if props.get('bootargs'):
            out['bootargs'] = props['bootargs'].rstrip(b'\0').decode(errors='replace')
    out['memory'].sort()
    if '--json' in sys.argv:
        print(json.dumps(out, indent=1))
    else:
        for k, v in out.items():
            print(f'{k}: {v}')


if __name__ == '__main__':
    main()
