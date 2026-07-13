# New Machine Setup Notes

Based on setting up `electra` (2026-03-25). Assumes Ubuntu/Debian-based Linux.

## System packages

```bash
# Essentials
# jq: needed by ~/.claude/statusline.sh
# xclip: needed by ~/.claude/scripts/build-webchat.py (degrades gracefully without it)
sudo apt install git wget jq xclip ripgrep graphviz libturbojpeg0-dev espeak-ng

# Python tooling
sudo apt install python3-pip pipx

# Deadsnakes PPA (multiple Python versions)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev
sudo apt install python3.11 python3.11-venv python3.11-dev
sudo apt install python3.12 python3.12-venv python3.12-dev
sudo apt install python3.13 python3.13-venv python3.13-dev
sudo apt install python3.14 python3.14-venv python3.14-dev

# SSH
sudo apt install openssh-server
sudo systemctl enable --now ssh
ssh-keygen -t ed25519

# Spellchecking
sudo apt install hunspell-en-us hunspell-en-gb
sudo apt install libenchant-2-voikko libvoikko1 voikko-fi

# WordNet (for Spacemacs define-word)
sudo apt install wordnet wordnet-base

# GitHub CLI — see https://cli.github.com/packages if these instructions become stale
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
gh auth login
gh auth refresh -h github.com -s workflow  # needed to merge PRs that touch .github/workflows/

# TeX Live (full install, ~4 GB download, ~7.5 GB on disk)
sudo apt install texlive-full

# OpenShot video editor — download from https://www.openshot.org/
# (not in Ubuntu repos; symlink the AppImage to ~/.local/bin/openshot)

# FFmpeg 7 (needed by Raven-server audio encoder; current for Ubuntu 22.04 and 24.04)
sudo add-apt-repository ppa:ubuntuhandbook1/ffmpeg7
sudo apt update
sudo apt install ffmpeg

# Webcam testing
sudo apt install cheese gnome-video-effects-frei0r gnome-video-effects-extra

# Meson + Ninja (build system for numerical Cython projects: pylu, pydgq, python-wlsqm)
sudo apt install meson ninja-build
```

## Input methods

```bash
# Math (LaTeX-style input, e.g. \gamma → γ, \partial → ∂)
sudo apt install ibus ibus-table ibus-table-latex

# Japanese (Mozc)
sudo apt install ibus-mozc

# Restart IBus after install
ibus restart
```

Then open IBus Preferences → Input Methods, add "LaTeX" (under ibus-table) and "Japanese - Mozc". Switch between input methods with the configured hotkey (check IBus Preferences → General).

No environment variable setup needed on Mint/Cinnamon (GTK_IM_MODULE etc. are not required).

### Keybindings

- IBus Preferences → General: set "Next input method" to Ctrl+Shift+Space.
- ibus-table-latex has an annoying default of toggling on/off at Left Shift. Remap this to Right Shift in its settings (IBus Preferences → Input Methods → LaTeX → Preferences).

## Desktop environment tweaks

- **Systray calendar (Cinnamon):** Set start of week to Monday (not the default Sunday). Right-click the clock → Settings.

## Python tooling (user-level)

```bash
# PDM (project manager)
pipx install pdm

# pyan3 (static call graph generator)
pipx install pyan3

# PyPI publishing
pipx install build
pipx install twine

# Global macro-enabled IPython (on latest Python)
pipx install ipython --python python3.14
pipx inject ipython mcpyrate

# Global macropython (one per Python version, with version suffix)
pipx install mcpyrate --python python3.10 --suffix 3.10
pipx install mcpyrate --python python3.11 --suffix 3.11
pipx install mcpyrate --python python3.12 --suffix 3.12
pipx install mcpyrate --python python3.13 --suffix 3.13
pipx install mcpyrate --python python3.14 --suffix 3.14

# Editor tools fallback venv (for projects without their own venv)
python3.14 -m venv ~/.local/venvs/editor-tools
~/.local/venvs/editor-tools/bin/python -m pip install flake8 autopep8 importmagic epc
```

### IPython config for mcpyrate

```bash
ipython profile create
```

Add to `~/.ipython/profile_default/ipython_config.py`:

```python
c.InteractiveShellApp.extensions = ["mcpyrate.repl.iconsole"]
```

(`autocall` defaults to 0 in modern IPython, no need to set it.)

## Node.js (nvm)

Node/npm/npx are managed entirely in userspace via nvm (Node Version Manager) — never via apt or a NodeSource repo. nvm clones itself into `~/.nvm` (a git checkout) and appends a load block to `~/.bashrc`. npm and npx come bundled inside each Node install; they are never installed or upgraded separately — a new Node gives you matching npm/npx for free.

```bash
# Bootstrap nvm — pin the tag, don't curl-pipe an unpinned/master URL.
# Check https://github.com/nvm-sh/nvm/releases for the current version if this is stale.
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash

# Restart the shell, or source the block the installer just appended to ~/.bashrc
source ~/.bashrc

# Node LTS + bundled npm/npx
nvm install --lts
nvm alias default 'lts/*'
```

