#!/usr/bin/env python3
"""Log an AMD APU machine's power, temperatures and clocks to CSV, once per interval.

    powerlog [--interval S] [--duration S] [--out FILE] [--label TEXT] [--live]
    powerlog --once

For example, five minutes of idle in BIOS Balance mode:

    powerlog --duration 300 --out idle-balance.csv --label "idle, Balance"

To watch the readings while something runs, either print each one as it is taken, or show the current
one under `watch`:

    powerlog --live
    watch -n 1 powerlog --once

Columns: elapsed time, socket power (PPT), CPU temperature (Tctl), GPU edge
temperature, GPU busy %, GPU clock, mean and max CPU clock, 1-minute load, and
GTT in use. Prints a summary (mean, min, max) when done. Ctrl+C stops it early
and still prints the summary.

The CPU clocks are `scaling_cur_freq`, the frequency the cpufreq driver reports,
not the effective clock: with amd-pstate at idle it stays near `scaling_min_freq`
(2 GHz on Strix Halo) while the cores sit in C-states, and turbostat's average
effective clock reads a few MHz. Use it for boost behaviour under load, not as a
measure of how busy the CPU is.

Reads sysfs only, so it needs no root. Sensors are found by driver name rather
than by hwmon index, which is not stable across boots.
"""

import argparse
import csv
import glob
import os
import pathlib
import signal
import statistics
import sys
import time

__all__ = ["find_hwmon", "make_sampler", "format_reading", "summarize", "main"]


def find_hwmon(name):
    """Return the hwmon directory whose `name` file says `name`, or None."""
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            if pathlib.Path(d, "name").read_text().strip() == name:
                return pathlib.Path(d)
        except OSError:
            continue
    return None


def _read_int(path):
    try:
        return int(pathlib.Path(path).read_text().strip())
    except (OSError, ValueError):
        return None


def _scale(value, divisor):
    return None if value is None else value / divisor


def make_sampler():
    """Locate the sensors once, and return a function that takes one sample as a dict."""
    amdgpu = find_hwmon("amdgpu")
    k10temp = find_hwmon("k10temp")
    if amdgpu is None:
        sys.exit("powerlog: no amdgpu hwmon found")
    # The DRM device behind the amdgpu hwmon holds gpu_busy_percent and the GTT counters.
    device = (amdgpu / "device").resolve()
    cpufreqs = sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"))

    def sample():
        freqs = [f for f in (_read_int(p) for p in cpufreqs) if f is not None]  # kHz
        return {
            "ppt_w": _scale(_read_int(amdgpu / "power1_input"), 1e6),  # µW
            "cpu_temp_c": _scale(_read_int(k10temp / "temp1_input"), 1e3) if k10temp else None,  # m°C
            "gpu_temp_c": _scale(_read_int(amdgpu / "temp1_input"), 1e3),
            "gpu_busy_pct": _read_int(device / "gpu_busy_percent"),
            "gpu_mhz": _scale(_read_int(amdgpu / "freq1_input"), 1e6),  # Hz
            "cpu_mhz_mean": statistics.fmean(freqs) / 1e3 if freqs else None,
            "cpu_mhz_max": max(freqs) / 1e3 if freqs else None,
            "load1": os.getloadavg()[0],
            "gtt_used_gib": _scale(_read_int(device / "mem_info_gtt_used"), 2**30),
        }

    return sample


def format_reading(row):
    """Format one sample from `make_sampler` as a single human-readable line."""
    def num(key, fmt, unit=""):
        value = row.get(key)
        return "n/a" if value is None else f"{value:{fmt}}{unit}"
    return (f"PPT {num('ppt_w', '6.1f', ' W')} | "
            f"Tctl {num('cpu_temp_c', '5.1f', ' °C')} | "
            f"GPU {num('gpu_temp_c', '4.0f', ' °C')} {num('gpu_busy_pct', '3d', '%')} {num('gpu_mhz', '5.0f', ' MHz')} | "
            f"CPU max {num('cpu_mhz_max', '5.0f', ' MHz')} | "
            f"load {num('load1', '5.2f')} | "
            f"GTT {num('gtt_used_gib', '6.2f', ' GiB')}")


def summarize(rows, fields):
    print(f"\n{len(rows)} sample{'s' if len(rows) != 1 else ''}")
    print(f"{'':16}{'mean':>10}{'min':>10}{'max':>10}")
    for f in fields:
        vals = [r[f] for r in rows if r[f] is not None]
        if vals:
            print(f"{f:16}{statistics.fmean(vals):10.2f}{min(vals):10.2f}{max(vals):10.2f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between samples (default 1)")
    ap.add_argument("--duration", type=float, default=None, help="stop after this many seconds (default: until Ctrl+C)")
    ap.add_argument("--out", default=None, help="CSV file to write (default: print only the summary)")
    ap.add_argument("--label", default="", help="free text stored in every row, e.g. 'idle, Balance'")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="also print each reading as it is taken")
    mode.add_argument("--once", action="store_true", help="print one reading and exit (for `watch`)")
    args = ap.parse_args()

    sample = make_sampler()
    if args.once:
        print(format_reading(sample()))
        return

    fields = list(sample().keys())
    rows = []
    stop = False

    def on_sigint(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, on_sigint)

    out = open(args.out, "w", newline="") if args.out else None  # noqa: SIM115 -- optional, closed in the finally below
    writer = csv.DictWriter(out, fieldnames=["t_s", "label", *fields]) if out else None
    if writer:
        writer.writeheader()
    t0 = time.monotonic()
    next_t = t0
    try:
        while not stop:
            row = sample()
            rows.append(row)
            if args.live:
                print(f"{time.monotonic() - t0:7.1f} s  {format_reading(row)}", flush=True)
            if writer:
                writer.writerow({"t_s": round(time.monotonic() - t0, 2), "label": args.label, **row})
                out.flush()
            next_t += args.interval
            if args.duration is not None and next_t - t0 > args.duration:
                break
            time.sleep(max(0.0, next_t - time.monotonic()))
    finally:
        if out:
            out.close()
    summarize(rows, fields)


if __name__ == "__main__":
    main()
