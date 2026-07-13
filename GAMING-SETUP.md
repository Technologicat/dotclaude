# Gaming setup (Steam, Proton)

**Opt-in.** This is not part of baseline machine setup. Apply it only on a machine that games, and only when separately requested — nothing here should be blanket-applied to a new box.

Currently applies to `maia` (work + hobby machine). A work-only machine wants none of this.

Prerequisite from baseline setup: the NVIDIA driver must come from the graphics-drivers PPA, so that `libnvidia-gl-XXX:i386` is present. See "NVIDIA driver" in `NEW-MACHINE-SETUP.md`. Without the i386 GL libs, 32-bit games fall back to software rendering (Vulkan → llvmpipe) or black-screen outright, and everything below is moot.

## Input Remapper phantom gamepad

Input Remapper (used here for Wacom tablet keys) creates a virtual gamepad device unconditionally, regardless of whether any mapping uses it. Steam sees this as an extra Xbox controller and gets confused — needs per-boot reselection of the real controller. Hide the virtual gamepad from Steam (and any other SDL2-based app) via udev:

```bash
sudo tee /etc/udev/rules.d/99-hide-input-remapper-from-steam.rules <<'EOF'
SUBSYSTEM=="input", ATTRS{name}=="input-remapper gamepad", ENV{ID_INPUT_JOYSTICK}="0", ENV{ID_INPUT}="0"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Note `ATTRS{name}` (plural) — walks up the device tree, required for evdev devices since the name lives on the parent input device, not the event node. The device still exists for things that open it by path; only joystick auto-detection is suppressed. Verify with `udevadm info -q property /dev/input/jsN | grep ID_INPUT`.

## vkBasalt (CRT post-processing)

Vulkan post-processing layer for applying ReShade FX shaders to games at runtime. Used here for CRT-style filters (scanlines, shadow mask, mild barrel warp) on 2D fighters and shoot-em-ups whose sprite art was authored against CRT presentation assumptions — the filter doesn't add a layer so much as restore the half of the visual contract that flat HD panels strip away.

Build from source. Ubuntu repos ship only the amd64 build of `vkbasalt`, but 32-bit Windows games (e.g. AH3's `AALib.exe`) launch a 32-bit Vulkan loader inside Proton and require an i386 build of the layer; the Vulkan loader requires bitness match between application and layer. Both archs built from one source tree, packaged separately via `checkinstall`, installed in parallel. Single Vulkan manifest at `/usr/share/vulkan/implicit_layer.d/vkBasalt.json` serves both archs — `library_path` is the bare soname `libvkbasalt.so`, which the loader resolves per-arch via ld.so.

Detailed recipe in `VKBASALT-SETUP.md`: build steps, dependency cascade (`spirv-headers`, `glslang-dev`, `libvulkan-dev`+`:i386`), the `-m32`-flags 32-bit build (vkBasalt doesn't ship a meson cross-file), checkinstall workflow with the expected manifest-conflict workaround, shader install from `gripped/vkBasalt-working-reshade-shaders`, and the tuned `CRT_Lottes.fx` parameters for HD content (skip the resolution-simulation pass; tune scanline darkness, blur, and mask intensity for readable small text).

## Per-game launch options

- **Arcana Heart 3:** `ENABLE_VKBASALT=1 DXVK_FRAME_RATE=60 %command%` — fighter timing tied to frames; uncapped 144 FPS subtly breaks move windows. Stock Proton 10.0-4 works (no longer needs GE-7-50 once the i386 NVIDIA libs are in place). Also enables vkBasalt to get the CRT filter (see above).

## Display GPU topology

- 3070 Ti = display GPU
- 4090 = eGPU, compute-only (no display attached, not a Vulkan presentation target)
- iGPU disabled in BIOS

The eGPU is not a presentation target, so games render on the internal dGPU regardless of which card is the more powerful. This is why the CRT-filter performance budget is set against the 3070 Ti, not the 4090.
