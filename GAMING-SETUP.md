# Gaming setup (Steam, Proton)

**Opt-in.** This is not part of baseline machine setup. Apply only when separately requested — nothing here should be blanket-applied to a new box.

Prerequisite: 32-bit GL and Vulkan drivers. Without them, 32-bit games fall back to software rendering (Vulkan → llvmpipe) or black-screen outright, and everything below is moot.

- **NVIDIA:** the driver must come from the graphics-drivers PPA, so that `libnvidia-gl-XXX:i386` is present. See "NVIDIA driver" in `NEW-MACHINE-SETUP.md`.
- **AMD (Mesa):** install Steam as `sudo apt install steam-installer mesa-vulkan-drivers:i386`, with the i386 architecture enabled (`dpkg --print-foreign-architectures`). `steam-installer` depends on the 32-bit Mesa GL driver but only *recommends* the 32-bit Vulkan one, hence naming it explicitly.

## Input Remapper phantom gamepad

Input Remapper (used here for Wacom tablet keys) creates a virtual gamepad device unconditionally, whether or not any mapping uses it. Steam enumerates it as a real controller and picks it as the default, shadowing the actual gamepad — so the real controller has to be reselected every boot. Recurs after Steam updates.

Suppress it via udev:

```bash
sudo tee /etc/udev/rules.d/65-hide-input-remapper-from-steam.rules <<'EOF'
SUBSYSTEM=="input", ATTRS{name}=="input-remapper gamepad", ENV{ID_INPUT_JOYSTICK}="0", ENV{ID_INPUT}="0", TAG-="uaccess", OWNER="root", GROUP="root", MODE="0600"
EOF
sudo udevadm control --reload-rules
sudo reboot
```

**What changed.** The original rule (May 2026) only cleared the classification:

```
# 99-hide-input-remapper-from-steam.rules — obsolete
SUBSYSTEM=="input", ATTRS{name}=="input-remapper gamepad", ENV{ID_INPUT_JOYSTICK}="0", ENV{ID_INPUT}="0"
```

That was enough for as long as Steam honored `ID_INPUT_JOYSTICK`, and the `99-` prefix was harmless: consumers read the *final* udev property, so it doesn't matter that the flag is cleared late. As of a July 2026 Steam update, Steam no longer consults the classification — it opens `/dev/input/event*` directly (confirmed with `fuser`, which showed steam holding the event node open). The rule went toothless: the device name never changed, Steam simply stopped asking the question the rule was answering.

So the flag is no longer the lever. **Access is.** Hence the two additions:

- `OWNER`/`GROUP`/`MODE` take the node to root-owned `0600`, so a direct open as a normal user fails outright.
- `TAG-="uaccess"` stops the ACL that would otherwise hand the seat's user read-write access to the node regardless of its mode bits. Without this, `0600` is defeated — the ACL is precisely what grants a desktop user access to their own input devices.

**And *that* is where the `65-` prefix becomes load-bearing.** For input devices, udev runs:

| Priority | Rule | Effect |
|---|---|---|
| 60 | `60-input-id.rules` | `input_id` builtin sets `ID_INPUT_JOYSTICK=1` from the EV capability bits |
| 70 | `70-uaccess.rules` | sees `ID_INPUT_JOYSTICK=1` → adds `TAG+="uaccess"` |
| 73 | `73-seat-late.rules` | matches the tag → runs the `uaccess` **builtin**, which writes the ACL |

Dropping the tag at 99 would be too late: the builtin at 73 has already written the ACL to the device node, and un-tagging a device whose ACL is on disk does nothing (`getfacl` kept showing the user entry survive every variant of a `99-` rule, including one with `TAG-="uaccess"` in it). **udev priorities are not "later wins" when a builtin is involved** — the suppression has to land in the window *between* the classification at 60 and its consumer at 70. At 65, clearing `ID_INPUT_JOYSTICK` means `70-uaccess` never adds the tag in the first place, so the builtin at 73 never fires and no ACL is ever written. (Which makes the explicit `TAG-="uaccess"` clause redundant — it removes a tag that will never exist. Keep it as documentation of intent, and as insurance if the classification dodge is ever bypassed too.)

