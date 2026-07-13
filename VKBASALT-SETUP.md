# vkBasalt setup on Linux Mint (Ubuntu jammy base)

Build vkBasalt from source, both 64-bit and 32-bit, package via `checkinstall`,
install a CRT shader, configure for arcade-game aesthetic on HD content.

Running example throughout: **Arcana Heart 3 LOVE MAX SIX STARS!!!!!! XTEND**
(`ArcanaHeart3LMSS`), a 32-bit Windows game running via Proton. The 32-bit build
of vkBasalt is required for this game; many other Steam titles are 64-bit and
only need the amd64 build.

This doc reconstructs the working setup as of 2026-05-09 against:
- Linux Mint (Ubuntu jammy)
- NVIDIA 3070 Ti Laptop GPU (display)
- vkBasalt 0.3.2.10 (built from `master`)

## Why build from source

Ubuntu jammy ships `vkbasalt` 0.3.2.5 in `universe`, **amd64 only**. No i386
package exists in the repos, and no PPA reliably provides one. A 32-bit Vulkan
game cannot load a 64-bit Vulkan layer (the loader requires bitness match), so
for 32-bit titles like AH3 the layer must be built from source for i386.

The cleanest path: build both archs from one source tree, package each with
`checkinstall` so dpkg can manage them later.

## Prerequisites

Build tools and headers for both architectures. The `spirv-headers` and
`glslang-dev` packages are `Architecture: all` — one install serves both.

```bash
# Build system
sudo apt install meson ninja-build glslang-tools checkinstall

# Headers (shared between arches)
sudo apt install spirv-headers glslang-dev

# 64-bit deps
sudo apt install libvulkan-dev libx11-dev

# 32-bit toolchain + deps
sudo apt install gcc-multilib g++-multilib
sudo apt install libvulkan-dev:i386 libx11-dev:i386 libstdc++-12-dev:i386
```

If a previous `vkbasalt` package is installed via apt, remove it first to avoid
file ownership conflicts:

```bash
sudo apt remove vkbasalt
```

## Get the source

```bash
cd ~/Documents/koodit  # or wherever; not /tmp (tmpfs vanishes on reboot)
git clone https://github.com/DadSchoorse/vkBasalt.git
cd vkBasalt
git checkout v0.3.2.10  # or whatever the latest stable tag is; `git tag -l`
```

## Build 64-bit

```bash
meson setup --buildtype=release --prefix=/usr \
            --libdir=lib/x86_64-linux-gnu \
            build64
ninja -C build64
```

Verify the binary before installing:

```bash
file build64/src/libvkbasalt.so
# Expected: ELF 64-bit LSB shared object, x86-64
```

Package and install with `checkinstall`:

```bash
sudo checkinstall -D --pkgname=vkbasalt --pkgversion=0.3.2.10 \
                  --pkgarch=amd64 --provides=vkbasalt \
                  ninja -C build64 install
```

Checkinstall prompts interactively for description etc.; defaults are fine.

## Build 32-bit

The upstream README documents the 32-bit build via `-m32` compiler flags rather
than a meson cross-file. Build directory is independent of `build64`, so no
clean step needed.

```bash
ASFLAGS=--32 CFLAGS=-m32 CXXFLAGS=-m32 \
PKG_CONFIG_PATH=/usr/lib/i386-linux-gnu/pkgconfig \
meson setup --prefix=/usr --buildtype=release \
            --libdir=lib/i386-linux-gnu \
            -Dwith_json=false \
            build32
ninja -C build32
```

