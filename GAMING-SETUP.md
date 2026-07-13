# Gaming setup (Steam, Proton)

**Opt-in.** This is not part of baseline machine setup. Apply only when separately requested — nothing here should be blanket-applied to a new box.

Prerequisite from baseline setup: the NVIDIA driver must come from the graphics-drivers PPA, so that `libnvidia-gl-XXX:i386` is present. See "NVIDIA driver" in `NEW-MACHINE-SETUP.md`. Without the i386 GL libs, 32-bit games fall back to software rendering (Vulkan → llvmpipe) or black-screen outright, and everything below is moot.

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

## vkBasalt (CRT post-processing)

Vulkan post-processing layer for applying ReShade FX shaders to games at runtime. Used here for CRT-style filters (scanlines and shadow mask; curvature is switched off) on 2D fighters and shoot-em-ups whose sprite art was authored against CRT presentation assumptions — the filter doesn't add a layer so much as restore the half of the visual contract that flat HD panels strip away.

Build from source. Ubuntu repos ship only the amd64 build of `vkbasalt`, but 32-bit Windows games (e.g. AH3's `AALib.exe`) launch a 32-bit Vulkan loader inside Proton and require an i386 build of the layer; the Vulkan loader requires bitness match between application and layer. Both archs built from one source tree, packaged separately via `checkinstall`, installed in parallel. Single Vulkan manifest at `/usr/share/vulkan/implicit_layer.d/vkBasalt.json` serves both archs — `library_path` is the bare soname `libvkbasalt.so`, which the loader resolves per-arch via ld.so.

Detailed recipe in `VKBASALT-SETUP.md`: build steps, dependency cascade (`spirv-headers`, `glslang-dev`, `libvulkan-dev`+`:i386`), the `-m32`-flags 32-bit build (vkBasalt doesn't ship a meson cross-file), checkinstall workflow with the expected manifest-conflict workaround, shader install from `gripped/vkBasalt-working-reshade-shaders`, and the tuned `CRT_Lottes.fx` parameters for HD content (skip the resolution-simulation pass; tune scanline darkness, blur, and mask intensity for readable small text).

## Per-game launch options

- **Arcana Heart 3:** `ENABLE_VKBASALT=1 DXVK_FRAME_RATE=60 %command%` — fighter timing tied to frames; uncapped 144 FPS subtly breaks move windows. Stock Proton 10.0-4 works (no longer needs GE-7-50 once the i386 NVIDIA libs are in place). Also enables vkBasalt to get the CRT filter (see above).

## Display GPU topology

- 3070 Ti = display GPU
- 4090 = eGPU, compute-only (no display attached, not a Vulkan presentation target)
- iGPU disabled in BIOS

The eGPU is not a presentation target, so games render on the internal dGPU regardless of which card is the more powerful. This is why the CRT-filter performance budget is set against the 3070 Ti, not the 4090.
