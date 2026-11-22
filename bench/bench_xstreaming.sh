#!/usr/bin/env bash
# Benchmark a running XStreaming Remote Play session on the tablet over ADB.
#
# usage: bench/bench_xstreaming.sh <label> [seconds]
# Start a stream first, then run this. Results go to bench/results/<label>-<time>.txt
#
# Measures (no root needed):
#   - frames actually shown: every actual-present timestamp of the video SurfaceView
#     from `dumpsys SurfaceFlinger --latency`, merged over the whole run
#   - WebRTC EglRenderer stats from logcat (received / dropped / render time)
#   - CPU of the app and of the whole system from /proc deltas
#   - PSS memory, GC count, log volume, network receive rate, temperature, CPU clock
set -euo pipefail

LABEL="${1:?label required, e.g. baseline}"
DURATION="${2:-60}"
PKG=com.xstreaming
LAYER="SurfaceView - com.xstreaming/com.xstreaming.MainActivity"
DIR="$(cd "$(dirname "$0")" && pwd)"
RAW="$(mktemp -d)"
trap 'rm -rf "$RAW"' EXIT
mkdir -p "$DIR/results"
OUT="$DIR/results/${LABEL}-$(date +%Y%m%d-%H%M%S).txt"

PID=$(adb shell pidof $PKG | tr -d '\r')
[ -n "$PID" ] || { echo "$PKG is not running" >&2; exit 1; }
APP_UID=$(adb shell "stat -c %u /proc/$PID" | tr -d '\r')

snap() {  # cpu jiffies of the app, its threads and the system; per-uid network; temperature
  adb shell "cat /proc/$PID/stat; head -1 /proc/stat; dumpsys battery | grep temperature; \
    grep -E '^[0-9]+ [a-z0-9]+ 0x0 $APP_UID ' /proc/net/xt_qtaguid/stats 2>/dev/null | sed 's/^/NET /'; \
    for t in /proc/$PID/task/*; do echo \"THR \$(cat \$t/stat)\"; done" | tr -d '\r'
}

adb logcat -c
snap > "$RAW/start.txt"
END=$(( $(date +%s) + DURATION ))
: > "$RAW/sf.txt"
# SurfaceFlinger keeps only the last ~127 frames (~2.1 s at 60 fps), so sample well
# inside that window; one adb call per sample keeps the interval short.
while [ "$(date +%s)" -lt "$END" ]; do
  adb shell "dumpsys SurfaceFlinger --latency '$LAYER'; cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null" \
    | tr -d '\r' >> "$RAW/sf.txt"
  sleep 0.8
done
snap > "$RAW/end.txt"
adb logcat -d | tr -d '\r' | grep " $PID " > "$RAW/log.txt" || true
adb shell "dumpsys meminfo $PID | grep -E 'TOTAL( PSS)?[: ]'" | tr -d '\r' | head -1 > "$RAW/mem.txt"
adb shell "cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null" | tr -d '\r' > "$RAW/thermal.txt"

python3 -I "$DIR/bench_report.py" "$RAW" "$LABEL" "$DURATION" | tee "$OUT"
echo "saved: $OUT"
