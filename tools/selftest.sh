#!/usr/bin/env bash
# Self-check: the a52sxq ADT builds and fdtmem.py reads a real FDT blob.
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

python3 tools/mkadt.py "$tmp/out.adt" >/dev/null 2>&1
[ -s "$tmp/out.adt" ] || { echo "FAIL: mkadt produced nothing"; exit 1; }
python3 tools/mkadt.py "$tmp/out.adt" --dump 2>/dev/null | grep -q "samsung,a52sxq" \
  || { echo "FAIL: ADT lacks the a52sxq identity"; exit 1; }
python3 tools/mkadt.py "$tmp/out.adt" --dump 2>/dev/null | grep -q "0x16a00000" \
  || { echo "FAIL: GIC reg is not SOC_BASE-relative (0x16a00000)"; exit 1; }

cat > "$tmp/t.dts" <<'DTS'
/dts-v1/;
/ { #address-cells = <2>; #size-cells = <2>;
  memory@80000000 { device_type = "memory"; reg = <0x0 0x80000000 0x0 0x60000000>; };
  interrupt-controller@17a00000 { compatible = "arm,gic-v3"; reg = <0x17a00000 0x10000>, <0x17a60000 0x100000>; };
  ufshc@1d84000 { compatible = "qcom,ufshc"; reg = <0x1d84000 0x3000>; };
};
DTS
command -v dtc >/dev/null || { echo "SKIP: dtc not installed (apt install device-tree-compiler)"; exit 0; }
dtc -I dts -O dtb -o "$tmp/t.dtb" "$tmp/t.dts" 2>/dev/null
out=$(python3 tools/fdtmem.py "$tmp/t.dtb")
grep -q "'0x80000000', '0x60000000'" <<<"$out" || { echo "FAIL: memory bank 0x80000000 not parsed"; echo "$out"; exit 1; }
grep -q "'0x17a00000'" <<<"$out" || { echo "FAIL: GIC not parsed"; exit 1; }
grep -q "'0x1d84000'" <<<"$out" || { echo "FAIL: UFS not parsed"; exit 1; }
# Shim compiles for aarch64 with no absolute relocations (needs the cross gcc)
if command -v aarch64-linux-gnu-gcc >/dev/null; then
  SKIP_IMAGE=1 bash shim/build.sh >/dev/null 2>&1 || { echo "FAIL: shim build"; exit 1; }
  [ -s shim/out/Image ] || { echo "FAIL: no shim Image"; exit 1; }
  echo "OK: shim compiles ($(stat -c%s shim/out/Image) byte Image)"
else
  echo "SKIP: aarch64-linux-gnu-gcc not installed (apt install gcc-aarch64-linux-gnu)"
fi

echo "OK: ADT builds, identity present, FDT memory/GIC/UFS parsed"

# Real-device regression: only when a live FDT dump is available (data/ is untracked)
if [ -f ../data/a52sxq.dtb ]; then
  out=$(python3 tools/fdtmem.py ../data/a52sxq.dtb)
  grep -q "'0x180000000', '0x100000000'" <<<"$out" || { echo "FAIL: 4 GB upper bank not parsed"; exit 1; }
  grep -q "timer_hz: 19200000" <<<"$out" || { echo "FAIL: timer not 19.2 MHz"; exit 1; }
  grep -q "'0xe1000000', '0x2300000'" <<<"$out" || { echo "FAIL: splash framebuffer moved"; exit 1; }
  echo "OK: live a52sxq dump matches mkadt.py constants"
fi

