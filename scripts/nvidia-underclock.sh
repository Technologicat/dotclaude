#!/bin/bash
#
# See
#   nvidia-smi --query
# for supported clock frequencies (clocks and max clocks).
#
# Also, for a more detailed report with individual supported
# memory/gpu clock combinations,
#   nvidia-smi -q -d SUPPORTED_CLOCKS
#
# For example, the most relevant parts of the output of `nvidia-smi --query`
# on my laptop GPU, before making any changes:
#
# GPU 00000000:01:00.0
#     Product Name                      : NVIDIA GeForce RTX 3070 Ti Laptop GPU
#     Product Brand                     : GeForce
#     Product Architecture              : Ampere
#     Display Mode                      : Enabled
#     Display Active                    : Enabled
#     Persistence Mode                  : Disabled
# Temperature
#     GPU Current Temp                  : 51 C
#     GPU Shutdown Temp                 : 98 C
#     GPU Slowdown Temp                 : 95 C
#     GPU Max Operating Temp            : 87 C
#     GPU Target Temperature            : N/A
#     Memory Current Temp               : N/A
#     Memory Max Operating Temp         : N/A
# Power Readings
#     Power Management                  : Supported
#     Power Draw                        : 20.32 W
#     Power Limit                       : 125.00 W
#     Default Power Limit               : 125.00 W
#     Enforced Power Limit              : 125.00 W
#     Min Power Limit                   : 1.00 W
#     Max Power Limit                   : 150.00 W
# Clocks
#     Graphics                          : 210 MHz
#     SM                                : 210 MHz
#     Memory                            : 405 MHz
#     Video                             : 555 MHz
# Max Clocks
#     Graphics                          : 1785 MHz
#     SM                                : 1785 MHz
#     Memory                            : 7001 MHz
#     Video                             : 1575 MHz
#
# Also maybe relevant, if underclocking is causing problems:
#     nvidia-settings -a "[gpu:0]/GpuPowerMizerMode=1"
# Check the current value:
#     nvidia-settings -q GpuPowerMizerMode

# sudo nvidia-smi --power-limit=80

# 1.1 GHz lets Cyberpunk 2077 barely hit 80 W, keeping the GPU clock rate
# stable (no need for throttling to avoid exceeding the 80 W power limit).
# The limit is dependent on the exact load, so for other applications
# the appropriate value may differ.
#
# Tested ok for 2h:15min (no crashes). Note that PowerMizer was set
# to prefer maximum performance.
# sudo nvidia-smi --lock-gpu-clocks=210,1100

# # Generic underclocked setting
# sudo nvidia-smi --lock-memory-clocks=405,6400
# sudo nvidia-smi --lock-gpu-clocks=210,1600

# # Generic underclocked setting 2
# sudo nvidia-smi --lock-memory-clocks=405,6400
# sudo nvidia-smi --lock-gpu-clocks=210,1500

action="enable"

if [ $# -ge 1 ]; then
    action="$1"
fi

# Detect eGPU
if [ "$(nvidia-smi -L | wc -l)" -ge 2 ]; then
    HAVE_EGPU=1
else
    HAVE_EGPU=0
fi

if [ "$action" = "enable" ]; then
    echo -ne "Enabling NVIDIA underclocking...\n"
    # Power limiting removed in NVIDIA driver 530:
    #   https://github.com/NVIDIA/open-gpu-kernel-modules/issues/483
    # Adjusting the maximum allowed clock rate still cuts power, but slightly unpredictably.
    # sudo nvidia-smi --power-limit=80
    sudo nvidia-smi --lock-gpu-clocks=210,1100 --id=0
    if [ "$HAVE_EGPU" -eq 1 ]; then
        sudo nvidia-smi --lock-gpu-clocks=210,2500 --id=1
    fi
elif [ "$action" = "disable" ]; then
    echo -ne "Disabling NVIDIA underclocking...\n"
    # sudo nvidia-smi --power-limit=125
    sudo nvidia-smi --reset-gpu-clocks
else
    echo -ne "Unknown action '$action'; valid: 'enable', 'disable'.\n"
    exit 2
fi
