#!/bin/bash
#
# Cap the CPU package power via Intel RAPL, to keep the fan quiet under
# sustained load (e.g. Strata). The CPU-side sibling of nvidia-underclock;
# unlike GeForce cards, the CPU still supports a real power limit.
#
# Usage:
#   cpu-powercap [enable [PL1_W [PL2_W]]]
#   cpu-powercap disable
#
# PL1 is the long-term (sustained) limit, PL2 the short-term (burst) one.
#
# RAPL is exposed through two interfaces, each with its own limits, and the
# lower of the two is the one enforced. So we write both.
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

RAPL_MSR=/sys/class/powercap/intel-rapl:0
RAPL_MMIO=/sys/class/powercap/intel-rapl-mmio:0

action="enable"
if [ $# -ge 1 ]; then
    action="$1"
fi

# Write PL1 and PL2 (in watts) to the given RAPL interface.
set_limits() {
    local dir="$1" pl1_w="$2" pl2_w="$3"
    echo $((pl1_w * 1000000)) | sudo tee "$dir/constraint_0_power_limit_uw" > /dev/null
    echo $((pl2_w * 1000000)) | sudo tee "$dir/constraint_1_power_limit_uw" > /dev/null
}

show_limits() {
    local dir
    for dir in "$RAPL_MSR" "$RAPL_MMIO"; do
        echo "  $dir: PL1 $(( $(cat "$dir/constraint_0_power_limit_uw") / 1000000 )) W," \
             "PL2 $(( $(cat "$dir/constraint_1_power_limit_uw") / 1000000 )) W"
    done
}

if [ "$action" = "enable" ]; then
    pl1="${2:-35}"
    pl2="${3:-45}"
    echo -ne "Enabling CPU power cap (PL1 ${pl1} W, PL2 ${pl2} W)...\n"
    set_limits "$RAPL_MSR" "$pl1" "$pl2"
    set_limits "$RAPL_MMIO" "$pl1" "$pl2"
    show_limits
elif [ "$action" = "disable" ]; then
    echo -ne "Disabling CPU power cap (restoring factory limits)...\n"
    set_limits "$RAPL_MSR" 200 157
    set_limits "$RAPL_MMIO" 77 157
    show_limits
else
    echo -ne "Unknown action '$action'; valid: 'enable', 'disable'.\n"
    exit 2
fi