**A reboot is genuinely required**, not as ritual: the live device node still carries the stale ACL granted under the old ordering, and the `uaccess` builtin only ever runs to *grant* — with the tag now absent it won't run at all, so it never revokes what's already there. `udevadm trigger` will not clear it. Only a fresh boot recreates the node through the corrected rule order.

`ATTRS{name}` (plural) walks up the device tree — required here, since for evdev the name lives on the parent input device, not the event node.

### Verifying

Device numbers drift across restarts; re-derive them from `/proc/bus/input/devices` first (the rule matches by name, so the drift is harmless).

```bash
getfacl /dev/input/eventNN                                # expect: no user ACL line
fuser -v /dev/input/eventNN                               # expect: no steam
udevadm info -q property /dev/input/jsN | grep -i input   # expect ID_INPUT_JOYSTICK=0 or absent
```

### If it breaks again

First check that the rule file survived (OS reinstalls clear `/etc/udev/rules.d/`; Steam updates don't), and that the device name string hasn't changed (`grep -A5 -i input-remapper /proc/bus/input/devices`) — a name change is only plausible after an input-remapper version bump, so it's the thing to check after an OS upgrade.

If both check out and the phantom is still there, the mechanism has changed again. `fuser` on the device node is what settled it last time: it shows unambiguously who is reading what.

## Logitech G29 racing wheel: `new-lg4ff`

The in-kernel `hid-logitech` module drives the G29 but plays only the constant-force effect. [`berarma/new-lg4ff`](https://github.com/berarma/new-lg4ff) is an out-of-tree replacement for the same module that plays most of the Linux FF API (all but inertia), with realtime effect handling, plus sysfs knobs for global gain, autocenter and per-type spring/damper/friction levels.

**The G29's mode switch must be in the PS3 position** — that is the mode the driver supports.

Installed through DKMS, so it is rebuilt automatically for each new kernel. DKMS installs it *as* `hid-logitech` under `updates/dkms/`, which takes precedence over the in-tree module of the same name. Nothing else is configured: no modprobe options, no udev rules. Secure Boot is disabled on the machines that run it (the personal machine, and the AI server in the living room), so the module needs no signing. Version 0.5.0 builds and installs cleanly on kernel 7.0 (checked 2026-11-15).

The checkout lives at `~/Documents/koodit/new-lg4ff`. Given a directory, `dkms install` copies the source to `/usr/src/new-lg4ff-<version>` by itself (without `.git`), taking the version from `dkms.conf`:

```bash
git clone https://github.com/berarma/new-lg4ff ~/Documents/koodit/new-lg4ff
sudo dkms install ~/Documents/koodit/new-lg4ff
sudo update-initramfs -u
```

The last step is per upstream's README: newer DKMS no longer updates the initramfs, and without it the in-tree module loads at boot instead. On the current install the DKMS build is already in the initramfs (`lsinitramfs /boot/initrd.img-$(uname -r) | grep hid-logitech` shows `updates/dkms/hid-logitech.ko`), so check that after a fresh install.

### Updating

Remove the old version from every kernel, then install the new one:

```bash
dkms status new-lg4ff                     # which version is installed
sudo dkms remove new-lg4ff/<old> --all
git -C ~/Documents/koodit/new-lg4ff pull
sudo dkms install ~/Documents/koodit/new-lg4ff
sudo update-initramfs -u
```

**Update before an OS upgrade that brings a newer kernel.** Upstream needed build fixes for Linux 6.12 and 6.15, which landed in 0.5.0. If the DKMS build fails on a new kernel, the in-tree module is still there and loads instead, so the wheel keeps working with degraded force feedback rather than failing outright.

### Verifying

Without the wheel connected:

```bash
dkms status new-lg4ff        # expect "installed" for the running kernel
modinfo -n hid-logitech      # expect a path under updates/dkms/, not kernel/drivers/hid/
```

With it connected:

```bash
sudo dmesg | grep -i 'force feedback'           # the driver version is at the end of the line
ls /sys/bus/hid/drivers/logitech/*/             # expect gain, spring_level, ffb_leds, ...
```

The sysfs entries are the unambiguous check, since the in-tree module does not create `gain` or the `*_level` files.

## Audio: silent games on a device with a narrow rate table

Symptom: one game has no sound at all, while everything else on the desktop plays normally.

The USB interface used here has **no 48000 Hz at 16 bits** (its full rate table is in `HARDWARE-NOTES.md`), and PulseAudio's stock configuration walks straight into that combination:

```
; default-sample-format = s16le
; default-sample-rate = 44100
; alternate-sample-rate = 48000
```

The sink runs at `default-sample-rate` and switches to `alternate-sample-rate` when a stream's native rate matches it, so that 48 kHz material can play unresampled. Essentially all modern game audio is 48 kHz. So the first such stream makes PulseAudio reopen the sink at 48000/`s16le`, the device has no altsetting offering that pair, and the game is silent — while every 44.1 kHz source on the machine carries on working, which is what makes it look like a game bug rather than a device one.

Nothing rescues it in between: `module-alsa-sink` opens the device with explicit parameters, so PulseAudio meets the raw rate table itself.

**The fix**, in `/etc/pulse/daemon.conf`:

```
alternate-sample-rate = 44100
resample-method = soxr-vhq
```

The first takes 48000 out of the pair of rates the sink will run at, pinning it to 44100 — which the device does support at 16 bits. The second upgrades the resampling that this makes unavoidable: stock is `speex-float-1`, and `soxr-vhq` is SoX's very-high-quality mode.

Apply with `systemctl --user restart pulseaudio`.

**To find out what is actually customized**, rather than trying to remember:

```bash
dpkg -V pulseaudio                                # flags daemon.conf when it differs from the package
grep -vE '^\s*;|^\s*$' /etc/pulse/daemon.conf     # stock lines are all ';'-commented, so this is the diff
```

That pair is worth keeping in mind generally: `dpkg -V` finds *which* config files a past self edited, across every package, which is a far better starting point than guessing at directories.

### Not the fix: `libasound2-plugins`

Recorded because it is the plausible-looking answer, and wrong. The package is installed for both architectures and does ship ALSA's `samplerate`/`speexrate` converters — but nothing here names a converter for `plug` to use (`grep -rn rate_converter /usr/share/alsa /etc/alsa` is empty), and the path that failed was PulseAudio's, which does not go through `plug` at all.

### After an OS upgrade

Newer Mint ships PipeWire, where none of the above applies: `/etc/pulse/daemon.conf` is not read, and rate policy lives in `~/.config/pipewire/pipewire.conf.d/` as `default.clock.rate` and `default.clock.allowed-rates`.

It may well need no equivalent. PipeWire negotiates a format per device instead of defaulting everything to `s16le`, and on the work machine it opens this same interface at **`S24_3LE` 48000** — exactly the pairing the device does support, sidestepping the gap without being told to. Test before configuring anything.

If a rate policy *is* wanted there, list what the hardware actually offers:

```
context.properties = {
    default.clock.rate          = 44100
    default.clock.allowed-rates = [ 44100 48000 ]
}
```

### If a game is silent again

```bash
cat /proc/asound/card<N>/stream0    # the device's real rate table, per altsetting
pactl list sinks                    # what rate and format the sink is actually running at
pactl list sink-inputs              # while the game runs — did it reach the sound server at all?
```

A game that shows up as a sink-input has reached the server, so any refusal is between server and hardware: compare the sink's rate and format against the rate table. A game that never appears did not get that far, and the cause is upstream of the server.

## vkBasalt (CRT post-processing)

Vulkan post-processing layer for applying ReShade FX shaders to games at runtime. Used here for CRT-style filters (scanlines and shadow mask; curvature is switched off) on 2D fighters and shoot-em-ups whose sprite art was authored against CRT presentation assumptions — the filter doesn't add a layer so much as restore the half of the visual contract that flat HD panels strip away.

Build from source. Ubuntu repos ship only the amd64 build of `vkbasalt`, but 32-bit Windows games (e.g. AH3's `AALib.exe`) launch a 32-bit Vulkan loader inside Proton and require an i386 build of the layer; the Vulkan loader requires bitness match between application and layer. Both archs built from one source tree, packaged separately via `checkinstall`, installed in parallel. Single Vulkan manifest at `/usr/share/vulkan/implicit_layer.d/vkBasalt.json` serves both archs — `library_path` is the bare soname `libvkbasalt.so`, which the loader resolves per-arch via ld.so.

Detailed recipe in `VKBASALT-SETUP.md`: build steps, dependency cascade (`spirv-headers`, `glslang-dev`, `libvulkan-dev`+`:i386`), the `-m32`-flags 32-bit build (vkBasalt doesn't ship a meson cross-file), checkinstall workflow with the expected manifest-conflict workaround, shader install from `gripped/vkBasalt-working-reshade-shaders`, and the tuned `CRT_Lottes.fx` parameters for HD content (skip the resolution-simulation pass; tune scanline darkness, blur, and mask intensity for readable small text).

## Old Unreal Engine games: crash on dead Epic telemetry

Some older Unreal Engine games on Steam report telemetry to Epic's online-services endpoints, which are now dead, and crash on it. Blackholing the endpoints in `/etc/hosts` works around it (tested 2026-11-21):

```
# --- dead Epic online-services endpoints (for some old games with telemetry) ---
0.0.0.0   datarouter-weighted.ol.epicgames.com
0.0.0.0   datarouter.ol.epicgames.com
::1       datarouter-weighted.ol.epicgames.com
::1       datarouter.ol.epicgames.com
```

## DXVK frame cap and vsync

**`DXVK_FRAME_RATE` is gone from DXVK itself**: removed upstream on 2025-11-17 (`dae35be`, "Remove DXVK_FRAME_RATE env var"), so DXVK 3.x ignores it. Whether it still works depends on the Proton, and it fails silently, the game simply running uncapped:

- **GE-Proton 10-34 and 11-11** emulate it: `protonfixes.setup_frame_rate` rewrites `DXVK_FRAME_RATE` (or `VKD3D_FRAME_RATE`, or `PROTON_FRAME_RATE`) into `DXVK_CONFIG` as `dxgi.maxFrameRate` and `d3d9.maxFrameRate`.
- **Stock Proton 10.0** ships DXVK 2.6.2, which still reads it.
- **Stock Proton 11.0** ships a DXVK newer than the removal, and its launch script has no shim. There it does nothing.

(Checked 2026-11-21: the string `DXVK_FRAME_RATE` is present in Proton 10.0's `d3d11.dll` and absent from Proton 11.0's, while `DXVK_CONFIG` is present in both.)

**The form that works everywhere is `DXVK_CONFIG`**, which takes `dxvk.conf` syntax inline, `;`-separated — so no config file is needed either:

```
DXVK_CONFIG="dxgi.maxFrameRate = 60; d3d9.maxFrameRate = 60" %command%
```

`dxgi.*` covers D3D10/11, `d3d9.*` covers D3D9; setting both means not having to know which API the game uses. DXVK does not handle D3D12 (that is VKD3D-Proton).

**Vsync for a game that has no vsync option** is the same mechanism: `dxgi.syncInterval = 1` (D3D10/11) or `d3d9.presentInterval = 1` (D3D9) forces it on. A file named by `DXVK_CONFIG_FILE` works too, but the inline form keeps the setting visible in the launch options. Vsync caps the frame rate at the *display's* refresh rate, which on the 144 Hz panel is 144, not 60 — so a game whose timing is tied to 60 FPS still needs the limiter. Under vsync at 144 Hz a 60 FPS cap paces unevenly: 144/60 = 2.4, so frames alternate between being shown for two and three refreshes. Switching the panel to its 60 Hz mode for such a game avoids that.

Status 2026-11-21: `dxgi.syncInterval = 1` appears to remove intermittent tearing in one game, tested together with a 60 FPS cap; not yet tested on its own.

## Per-game launch options

- **Arcana Heart 3:** `ENABLE_VKBASALT=1 DXVK_FRAME_RATE=60 %command%` — the game's timing is tied to frames and it expects 60 FPS, so uncapped on a 144 Hz panel it runs at 144/60 = 2.4× speed. Not a subtle drift in the move windows; the whole game is fast. The frame cap is what makes it playable at all. Stock Proton 10.0-4 works (no longer needs GE-7-50 once the i386 NVIDIA libs are in place). `ENABLE_VKBASALT=1` is what switches on the CRT filter (see above).

## Display GPU topology

- 3070 Ti = display GPU
- 4090 = eGPU, compute-only (no display attached, not a Vulkan presentation target)
- iGPU disabled in BIOS

The eGPU is not a presentation target, so games render on the internal dGPU regardless of which card is the more powerful. This is why the CRT-filter performance budget is set against the 3070 Ti, not the 4090.
