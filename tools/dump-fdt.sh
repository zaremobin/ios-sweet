#!/usr/bin/env bash
# Dump the live device tree from the phone (needs adb + root).
# Run on the PC with the phone connected:  bash dump-fdt.sh a52sxq.dtb
set -euo pipefail
out=${1:-a52sxq.dtb}
adb wait-for-device
# /sys/firmware/fdt is root-readable; some kernels only expose it via /proc
if adb shell 'su -c "test -r /sys/firmware/fdt"' 2>/dev/null; then
  adb exec-out 'su -c "cat /sys/firmware/fdt"' > "$out"
else
  echo "no /sys/firmware/fdt; falling back to /proc/device-tree" >&2
  adb shell 'su -c "cat /proc/device-tree/memory@*/reg" ' | xxd -r -p > "${out}.mem" || true
  echo "got memory regs as ${out}.mem (hex). Send that file." >&2
  exit 2
fi
echo "wrote $out ($(stat -c%s "$out") bytes)"
python3 tools/fdtmem.py "$out"
