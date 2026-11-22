#!/usr/bin/env python3
"""Summarise the raw files written by bench_xstreaming.sh. usage: bench_report.py <rawdir> <label> <seconds>"""
import os
import re
import statistics
import sys

raw, label, duration = sys.argv[1], sys.argv[2], float(sys.argv[3])


def read(name):
    with open(os.path.join(raw, name)) as fh:
        return fh.read()


# --- frames shown: union of actual-present timestamps across all samples
stamps = set()
for line in read("sf.txt").splitlines():
    p = line.split()
    if len(p) == 3:
        t = int(p[1])
        if 0 < t < 2 ** 62:
            stamps.add(t)
s = sorted(stamps)
if len(s) > 2:
    span = (s[-1] - s[0]) / 1e9
    gaps = [(b - a) / 1e6 for a, b in zip(s, s[1:])]
    fps = (len(s) - 1) / span
    # per-second fps buckets
    buckets = {}
    for t in s:
        buckets[int((t - s[0]) / 1e9)] = buckets.get(int((t - s[0]) / 1e9), 0) + 1
    per_sec = [v for k, v in sorted(buckets.items())][1:-1] or [0]
else:
    span, gaps, fps, per_sec = 0, [0], 0, [0]

# --- cpu from /proc deltas
def cpu(snapshot):
    lines = snapshot.splitlines()
    pstat = lines[0].rsplit(")", 1)[1].split()
    app = int(pstat[11]) + int(pstat[12])  # utime + stime (fields 14,15)
    sysv = [int(x) for x in lines[1].split()[1:]]
    total, idle = sum(sysv), sysv[3] + sysv[4]
    # NET <idx> <iface> <tag> <uid> <cnt_set> <rx_bytes> ...
    rx = sum(int(l.split()[6]) for l in lines if l.startswith("NET "))
    temp = next((int(l.split(":")[1]) / 10 for l in lines if "temperature" in l), None)
    threads = {}
    for l in lines:
        if l.startswith("THR "):
            head, rest = l[4:].split(" (", 1)
            name, fields = rest.rsplit(") ", 1)
            f = fields.split()
            threads[head] = (name, int(f[11]) + int(f[12]))
    return app, total, idle, rx, temp, threads


a0, t0, i0, rx0, temp0, th0 = cpu(read("start.txt"))
a1, t1, i1, rx1, temp1, th1 = cpu(read("end.txt"))
dt_total = max(t1 - t0, 1)
ncpu = 4
app_pct_total = 100.0 * (a1 - a0) / dt_total                 # share of all 4 cores
app_pct_core = app_pct_total * ncpu                          # % of one core
sys_busy = 100.0 * (1 - (i1 - i0) / dt_total)
rx_mbps = (rx1 - rx0) * 8 / duration / 1e6

# --- logcat
log = read("log.txt").splitlines()
gc = sum(1 for l in log if "GC freed" in l)
egl = [re.search(r"Frames received: (\d+)\. Dropped: (\d+)\. Rendered: (\d+)\. Render fps: ([\d,\.]+)\. Average render time: (\d+) us", l)
       for l in log if "EglRenderer: Duration" in l]
egl = [m for m in egl if m]
recv = sum(int(m.group(1)) for m in egl)
drop = sum(int(m.group(2)) for m in egl)
rend = sum(int(m.group(3)) for m in egl)
rtime = statistics.mean(int(m.group(5)) for m in egl) if egl else 0
js_lines = sum(1 for l in log if "ReactNativeJS" in l)

mem = read("mem.txt").split()
pss_mb = next((int(x) / 1024 for x in mem if x.isdigit()), 0)
# CPU clocks are single kHz values mixed into sf.txt (the SF refresh-period line is ~16.6M ns)
freqs = [int(l) for l in read("sf.txt").splitlines() if l.strip().isdigit() and 100000 <= int(l) <= 5000000]
therm = [int(x) for x in read("thermal.txt").split() if x.lstrip("-").isdigit()]


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


print(f"== XStreaming benchmark: {label}  ({duration:.0f}s)")
print(f"frames shown        : {fps:5.1f} fps avg over {span:.0f}s ({len(s)} frames)")
print(f"per-second fps      : min {min(per_sec)}, p10 {pct(per_sec, 0.10)}, median {statistics.median(per_sec)}")
print(f"frame gaps          : median {statistics.median(gaps):.1f} ms, p99 {pct(gaps, 0.99):.1f} ms, max {max(gaps):.0f} ms, >33ms: {sum(g > 33 for g in gaps)}, >50ms: {sum(g > 50 for g in gaps)}")
print(f"webrtc renderer     : received {recv}, dropped {drop}, rendered {rend}, avg render {rtime:.0f} us")
print(f"cpu app             : {app_pct_core:5.1f}% of one core ({app_pct_total:.1f}% of all 4)")
print(f"cpu system busy     : {sys_busy:5.1f}%")
print(f"cpu clock avg       : {statistics.mean(freqs) / 1000:.0f} MHz" if freqs else "cpu clock avg       : n/a")
print(f"memory (PSS)        : {pss_mb:.0f} MB")
print(f"GC during run       : {gc}")
print(f"app log lines       : {len(log)} ({js_lines} from JS) = {len(log) / duration:.1f}/s")
print(f"network rx          : {rx_mbps:.2f} Mbps" if rx1 else "network rx          : n/a")
print(f"battery temp        : {temp0} -> {temp1} C")
print(f"thermal zones max   : {max(therm) if therm else 'n/a'}")

# in-app WebRTC stats, logged once per second as "[XSPERF] {json}" while the
# XStreaming performance panel is visible
import json  # noqa: E402

perf = []
for l in log:
    if "[XSPERF]" in l:
        try:
            perf.append(json.loads(l.split("[XSPERF]", 1)[1].strip()))
        except ValueError:
            pass


def num(v):
    m = re.search(r"-?\d+(\.\d+)?", str(v))
    return float(m.group(0)) if m else None


if perf:
    print(f"in-app stats ({len(perf)} samples, from the performance panel):")
    for key, unit in (("decode", "ms"), ("jit", "ms"), ("rtt", "ms"), ("fps", "fps"), ("br", "Mbps")):
        vals = [x for x in (num(p.get(key)) for p in perf) if x is not None]
        if vals:
            print(f"   {key:7s}: median {statistics.median(vals):6.1f} {unit}, p90 {pct(vals, 0.90):6.1f}, max {max(vals):6.1f}")
    last = perf[-1]
    print(f"   frames lost {last.get('fl')}, packets lost {last.get('pl')} (cumulative)")
else:
    print("in-app stats        : none (turn on 'Tampilkan performa' to log decode/jitter/RTT)")

# per-thread CPU (grouped by thread name), % of one core
by_name = {}
for tid, (name, j1) in th1.items():
    j0 = th0[tid][1] if tid in th0 else 0  # threads born mid-run count from zero
    by_name[name] = by_name.get(name, 0) + (j1 - j0)
jiffies_per_core = dt_total / ncpu
print("top threads (% of one core):")
for name, j in sorted(by_name.items(), key=lambda kv: -kv[1])[:12]:
    if j > 0:
        print(f"   {100.0 * j / jiffies_per_core:5.1f}%  {name}")