Verify:

```bash
node --version    # v24.x (current LTS line) or newer
npm --version
npx --version
nvm --version
command -v nvm     # "nvm is a function" — it's a shell function, not a binary on PATH
```

Security note: `curl | bash` runs whatever is at that URL. Pinning the tag (`v0.40.4`, not `master`) gives a fixed artifact you can eyeball with a plain `curl` before piping. Normal tradeoff for a personal dev box — do *not* paste the unpinned form onto a server.

The load block nvm writes to `~/.bashrc` (this is the diagnostic that nvm owns your Node):

```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
```

This is sourced by interactive shells only — so **GUI apps launched outside an interactive shell don't see nvm's node/npx on PATH**. Bites anything that spawns an MCP server or build tool from a desktop-launched app (see LM Studio below). nvm itself rarely needs upgrading; re-run the bootstrap with a newer tag to bump it. The literal original install command tends to age out of `~/.bash_history` — don't bother trying to recover it, the recipe above reproduces the same end state.

### LM Studio MCP servers

`mcp.json` lives at `~/.lmstudio/mcp.json` (LM Studio follows Cursor's notation: a top-level `mcpServers` object). LM Studio spawns one process per server; for npx-based local servers, npx must be on the *spawned* process's PATH — which, per the nvm gotcha above, it isn't when LM Studio is launched from the desktop. The login-shell wrapper (`bash -lc`) re-sources the profile so npx resolves, and survives Node upgrades (no hardcoded version directory). Confirmed working on `maia`:

```json
{
  "mcpServers": {
    "open-meteo": {
      "command": "bash",
      "args": ["-lc", "npx -y -p open-meteo-mcp-server open-meteo-mcp-server"]
    }
  }
}
```

Why `-lc` works on Ubuntu: a login shell sources `~/.profile`, and Ubuntu's stock `~/.profile` in turn sources `~/.bashrc` when running under bash — so the nvm block (which the installer wrote to `.bashrc`) gets loaded. On a setup *without* that `.profile`→`.bashrc` bridge, npx won't resolve; use `-ic` (interactive, sources `.bashrc` directly) or add an explicit `source ~/.bashrc` to `.profile`.

Notes on the npx invocation, for future debugging:
- First launch is slow — npx fetches `open-meteo-mcp-server` from the registry into `~/.npm/_npx/` (a content-hash-keyed cache) and runs the binary from there. Subsequent launches hit the cache.
- `-y` auto-approves the install so the non-interactive spawned process doesn't hang on a prompt.
- `-p X X` is `--package` (what to fetch) + the trailing command (what to run); they collide on the same name here, so a bare `npx -y open-meteo-mcp-server` would resolve identically. The explicit form is the README author's.
- Cache reuse means you don't pull fresh arbitrary code every launch (good) but also don't auto-get upstream security fixes until the cache entry clears (less good). For a pinned, controlled artifact: `npm install -g open-meteo-mcp-server@<version>` and point `command` at the installed binary instead.
- Tools appear under the Program tab, gated behind LM Studio's per-call confirmation dialog. If they don't appear after saving `mcp.json`, check LM Studio's logs for a spawn/ENOENT error on npx — that's the PATH problem, meaning the `-lc` bridge above didn't fire.

## Spacemacs

```bash
git clone https://github.com/syl20bnr/spacemacs ~/.emacs.d
git clone git@github.com:Technologicat/spacemacs.d.git ~/.spacemacs.d
```

### Key init.el settings

- Python layer: `(python :variables python-auto-set-local-pyvenv-virtualenv 'on-visit)`
- `python-shell-interpreter`: `"python"` (not `"ipython3"`)
- `python-shell-interpreter-args`: `"-i"`
- `flycheck-python-flake8-executable`: `"~/.local/venvs/editor-tools/bin/flake8"` (fallback; Spacemacs overrides with project venv when available)
- `importmagic-python-interpreter`: `"~/.local/venvs/editor-tools/bin/python"`
- `default` face `:background`: use `unspecified` (not `nil` — causes warning on Emacs 29.3)
- Remove `pt` from `dotspacemacs-search-tools` (dropped by Spacemacs)

### Config files (symlinks)

```bash
# flake8 config chain: pep8 → flake8 → actual file in .spacemacs.d
ln -s ~/.spacemacs.d/flake8 ~/.config/flake8
ln -s ~/.config/flake8 ~/.config/pep8
```

### Wiktionary dictionary

Copy `~/.spacemacs.d/dictionaries_enwiktionary/` from old machine (Matthias Buchmeier's Wiktionary extraction, dictd format). Update from `http://en.wiktionary.org/wiki/User:Matthias_Buchmeier` if desired.

### Fonts

Copy `~/.fonts/` from old machine. Run `fc-cache -fv` after.

## Claude Code

`~/.claude/` is a git repo (`Technologicat/dotclaude`), so the config comes down with a clone rather than a copy:

```bash
git clone git@github.com:Technologicat/dotclaude.git ~/.claude
```

Then hand-carry the two gitignored private files from the old machine over a trusted channel — the repo is public, so they are deliberately not in it:

- `SECRET-SAUCE.md` — private `CLAUDE.md` fragment, imported via `@./SECRET-SAUCE.md`
- `HARDWARE-NOTES.md` — GPU models, torch device ordering, benchmarks

Both are optional: Claude Code ignores a missing `@import`, and nothing else reads them at startup. See the repo's `README.md` for the full deployment story.

Runtime state (`projects/`, `sessions/`, `memory/`, caches) is machine-local by design and is *not* synced — auto-memory accumulates per machine.

The statusline script requires `jq`; `scripts/build-webchat.py` uses `xclip`. Both are in the Essentials block above.

### Kitty terminal workaround

Claude Code may leave the terminal in raw mode on exit. Add to `~/.bashrc`:

```bash
alias claude='command claude; reset'
```

## Project setup (all projects)

Each project needs editor tooling in dev dependencies so Spacemacs finds them via auto-activated pyvenv. Standard dev deps block:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "flake8",
    "autopep8",
    "importmagic",
    "epc",
    "jedi>=0.19.2",
]
```

### Raven-specific

```bash
cd ~/Documents/koodit/raven
pdm use python3.12
pdm install -G cuda
```

- `requires-python` narrowed to `<3.13` due to kokoro/misaki TTS dependency
- After activating the venv, `source env.sh` to set up CUDA library paths (LD_LIBRARY_PATH, ptxas). The script auto-discovers all pip-installed NVIDIA lib dirs — works with CUDA 12 and 13.

## NVIDIA driver

Use the **graphics-drivers PPA**, on every machine:

```bash
sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt update
sudo apt install nvidia-driver-XXX  # XXX = current version per repo README
sudo reboot
```

Reboot is needed so the kernel module matches userspace.

**Not the CUDA repo.** The obvious path for an AI workstation is the CUDA repo (`gpu22.04.1` packages and similar). It works for compute, but **omits `libnvidia-gl-XXX:i386`** — every other NVIDIA lib (compute, decode, encode, fbc1) ships both arches; GL is the orphan. Nothing complains at install time. The breakage surfaces only when 32-bit code touches the GPU, at which point Vulkan silently falls back to llvmpipe (software rendering) and OpenGL apps black-screen.

The PPA has no compensating downside: it ships `libnvidia-gl-XXX` for both `amd64` and `i386`, and the CUDA toolkit stays compatible either way — NVIDIA's user-mode driver is forward-compatible, so anything built against an older CUDA runtime runs fine against a newer driver. So there's nothing to trade off and no decision to make: take the PPA and keep the i386 libs, whether or not this machine will ever run 32-bit GL code.

(The consumers of those i386 libs are Steam, Proton, and pre-2020-ish Linux/Wine games — see `GAMING-SETUP.md`. But the point of installing from the PPA unconditionally is precisely that you don't have to predict that in advance.)

Verify:

```bash
nvidia-smi                                       # driver loaded, GPUs visible
ls /usr/lib/i386-linux-gnu/libGLX_nvidia*        # i386 lib present
vulkaninfo --summary | grep -E 'deviceName'      # NVIDIA on its line, not just llvmpipe
```

The Vulkan ICD manifest at `/usr/share/vulkan/icd.d/nvidia_icd.json` uses a bare soname (`libGLX_nvidia.so.0`), not an absolute path — so a single manifest covers both arches as long as the i386 library is on disk. No separate `nvidia_icd.i686.json` is needed; absence of one is not the diagnostic.

Take a Timeshift snapshot before any driver-stack swap. NVIDIA's userspace + kernel module + DKMS state can end up in inconsistent states even when apt is happy, and a black-screen X server is much faster to recover from a snapshot than from a TTY.

## Hardware

- Check NVIDIA drivers: `nvidia-smi`
- Check CUDA version: `nvidia-smi` (top right)
- List GPUs: `nvidia-smi -L`
- Torch device ordering: eGPU is `cuda:0`, internal dGPU is `cuda:1`. Without eGPU, internal is `cuda:0`.
- Note: GPU model alone may be ambiguous (e.g. both internal and eGPU could be 4090s with different VRAM). Use `nvidia-smi -L` to distinguish.

## Gaming

Not part of baseline setup. If this machine games, see `GAMING-SETUP.md` (Steam/Proton, the Input Remapper phantom-gamepad udev rule, vkBasalt CRT post-processing, per-game launch options) and `VKBASALT-SETUP.md` for the vkBasalt build recipe. Apply only when separately requested.

The one thing baseline setup must get right for gaming's sake is the NVIDIA driver source — see above; the graphics-drivers PPA is the unconditional choice.