Notes on the command:
- `-Dwith_json=false` disables JSON config parsing in the 32-bit build (drops
  the cJSON dependency, which isn't reliably packaged for i386 on Ubuntu).
  Practical impact: 32-bit games read `vkBasalt.conf` (simple `key = value`
  format) but not `vkBasalt.conf.json`. Fine for typical use.
- `-m32` uses the host gcc to emit 32-bit code; not a true cross-compile.
  Requires `gcc-multilib g++-multilib`.

Verify:

```bash
file build32/src/libvkbasalt.so
# Expected: ELF 32-bit LSB shared object, Intel 80386
```

Package and install. Different `pkgname` from the 64-bit so dpkg lets both
coexist:

```bash
sudo checkinstall -D --pkgname=vkbasalt-i386 --pkgversion=0.3.2.10 \
                  --pkgarch=i386 --provides=vkbasalt-i386 \
                  ninja -C build32 install
```

**Expected dpkg conflict**: both packages try to own
`/usr/share/vulkan/implicit_layer.d/vkBasalt.json`. The manifest is identical
between builds (it references the library by bare name `libvkbasalt.so`, which
the Vulkan loader resolves per-arch via ld.so). Resolve with:

```bash
# checkinstall fails on file conflict; install the produced .deb manually
sudo dpkg -i --force-overwrite vkbasalt-i386_0.3.2.10-1_i386.deb
```

(Exact filename varies; `ls *.deb` in the source dir to find it.)

## Verify install

Both libraries should be in their arch-specific paths:

```bash
ls -la /usr/lib/x86_64-linux-gnu/libvkbasalt* /usr/lib/i386-linux-gnu/libvkbasalt*
cat /usr/share/vulkan/implicit_layer.d/vkBasalt.json
# library_path should be the bare name "libvkbasalt.so", not an absolute path
```

Smoke test the 64-bit layer (no config = pass-through, no errors expected):

```bash
ENABLE_VKBASALT=1 vkcube
# Should print: "vkBasalt err: no good config file" (this is fine — means
# the layer loaded but didn't find a config yet)
```

The "err" wording is misleading; it's really "no config, doing nothing." If
the layer didn't load at all you'd see no vkBasalt output whatsoever.

To verify the 32-bit layer loads, install `vulkan-tools:i386` or just test
with the actual game (next section).

## Install CRT shader

Use `gripped/vkBasalt-working-reshade-shaders` — a curated set of ReShade FX
shaders verified to compile under vkBasalt's reshade subset, with all required
include files (`.fxh`) co-located. Skip `crosire/reshade-shaders` (slim or
otherwise); they don't include the CRT shaders we want and have more
compatibility issues.

```bash
cd ~/Documents/koodit
git clone --depth=1 https://github.com/gripped/vkBasalt-working-reshade-shaders.git

mkdir -p ~/.config/reshade
cp -r vkBasalt-working-reshade-shaders/allshaders/reshade-shaders-working/Shaders ~/.config/reshade/
cp -r vkBasalt-working-reshade-shaders/allshaders/reshade-shaders-working/Textures ~/.config/reshade/
```

The relevant CRT shaders are now at `~/.config/reshade/Shaders/`:
- `CRT.fx` — cgwg/Themaister/DOLLS classic, simpler parameter set.
- `CRT_Lottes.fx` — luluco250's port of Timothy Lottes' shader. **This is
  what the tuned config below targets.**
- `CRT_Yee64.fx`, `CRT_Yeetron.fx` — variants, not used here.

## CRT_Lottes.fx tuning

Default `CRT_Lottes.fx` includes a resolution-downscale-then-upscale pass that
makes small text unreadable on HD content (AH3's UI is authored at 1280×720
native, with name plates and stat text in the 12-15px glyph range that doesn't
survive simulation of 540p source).

Edit `~/.config/reshade/Shaders/CRT_Lottes.fx` with these changes:

```c
// Around line 46-48: skip the downscale-upscale roundtrip
#ifndef CRT_LOTTES_DOWNSCALE
#define CRT_LOTTES_DOWNSCALE 0   // was 1
#endif

// Around line 26: no barrel distortion
#define CRT_LOTTES_WARP 0        // was 1

// Around line 70: gentler scanline darkening
> = 0.85;   // fThin: was 0.7

// Around line 78: less horizontal blur
> = 1.8;    // fBlur: was 2.5

// Around line 86: subtler shadow mask
> = 0.7;    // fMask: was 0.5
```

Five edits, and that's the complete set — every other `CRT_LOTTES_*` macro and uniform is at its upstream default (`TONE`, `CONTRAST`, `SATURATION` on; `MASK` = `GRILLE_LITE`; `2TAP`, `CUSTOM_RESOLUTION` off; `SMOOTH_DOWNSCALE` on). The shader records its own originals in trailing comments, so `grep '// ' CRT_Lottes.fx` re-derives this list from the live file if it ever drifts again.

`fDownscale` stays at 2.0 (default). Even with `CRT_LOTTES_DOWNSCALE = 0`,
this still controls scanline pitch — at 1080p output you get 540-line
scanlines (one dark band per 2 output rows), which is the "double-size
scanlines" pattern. The scanline *count* scales with output height
(`output_height / fDownscale`), but the scanline *thickness in physical
millimetres on the panel* is `fDownscale × pixel_pitch` — so on a same-size
panel switched between 1080p and 4K input, scanlines are half as thick at
4K. For matched physical scanline thickness across resolutions, scale
`fDownscale` proportionally: `2.0` at 1080p input, `4.0` at 4K input.

**Curvature is off.** `CRT_LOTTES_WARP` is set to 0, which compiles the barrel
distortion out entirely; the `f2Warp` uniform is then inert and its value
doesn't matter. Warp is the one CRT artifact that a flat panel can only
simulate, not restore — scanlines and shadow mask reconstruct something the
sprite art was authored against, whereas curvature just bends a flat image and
costs edge legibility. To get it back, set the macro to 1 and tune `f2Warp`
from there.

## vkBasalt config

Create `~/.config/vkBasalt/vkBasalt.conf`. Paths must be absolute — vkBasalt's
config parser does not expand `~`, so substitute your own home directory for
`/home/USER` below:

```
effects = crt

reshadeTexturePath = "/home/USER/.config/reshade/Textures"
reshadeIncludePath = "/home/USER/.config/reshade/Shaders"

crt = "/home/USER/.config/reshade/Shaders/CRT_Lottes.fx"

toggleKey = Home
enableOnLaunch = True
```

Smoke test against vkcube — should show a spinning cube with scanlines and
faint chromatic mask (looks weird on 3D content but proves the path):

```bash
ENABLE_VKBASALT=1 vkcube
```

Expected output:
```
vkBasalt info:  config file: vkBasalt.conf
vkBasalt info:  effects = crt
vkBasalt info:  reshadeTexturePath = /home/USER/.config/reshade/Textures
vkBasalt info:  reshadeIncludePath = /home/USER/.config/reshade/Shaders
vkBasalt info:  crt = /home/USER/.config/reshade/Shaders/CRT_Lottes.fx
vkBasalt info:  toggleKey = Home
vkBasalt info:  enableOnLaunch = True
Selected GPU 0: NVIDIA GeForce RTX 3070 Ti Laptop GPU, type: 2
```

## Enable for a Steam game

In Steam, right-click game → Properties → Launch Options:

```
ENABLE_VKBASALT=1 %command%
```

For AH3 specifically:
- Launches `ArcanaHeart3LMSS/AALib.exe` (32-bit, confirmed via `file`)
- Proton spins up a 32-bit Vulkan loader inside the pressure-vessel container
- The container mounts the host's `/usr/share/vulkan/implicit_layer.d/`
- Loader sees the vkBasalt manifest, resolves `libvkbasalt.so` to the i386
  build, applies the shader
- `Home` key toggles vkBasalt on/off in-game

## Per-display-config notes

**Match game render resolution to display input resolution where possible.**
The CRT_Lottes shader produces sharp scanline transitions (steep Gaussian
falloff). When the panel's built-in scaler resamples the image — typical
when running games below panel native, e.g. 1080p game shown on a 4K panel
set to 1080p input — those transitions get softened. The softening is
bearable for gaming use; the panel's scaler is fine for moving images even
when it's "horribly blurry for desktop productivity," and the CRT effect
still dominates. Most gaming on this machine runs this way: 4K external display
switched to 1080p input mode, game rendered at 1080p, accepting display-side
upscaling rather than asking the 3070 Ti to drive 4K natively.

**Pathological case (avoid):** rendering *above* panel native and letting the
desktop compositor downsample. Pays GPU cost AND smooths exactly the
high-frequency scanline detail the shader generates. Only an issue if doing
DSR/VSR or similar render-above-native tricks. (Native screenshot capture
to a higher-res buffer for further processing is the relevant exception —
see notes on the screenshot workflow below.)

**Scanline pitch tracks output_height.** When switching display input
resolution (e.g. between 1080p and 4K modes), the shader's
`output_height / fDownscale` math adapts the scanline count automatically,
but on the same physical panel this means the scanlines change apparent
thickness — half as thick at 4K input as at 1080p input with the same
`fDownscale` value. Scale `fDownscale` proportionally if you want the same
look across modes (`2.0` at 1080p, `4.0` at 4K).

**Screenshot capture caveat.** Capturing at 4K and downsampling to 1080p
(e.g. in GIMP for sharing) blurs the scanline transitions because the
downsample kernel averages over neighbouring rows. Native-resolution
capture preserves the shader's intended sharpness. Use captures at the
actual display input resolution as the reference for "what the shader
looks like."

## Gotchas observed during initial setup

1. **Ubuntu package `libvkbasalt32` does not exist** despite seeming
   plausible. The only apt-shipped package is `vkbasalt` (amd64 only).
   This is why we build i386 from source.

2. **No meson cross-file in the vkBasalt repo.** The 32-bit build uses
   `-m32` compiler flags instead (`--cross-file build32.txt` would fail —
   no such file exists in the source tree). See the 32-bit build section
   above.

3. **Header packages can be non-obvious.** Build failures progress through
   `spirv-headers` → `glslang-dev` → `libvulkan-dev` as missing. All three
   are needed before the build can complete; install all up front.

4. **`checkinstall` produces empty package if `ninja install` has nothing
   to write.** If you already ran `ninja install` directly before discovering
   checkinstall exists, `rm -rf build64 && meson setup ... build64 && ninja`
   to get a fresh build state, then run checkinstall on the install step.

5. **Manifest file conflict between vkbasalt and vkbasalt-i386 packages**
   is expected; resolve with `dpkg -i --force-overwrite` as documented above.

## Notes for future installs

The build recipe above should work unchanged against any reasonably recent
Ubuntu/Mint release. Verify:

- `apt show vkbasalt` — confirm still amd64-only; if i386 becomes available
  upstream, prefer `apt install vkbasalt:i386` over building from source
- The vkBasalt repo has had occasional API changes; check
  `git log --since=<previous-build-date>` for anything that affects the
  build commands

The shader config (`~/.config/reshade/`, `~/.config/vkBasalt/`) is per-user
and survives OS reinstall if `/home` is preserved. The tuned `CRT_Lottes.fx`
parameters are the load-bearing customization; everything else can be
regenerated from the gripped repo.

## References

- vkBasalt: https://github.com/DadSchoorse/vkBasalt
- Working shader set: https://github.com/gripped/vkBasalt-working-reshade-shaders
- luluco250's FXShaders (upstream of CRT_Lottes.fx): https://github.com/luluco250/FXShaders
- ReShade FX language reference: https://github.com/crosire/reshade
