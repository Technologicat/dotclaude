#!/bin/bash
#
# Cap the CPU package power via Intel RAPL, to keep the fan quiet under
# sustained load (e.g. Strata). The CPU-side sibling of nvidia-underclock;
# unlike GeForce cards, the CPU still supports a real power limit.
#
# Usage:
#   cpu-powercap [enable [PL1_W [PL2_W]]]
#   cpu-powercap disable
#   cpu-powercap watch [INTERVAL_S]
#
# PL1 is the long-term (sustained) limit, PL2 the short-term (burst) one.
# `disable` restores whatever the limits were before the first `enable`.
# `watch` prints the limits, then the measured package power, busy % and
# clock every INTERVAL_S seconds (default 2) until Ctrl+C. Run it under
# load to see whether a cap actually holds.
#
# RAPL is exposed through two interfaces, each with its own limits, and the
# lower of the two is the one enforced. So we write both, where both exist.
#
# Factory values on the work machine (i7-13850HX), read 2026-10-31:
#   intel-rapl:0       (MSR)   PL1 200 W, PL2 157 W  -- PL1 effectively unlimited (PSU is 240 W)
#   intel-rapl-mmio:0  (MMIO)  PL1  77 W, PL2 157 W  -- the PL1 actually in force
#
# Inspect the current state:
#   for d in /sys/class/powercap/intel-rapl:0 /sys/class/powercap/intel-rapl-mmio:0; do
#       echo "$d: $(cat $d/constraint_{0,1}_power_limit_uw)"; done
#
# These are runtime settings; a reboot restores the firmware defaults.
#
# Caveat (not verified here): thermald may rewrite RAPL limits on its own.
# If the cap does not hold, check that first.

action="enable"
if [ $# -ge 1 ]; then
    action="$1"
fi

# Whichever of the two RAPL interfaces this machine has.
interfaces=()
for dir in /sys/class/powercap/intel-rapl:0 /sys/class/powercap/intel-rapl-mmio:0; do
    if [ -d "$dir" ]; then
        interfaces+=("$dir")
    fi
done
if [ ${#interfaces[@]} -eq 0 ]; then
    echo "No RAPL package interface found under /sys/class/powercap; nothing to do."
    exit 1
fi

# The limits as they were before the first `enable`, which `disable` restores.
# The runtime dir is a tmpfs cleared at reboot -- which is also when the limits
# themselves revert to the firmware's -- so the snapshot cannot outlive them.
SNAPSHOT="${XDG_RUNTIME_DIR:?}/cpu-powercap.snapshot"

# Write PL1 and PL2 (in microwatts, the sysfs unit) to the given RAPL interface.
set_limits_uw() {
    local dir="$1" pl1_uw="$2" pl2_uw="$3"
    echo "$pl1_uw" | sudo tee "$dir/constraint_0_power_limit_uw" > /dev/null
    echo "$pl2_uw" | sudo tee "$dir/constraint_1_power_limit_uw" > /dev/null
}

show_limits() {
    local dir
    for dir in "${interfaces[@]}"; do
        echo "  $dir: PL1 $(( $(cat "$dir/constraint_0_power_limit_uw") / 1000000 )) W," \
             "PL2 $(( $(cat "$dir/constraint_1_power_limit_uw") / 1000000 )) W"
    done
}

if [ "$action" = "enable" ]; then
    pl1="${2:-35}"
    pl2="${3:-45}"
    # Only the first `enable` since boot (or since the last `disable`) takes the
    # snapshot, so trying another wattage does not save the previous cap as "factory".
    if [ ! -f "$SNAPSHOT" ]; then
        for dir in "${interfaces[@]}"; do
            echo "$dir $(cat "$dir/constraint_0_power_limit_uw") $(cat "$dir/constraint_1_power_limit_uw")"
        done > "$SNAPSHOT"
    fi
    echo -ne "Enabling CPU power cap (PL1 ${pl1} W, PL2 ${pl2} W)...\n"
    for dir in "${interfaces[@]}"; do
        set_limits_uw "$dir" $((pl1 * 1000000)) $((pl2 * 1000000))
    done
    show_limits
elif [ "$action" = "disable" ]; then
    if [ ! -f "$SNAPSHOT" ]; then
        echo "No saved limits in $SNAPSHOT; not enabled since boot, so nothing to restore."
        show_limits
        exit 0
    fi
    echo -ne "Disabling CPU power cap (restoring the limits saved by the first 'enable')...\n"
    while read -r dir pl1_uw pl2_uw; do
        set_limits_uw "$dir" "$pl1_uw" "$pl2_uw"
    done < "$SNAPSHOT"
    rm -f "$SNAPSHOT"
    show_limits
elif [ "$action" = "watch" ]; then
    echo "Current limits:"
    show_limits
    # The energy counters turbostat reads are root-only.
    exec sudo turbostat --quiet --show PkgWatt,Busy%,Bzy_MHz -i "${2:-2}"
else
    echo -ne "Unknown action '$action'; valid: 'enable', 'disable', 'watch'.\n"
    exit 2
fi
