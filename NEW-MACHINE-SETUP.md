# New Machine Setup Notes

Based on setting up a new dev machine (2026-03-25). Assumes Ubuntu/Debian-based Linux.

## System packages

```bash
# Essentials
# jq: needed by ~/.claude/statusline.sh
# xclip: needed by ~/.claude/scripts/build-webchat.py (degrades gracefully without it)
# wmctrl: needed by ~/.claude/scripts/em (raises the Emacs window after opening a file)
# xdotool: drives a GUI app from the shell - activate a window, inject keystrokes. With xclip, this
#          is how a GUI feature gets verified end-to-end (press the hotkey, read the clipboard back)
#          rather than only through unit tests. Needed for live testing of the DPG apps in Raven.
# ripgrep: `rg`, the first choice in Spacemacs's `dotspacemacs-search-tools` (falls back to ag/pt/ack/grep).
# shellcheck: linter for the bash scripts in ~/.claude/scripts/. Bash fails quietly - an unquoted
#          expansion or a typo'd variable produces a wrong result rather than an error - so a linter
#          catches things a test run does not.
# tesseract-ocr: reads text out of a screenshot, for live GUI testing. An agent checking one status
#          line - "Will pick: /some/path" - can crop it and OCR it instead of reading the whole
#          screenshot, which costs a couple of thousand tokens against about fifty. Treat it as a fast
#          check rather than as ground truth: small text on a dark theme misreads often enough that a
#          surprising answer is a reason to look at the image, not to believe the OCR.
# gifsicle: the last step of turning a screen capture into a GIF for a README (live-gui-testing skill,
#          "Capturing motion"). `--lossy=30` took a 2.9 MB capture of a GUI animation to 1.9 MB with no
#          visible difference, which matters because GitHub will not play a repo-relative video.
# pandoc: document conversion both ways — reading an .odt/.docx into plain text an agent can use, and
#          exporting a Markdown draft (e.g. a monthly activity report) to .odt/.docx for email.
# zbar-tools: `zbarimg file.png` decodes a QR code or barcode from an image, for checking that an
#          exported code (e.g. `python -m raven.common.gui.qroverlay out.png`) scans before it is
#          sent on. Reads PNG and SVG alike. For manual use; nothing tests against it.
# libimage-exiftool-perl: `exiftool`, the reference reader for image metadata (EXIF, IPTC, XMP).
#          chandra's test suite checks with it that the XMP chandra writes reads back as the standard
#          IPTC properties, and skips that test where exiftool is absent.
# kitty: the terminal Claude Code runs in, on every machine. Installing it also provides the
#          `xterm-kitty` terminfo, which a host needs before anyone can SSH into it from Kitty
#          (the alternative is `kitten ssh`, which carries the terminfo along).
# htop, nvtop: process and GPU monitors. nvtop ("Neat Videocard TOP") covers AMD and Intel GPUs as
#          well as NVIDIA, so it is the GPU monitor on every machine.
# nethogs: network bandwidth per process, top-style. Needs root: `sudo nethogs <interface>`.
# powertop: wakeups and CPU usage per process, plus power tunables. Needs root. On AMD it shows no
#          wattage, but the events/s view still finds what keeps a machine from idling.
sudo apt install git wget jq xclip xdotool wmctrl ripgrep graphviz libturbojpeg0-dev espeak-ng shellcheck tesseract-ocr gifsicle pandoc zbar-tools libimage-exiftool-perl kitty htop nvtop nethogs powertop

# Python tooling
sudo apt install python3-pip pipx

# OOM: earlyoom. These machines run without swap, and even so the kernel can thrash before its
# OOM killer fires: under memory pressure it evicts file-backed pages (code included) and keeps
# re-reading them, so the desktop freezes for minutes rather than a process being killed.
# earlyoom kills the largest process early instead. Mint does not run systemd-oomd (inactive on a
# fresh 22.3 install), so nothing else covers this.
# Remove the installer's swapfile too: `sudo swapoff /swapfile`, delete its line in /etc/fstab,
# then `sudo rm /swapfile`.
sudo apt install earlyoom
# Then replace its default threshold. That default is SIGTERM at <= 10% available memory and
# SIGKILL at <= 5%. With no swap the swap condition always holds, so memory alone decides, and a
# local LLM that legitimately leaves ~6% free (a large model on the work machine, or GPU memory
# on the AI server) would be killed as soon as it loads. Use absolute sizes instead: SIGTERM at
# 2 GiB, SIGKILL at 1 GiB. `-M` replaces the percentage default rather than adding to it.
sudo sed -i 's/^EARLYOOM_ARGS=.*/EARLYOOM_ARGS="-r 3600 -M 2097152,1048576"/' /etc/default/earlyoom
sudo systemctl restart earlyoom
journalctl -u earlyoom -n 3 --no-pager   # check the "sending SIGTERM when mem <= ..." line

# Deadsnakes PPA (multiple Python versions)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev
sudo apt install python3.11 python3.11-venv python3.11-dev
sudo apt install python3.12 python3.12-venv python3.12-dev
sudo apt install python3.13 python3.13-venv python3.13-dev
sudo apt install python3.14 python3.14-venv python3.14-dev
sudo apt install python3.15 python3.15-venv python3.15-dev

# PyPy — deadsnakes does NOT package it, and Ubuntu universe ships only 7.3.9 (Python 3.9),
# which is four years stale. Use the official portable tarball. Current stable is 7.3.23,
# which implements Python 3.11 and nothing else; 3.12 exists only as a nightly.
# Pick the current URL from https://downloads.python.org/pypy/versions.json
curl -LO https://downloads.python.org/pypy/pypy3.11-v7.3.23-linux64.tar.gz
# Upstream publishes no checksum for this release — pypy.org/checksums.html has no 7.3.23
# entry and there is no .sha256 sidecar — so the only assurance is HTTPS from the official
# host. What we can do is make both machines agree; this is what the file hashed to here:
#   sha256  2bcab031cef7a37fe1930b51f7091e78a191ae63f80eca00a265d3378c3a645b
sha256sum pypy3.11-v7.3.23-linux64.tar.gz
tar -xzf pypy3.11-v7.3.23-linux64.tar.gz -C ~/.local/bin/   # matches how 7.3.9 was installed
~/.local/bin/pypy3.11-v7.3.23-linux64/bin/pypy3 -m ensurepip
ln -sfn pypy3.11-v7.3.23-linux64/bin/pypy3.11 ~/.local/bin/pypy3.11
ln -sfn pypy3.11-v7.3.23-linux64/bin/pypy3.11 ~/.local/bin/pypy   # bare `pypy` = current stable
# `pypy -m venv <dir>` then works like any other interpreter. Needed for the PyPy CI jobs in
# mcpyrate and unpythonic, and for checking whether a project can take PyPy at all — note that
# PyPy has no `_symtable`, so anything importing the stdlib `symtable` cannot run on it (this
# is what rules out pyan).

# SSH
sudo apt install openssh-server
sudo systemctl enable --now ssh
ssh-keygen -t ed25519

# Spellchecking
sudo apt install hunspell-en-us hunspell-en-gb
sudo apt install libenchant-2-voikko libvoikko1 voikko-fi
# Spacemacs's config (`~/.spacemacs.d/config.el`) runs ispell/flyspell through ~/.local/bin/enchant,
# so link the enchant-2 binaries there under their unversioned names. Without these, flyspell fails
# at startup with "Searching for program No such file or directory ~/.local/bin/enchant".
ln -s /usr/bin/enchant-2 ~/.local/bin/enchant
ln -s /usr/bin/enchant-lsmod-2 ~/.local/bin/enchant-lsmod

# WordNet (for Spacemacs define-word)
sudo apt install wordnet wordnet-base

# GitHub CLI — see https://github.com/cli/cli/blob/trunk/docs/install_linux.md if these instructions become stale.
# That page lists the signing-key fingerprints; check them against `gpg --show-keys` on the downloaded keyring.
# The signing key has an expiry date (the 2022 one expired on 2026-09-05), and `apt update` then fails with EXPKEYSIG:
# re-download the keyring with the first three lines below, and the sources list can stay as it is.
sudo mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
gh auth login
gh auth refresh -h github.com -s workflow  # needed to merge PRs that touch .github/workflows/

# TeX Live (full install, ~4 GB download, ~7.5 GB on disk)
sudo apt install texlive-full

# Zotero reference manager — not in Ubuntu repos. Get the current Linux tarball from
# https://www.zotero.org/download/ (the direct link is a redirect:
# https://www.zotero.org/download/client/dl?channel=release&platform=linux-x86_64).
# Upstream publishes no checksum, so the only assurance is HTTPS from the official host;
# what we can do is make both machines agree. Zotero 10.0 hashed to this here:
#   sha256  fad10b2bee0b6178248a0ffb7b4add0bc2b1e71088f47d5549423e1cc80034b8
tar -xJf ~/Downloads/Zotero-10.0_linux-x86_64.tar.xz -C ~/.local/bin/   # as with PyPy above
ln -sfn Zotero_linux-x86_64/zotero ~/.local/bin/zotero
# The extracted directory is named `Zotero_linux-x86_64` with no version in it, and Zotero
# updates itself in place (it ships Mozilla's `updater`), so the symlink is written once and
# never revised — a later tarball extracted the same way lands on top of the same directory.
#
# Desktop entry: set_launcher_icon rewrites Icon= in zotero.desktop to an absolute path.
~/.local/bin/Zotero_linux-x86_64/set_launcher_icon
ln -sfn ~/.local/bin/Zotero_linux-x86_64/zotero.desktop ~/.local/share/applications/zotero.desktop
# Symlink rather than copy: the Exec= line finds the app directory from the desktop file's own
# location (%k → realpath → dirname), so a copy would look for `zotero` beside the copy.
# Upstream notes that some updates need set_launcher_icon re-run.
# `desktop-file-validate` rejects that Exec= line (unescaped `$` inside quotes — a real spec
# violation upstream). The launcher works anyway, so leave the file alone; the three errors
# are not a symptom of anything.
#
# First run does the rest of the setup by prompting: it offers the LibreOffice integration
# (accept), and opens a page for the browser connector (installed into Chromium here). The
# account is connected afterwards from Settings → Account in the app.

# OpenShot video editor — download from https://www.openshot.org/
# (not in Ubuntu repos; symlink the AppImage to ~/.local/bin/openshot)

# GIMP and Inkscape — image editors, and between them what opens the art originals a
# project keeps beside what it ships: Raven's `00_workfiles/` directories hold the .xcf and
# .svg files its icons and character assets were exported from, and those are excluded from
# the wheel, so they are editable only from a checkout.
sudo apt install gimp inkscape

# pix — image viewer for a whole folder, side by side. (xviewer, for a single image, ships
# with Mint Cinnamon and needs no install.) Both are named in ~/.claude/CLAUDE.md as the way
# an agent hands an image back, so a machine without them cannot follow those instructions.
sudo apt install pix

# FFmpeg 7 (needed by Raven-server audio encoder; current for Ubuntu 22.04 and 24.04)
sudo add-apt-repository ppa:ubuntuhandbook1/ffmpeg7
sudo apt update
sudo apt install ffmpeg

# Webcam testing
sudo apt install cheese gnome-video-effects-frei0r gnome-video-effects-extra

# Meson + Ninja (build system for numerical Cython projects: pylu, pydgq, python-wlsqm)
sudo apt install meson ninja-build
```

## Filesystem (ext4 root on an SSD)

Two changes to the installer's defaults:

- **Reserved blocks: 1% instead of 5%.** ext4 reserves 5% for root by default, which on a 2 TB disk is
  ~100 GB held back. 1% is plenty on a modern disk.
- **`noatime`** instead of the default `relatime`, so that reading a file never causes a write.

```bash
ROOTDEV=$(findmnt -no SOURCE /)
sudo tune2fs -l "$ROOTDEV" | grep -i 'reserved block count'   # before
sudo tune2fs -m 1 "$ROOTDEV"
# In /etc/fstab, add noatime to the root line's options: errors=remount-ro → noatime,errors=remount-ro
sudo mount -o remount /
findmnt -no OPTIONS /                                          # expect noatime
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

### Do not set the IM environment variables by hand

No environment variable setup is needed on Mint/Cinnamon, and doing it anyway **silently disables IBus autostart**. Keep `GTK_IM_MODULE`, `QT_IM_MODULE` and `XMODIFIERS` out of `~/.profile`, `~/.bashrc`, `~/.xprofile` and everything else in the login path. This matters because exporting exactly these three is the standard internet advice for "my input method isn't working", so it is the first thing one reaches for — and here it is the cause.

The mechanism: `/etc/X11/Xsession.d/70im-config_launch` skips its phase 1 when any of those variables is already set, on the reasoning that the user configured the IM by hand and it should keep out of the way. Skipping phase 1 leaves `IM_CONFIG_PHASE` unset, so `im-launch` also skips phase 2 — and phase 2 is what runs `ibus-daemon --daemonize --xim`. The session comes up with no daemon at all: no tray icon, no switcher hotkey, no input methods. LightDM sources `~/.profile` before Xsession runs, so the variables are already in the environment by the time the hook looks.

Tell-tales, when the input methods are missing:

- `pgrep ibus` returns nothing, while `env | grep IM_MODULE` looks perfectly correct. Nothing errors and nothing is logged, which is what makes this hard to spot.
- `CLUTTER_IM_MODULE` is absent. im-config sets all four variables, so having exactly the three that a hand-written `export` block sets is the fingerprint that phase 1 never ran.

Starting `ibus-daemon --daemonize --xim` by hand confirms the diagnosis and fixes the running session; removing the exports fixes it permanently, from the next login on. Applications only connect to IBus at startup, so anything launched before the daemon needs restarting.

### Cinnamon's own input-source switching is not used

Cinnamon has a native input-source mechanism — the list in `org.cinnamon.desktop.input-sources`, surfaced by the `keyboard@cinnamon.org` applet. Getting it working proved difficult enough to abandon (April 2026), so the setup above uses IBus's own machinery end to end: the tray icon is IBus's panel `ibus-ui-gtk3`, which Cinnamon merely embeds as a status icon (see the `'ibus-ui-gtk': 'input-method'` mapping in its `statusIconDispatcher.js`), and the switcher hotkey is IBus's own, in `org.freedesktop.ibus.general.hotkey`.

So `org.cinnamon.desktop.input-sources sources` holding an empty list is the expected state here, not a fault to repair. It looks like an obvious culprit when the input methods are missing, which makes populating it an attractive wrong turn — check whether `ibus-daemon` is running before touching it. IBus keeps its own engine list in `org.freedesktop.ibus.general preload-engines`, and that is the one that matters.

Worth re-testing after a major OS upgrade. This arrangement was settled against one particular Mint/Cinnamon/IBus combination, and a newer Cinnamon may well make the native route work — in which case the machines can converge on it rather than each keeping its own workaround.

### Keybindings

- IBus Preferences → General: set "Next input method" to Ctrl+Shift+Space.
- ibus-table-latex has an annoying default of toggling on/off at Left Shift. Remap this to Right Shift in its settings (IBus Preferences → Input Methods → LaTeX → Preferences).

## Desktop environment tweaks

- **Systray calendar (Cinnamon):** Set start of week to Monday (not the default Sunday). Right-click the clock → Settings.

### CPU temperature in the system monitor applet

The panel applet `multicore-sys-monitor@ccadeptic23` reads the CPU temperature from one literal file
path: Configure → "Path to the system file used to check the CPU temperature". Its default,
`/sys/class/thermal/thermal_zone1/temp`, is not the CPU on any of these machines. The file holds
thousandths of a degree Celsius.

Where the CPU sensor lives differs by vendor, and on neither is its path stable:

- **Intel:** the thermal zone of type `x86_pkg_temp`, the CPU package sensor. Its zone number differs
  per machine (6 on one laptop, 8 on the other).
- **AMD:** there may be no thermal zones at all, since they come from the ACPI firmware, and the AI
  server's BIOS exposes none. The CPU sensor is the `k10temp` driver's `temp1_input` (label `Tctl`)
  under `/sys/class/hwmon/`, and the hwmon index depends on the order the drivers load in.

The applet takes no glob, so a udev rule links whichever sensor exists to `/run/cpu-temp` each time
its driver registers. One rules file serves every machine, because only the line that matches fires:

```bash
sudo tee /etc/udev/rules.d/90-cpu-temp-symlink.rules >/dev/null <<'EOF'
# Link the CPU temperature sensor to /run/cpu-temp, for the panel applet. Only one line matches per machine.
ACTION=="add", SUBSYSTEM=="thermal", ATTR{type}=="x86_pkg_temp", RUN+="/bin/ln -sfn /sys%p/temp /run/cpu-temp"
ACTION=="add", SUBSYSTEM=="hwmon", ATTR{name}=="k10temp", RUN+="/bin/ln -sfn /sys%p/temp1_input /run/cpu-temp"
EOF
# Create the link now; at boot it happens by itself. Intel:
sudo udevadm trigger --action=add -s thermal --attr-match=type=x86_pkg_temp
# AMD:
sudo udevadm trigger --action=add -s hwmon --attr-match=name=k10temp
cat /run/cpu-temp
```

Then point the applet at `/run/cpu-temp`. Note the `--action=add`: `udevadm trigger` sends `change`
events by default, which these rules do not match, so without it the link silently fails to appear.

## Home LAN name resolution

On the home LAN, machines reach each other by bare hostname (`ssh hostname`), served by the router's DNS.
Set up 2026-11-14. The pattern works on any router that can do DHCP reservations with hostnames; only the
menu locations differ (on the current ASUS router: LAN → DHCP Server):

- **Domain name** `home.arpa` (RFC 8375). Not `.local`, which belongs to mDNS.
- **Manual assignment** enabled: a fixed IP plus a hostname for each machine, keyed by its Wi-Fi MAC.
- **Router DNS fields** left empty, and "advertise router's IP" on, so that clients use the router as their
  DNS server and it answers for the names.

mDNS (`hostname.local`, via Avahi) keeps working alongside this.

**Adding a machine:** add a reservation, taking the MAC from the router's client list. If NetworkManager
randomizes the MAC for that network, the reservation will not match, so switch that off for the home
network. Reconnect, then check with `getent hosts <name>`.

**Replacing a machine:** update or delete its old entry. A stale MAC still holding a name or an IP
misroutes silently.

**Replacing the router:** redo the above. The old router's config backup is in the rolling backup, for
reference.

## Core dumps

`systemd-coredump` saves every segfault with no preparation, which is why chasing one starts with reading
the core rather than trying to reproduce it. The defaults are too small for the processes worth reading,
though, and a core over the cap is written **truncated** — which is not an error and does not say so. It
looks like an ordinary core until gdb resolves every frame to `??`.

Raise both caps (needs root):

```bash
sudo mkdir -p /etc/systemd/coredump.conf.d
sudo tee /etc/systemd/coredump.conf.d/50-bigger-cores.conf >/dev/null <<'EOF'
[Coredump]
ProcessSizeMax=8G
ExternalSizeMax=8G
EOF
sudo systemctl daemon-reexec
```

A drop-in rather than an edit to `/etc/systemd/coredump.conf`, so a distribution upgrade replacing that
file cannot silently take the setting with it.

**Why 8G.** The default is 2G, and Raven's test suite peaks at **2.43 GiB** without its ML group and
**5.63 GiB** with it — the `ml` tests load Whisper, Kokoro, spaCy, Flair, transformers and
sentence-transformers in-process, all resident at once. Note RSS is not quite what the cap measures, since
a core omits file-backed pages and most of that first figure is shared objects; but the margin is thin
enough at 2G that the narrow case only fits by luck.

Storage is bounded separately by `MaxUse` (unset → 10% of the filesystem), cores are zstd-compressed, and
`/var/lib/systemd/coredump` is swept after two weeks. So a bigger cap costs disk only while a core is
actually there, and does not accumulate.

Check what is saved with `coredumpctl list`; read one with
`coredumpctl --debugger-arguments="-batch -ex 'thread apply all bt 12'" gdb <PID>`.

## Python tooling (user-level)

```bash
# PDM (project manager)
pipx install pdm

# pyan3 (static call graph generator)
pipx install pyan3

# PyPI publishing
pipx install build
pipx install twine

# GGUF metadata tools (gguf-dump et al.), from the llama.cpp project.
# `gguf-dump --no-tensors model.gguf` prints a local LLM's metadata, including its
# `tokenizer.chat_template`. Reading that template is the only reliable way to find
# out what message shapes a model actually accepts — backends surface a rejected
# shape as a template-parser error that names the parser, not the offending message,
# and the templates' own error strings can be misleading (Qwen3.5's "System message
# must be at the beginning" is really a count rule: exactly one, at index 0).
pipx install gguf

# Global macro-enabled IPython (on latest Python)
pipx install ipython --python python3.14
pipx inject ipython mcpyrate

# Global macropython (one per Python version, with version suffix)
pipx install mcpyrate --python python3.10 --suffix 3.10
pipx install mcpyrate --python python3.11 --suffix 3.11
pipx install mcpyrate --python python3.12 --suffix 3.12
pipx install mcpyrate --python python3.13 --suffix 3.13
pipx install mcpyrate --python python3.14 --suffix 3.14
pipx install mcpyrate --python python3.15 --suffix 3.15   # supported since mcpyrate 4.3.0

# ...and a bare `macropython` pointing at a current one, so tooling and docs can
# rely on the unsuffixed name existing. Cleaning __pycache__ (macropython -C) is
# version-agnostic, which is the common use for the bare name.
ln -s ~/.local/bin/macropython3.14 ~/.local/bin/macropython

# Editor tools fallback venv (for projects without their own venv)
python3.14 -m venv ~/.local/venvs/editor-tools
~/.local/venvs/editor-tools/bin/python -m pip install flake8 autopep8 importmagic epc
```

**When to use the suffixed name instead.** The bare symlink is a convenience for
version-agnostic work — cleaning `__pycache__`, mostly. To *run* macro-enabled code
outside a project venv, the interpreter version matters, so name it explicitly
(`macropython3.12 script.py`). Inside a project venv that has `mcpyrate`, the venv's
own `macropython` shadows the symlink anyway and is the right one by construction.

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

**Needed by:** pi (below, under "Local AI stack"), LM Studio's `npx`-based MCP servers, the Playwright MCP server, and JS development generally — modding JS software, and the planned Raven-avatar JS client. Nothing in the base setup fails without it, so a skipped step here goes unnoticed until one of those is first used.

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

**Move the first two lines above `~/.bashrc`'s "If not running interactively" guard** (see "Bashrc additions" below); the `bash_completion` line stays where the installer put it. The installer appends the block at the end, below the guard, so as installed it is sourced by interactive shells only: a `bash -lc` — which is how the MCP servers here are launched — returns at the guard and never reaches it, and neither does a non-interactive `ssh host '<cmd>'`. Check with `env -i HOME=$HOME bash -lc 'which npx'`, which prints a path once the move is done and nothing before. nvm itself rarely needs upgrading; re-run the bootstrap with a newer tag to bump it. The literal original install command tends to age out of `~/.bash_history` — don't bother trying to recover it, the recipe above reproduces the same end state.

### LM Studio MCP servers

`mcp.json` lives at `~/.lmstudio/mcp.json` (LM Studio follows Cursor's notation: a top-level `mcpServers` object). LM Studio spawns one process per server; for npx-based local servers, npx must be on the *spawned* process's PATH — which, per the nvm gotcha above, it isn't when LM Studio is launched from the desktop. The login-shell wrapper (`bash -lc`) re-sources the profile so npx resolves, and survives Node upgrades (no hardcoded version directory). Confirmed working, using the [open-meteo](https://github.com/cmer81/open-meteo-mcp) weather server as the example:

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

Why `-lc` works on Ubuntu: a login shell sources `~/.profile`, and Ubuntu's stock `~/.profile` in turn sources `~/.bashrc` when running under bash. The shell is still non-interactive, so `.bashrc` returns at its "If not running interactively" guard, and only what sits above the guard is loaded — hence moving the nvm lines there (Node.js section above). With LM Studio started from a terminal, its servers would inherit that terminal's PATH and find npx regardless; the move is what makes the config work however LM Studio was launched.

Notes on the npx invocation, for future debugging:
- First launch is slow — npx fetches `open-meteo-mcp-server` from the registry into `~/.npm/_npx/` (a content-hash-keyed cache) and runs the binary from there. Subsequent launches hit the cache.
- `-y` auto-approves the install so the non-interactive spawned process doesn't hang on a prompt.
- `-p X X` is `--package` (what to fetch) + the trailing command (what to run); they collide on the same name here, so a bare `npx -y open-meteo-mcp-server` would resolve identically. The explicit form is the README author's.
- Cache reuse means you don't pull fresh arbitrary code every launch (good) but also don't auto-get upstream security fixes until the cache entry clears (less good). For a pinned, controlled artifact: `npm install -g open-meteo-mcp-server@<version>` and point `command` at the installed binary instead.
- Once running, the server's tools show up in the chat UI (hammer icon, as of mid-2026 — the devs move the GUI around), gated behind LM Studio's per-call confirmation dialog. If they don't appear after saving `mcp.json`, check LM Studio's logs for a spawn/ENOENT error on npx — that's the PATH problem, meaning the `-lc` bridge above didn't fire.

Pre-flight check, from a fresh terminal on the target machine:

```bash
bash -lc 'which npx && node --version'
```

A path plus a version means the config above will work. Empty output means the login shell isn't sourcing the nvm block — fix that on the dotfile side, not in `mcp.json`.

npx package names drift over time. If `open-meteo-mcp-server` ever stops resolving, that's the first thing to check when copying this config to a new machine after a long gap: run the `npx -y -p …` line directly in a terminal and watch for a resolution failure. From LM Studio's side the symptom is silent — the server just never comes up.

#### The current set

Four servers, set up 2026-10 to give a local model (Qwen) something to work with. The filesystem and shell servers are for LM Studio only — pi has its own file and shell tools — while Playwright is in pi's `mcp.json` too. Two need an install step first; the other two are fetched by npx on first launch, as above.

**Filesystem — [mark3labs/mcp-filesystem-server](https://github.com/mark3labs/mcp-filesystem-server).** Not the official `@modelcontextprotocol/server-filesystem`: this one has `search_within_files`. The alternative was the official server plus mcollina's `mcp-ripgrep` for search, and `mcp-ripgrep` had an open CVE (as of 2026-10).

It is a Go binary. `go install` would work, but Go is not otherwise needed here, so use the release tarball instead:

```bash
# From https://github.com/mark3labs/mcp-filesystem-server/releases, the linux_amd64 tarball.
# It unpacks flat (binary, LICENSE, README), so give it a directory of its own and symlink
# the binary out of it, as with PyPy and Zotero above.
mkdir -p ~/.local/bin/mcp-filesystem-server_linux_amd64
tar -xzf mcp-filesystem-server_*linux_amd64*.tar.gz -C ~/.local/bin/mcp-filesystem-server_linux_amd64
ln -sfn mcp-filesystem-server_linux_amd64/mcp-filesystem-server ~/.local/bin/mcp-filesystem-server
```

Its arguments are the directories it may access — here one dedicated sandbox, `~/Documents/lmstudio_mcp`. Installed version: 0.11.1 on all three machines (2026-11-16); the binary has no `--version`, but its reply to an MCP `initialize` request names it in `serverInfo`.

**Shell — [hdresearch/mcp-shell](https://github.com/hdresearch/mcp-shell).** Run from a clone rather than through npx. The npm package of the same name names no source repository, so the clone is the copy that can be read:

```bash
git clone https://github.com/hdresearch/mcp-shell ~/Documents/koodit/mcp-shell
cd ~/Documents/koodit/mcp-shell && npm install    # `prepare` runs the TypeScript build
```

To update, `git pull` and `npm install` again.

**Browser — [Playwright MCP](https://github.com/microsoft/playwright-mcp)**, for testing HTML. Fetched live by npx, and pointed at the system Chromium.

The `mcp.json` for all four:

```json
{
  "mcpServers": {
    "open-meteo": {
      "command": "bash",
      "args": ["-lc", "npx -y -p open-meteo-mcp-server open-meteo-mcp-server"]
    },
    "filesystem": {
      "command": "bash",
      "args": ["-lc", "mcp-filesystem-server $HOME/Documents/lmstudio_mcp"]
    },
    "playwright": {
      "command": "bash",
      "args": ["-lc", "npx -y @playwright/mcp --browser chromium --executable-path $(which chromium)"]
    },
    "shell": {
      "command": "bash",
      "args": ["-lc", "node $HOME/Documents/koodit/mcp-shell/build/index.js"]
    }
  }
}
```

#### LM Studio stops in its terminal when a turn begins

With the filesystem or Playwright server enabled, `lmstudio` started from a terminal stops as if Ctrl+Z had been pressed when an AI turn begins, and needs `fg`, several times over. Something in those servers' startup signals the terminal it should not. Running LM Studio under `script`, which gives it a pseudo-terminal of its own, blocks that and still shows the log in colour. In `~/.bashrc`:

```bash
alias lmstudio='script -qc "lmstudio" /dev/null'
```

The cause is not pinned down. Separately, keep anything that touches the terminal — a `stty -ixon`, say — below `~/.bashrc`'s "if not running interactively" guard: every server here starts through `bash -lc`, which runs whatever sits above it, and an `stty` there puts an `Inappropriate ioctl for device` into each server's log.

## Spacemacs

```bash
sudo apt install emacs     # Ubuntu's package; 29.3 on Mint 22.x
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
# flake8 (reporter) and autopep8 (rewriter) each get their own config from .spacemacs.d.
# Not one shared file: autopep8 ignores `# noqa`, so it needs a whitelist, not flake8's ignore list.
ln -s ~/.spacemacs.d/flake8 ~/.config/flake8
ln -s ~/.spacemacs.d/pep8 ~/.config/pep8
```

### Wiktionary dictionary

Copy `~/.spacemacs.d/dictionaries_enwiktionary/` from old machine (Matthias Buchmeier's Wiktionary extraction, dictd format). Update from [Matthias Buchmeier's Wiktionary user page](http://en.wiktionary.org/wiki/User:Matthias_Buchmeier) if desired.

### Fonts

Copy `~/.fonts/` from old machine. Run `fc-cache -fv` after.

#### Microsoft core fonts

For reading `.docx` and `.pptx` written by other people — Arial, Times New Roman, Courier New, Verdana, Georgia and the rest of the web core set:

```bash
sudo apt install ttf-mscorefonts-installer   # multiverse; downloads from SourceForge, EULA prompt
fc-cache -fv
```

Interactive (the EULA is a debconf dialog), and it fetches the archives at install time rather than shipping them.

Ubuntu ships metric-compatible substitutes by default — `fonts-liberation` (Times, Arial, Courier), `fonts-crosextra-carlito` (Calibri), `fonts-crosextra-caladea` (Cambria) — and fontconfig maps the MS names onto them automatically. Layout and line breaks therefore come out right without this package; the glyph shapes don't. Check with `fc-list | grep -i arial`: hits under `truetype/msttcorefonts/` mean the real thing is installed, no hits mean substitution is doing the work.

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

### MCP servers

Playwright, for client-side JS testing — the same server LM Studio and pi run (Node.js section). User scope, so it lands in `~/.claude.json` (machine-local, not in this repo) and is available in every project:

```bash
claude mcp add --scope user playwright -- bash -lc 'npx -y @playwright/mcp --browser chromium --executable-path $(which chromium)'
claude mcp get playwright    # Status: ✔ Connected
```

The single quotes keep `$(which chromium)` unexpanded, so it is resolved each time the server starts. Needs nvm's load lines above `~/.bashrc`'s interactive guard (Node.js section), or `bash -lc` finds no `npx`.

### Point git at the shared hooks

The hook script travels with the clone; the setting that activates it does not, because it lives in `~/.gitconfig` rather than in any repo. So this is one command per machine:

```bash
git config --global core.hooksPath '~/.claude/githooks'
```

Quote the tilde so the shell leaves it alone — git expands it itself, which is what keeps a username out of the config.

That installs `githooks/commit-msg` for **every** repo on the machine, freshly cloned ones included, so there is nothing to repeat per project. It refuses a commit whose message carries no `Co-Authored-By: Claude ...` trailer, and it fires only when `CLAUDECODE` is set, so commits made from magit or an ordinary shell are untouched. `git commit --no-verify` bypasses it. Rationale in `CLAUDE.md`, under the section on the hook.

Note this *replaces* per-repo `.git/hooks/` rather than adding to it. No fleet repo had a hook installed when this went in (checked 2026-08-26), so nothing was displaced — but a project that later wants its own hooks has to put them here, or override `core.hooksPath` locally.

Put the bare-command scripts on PATH. The repo holds the only copy, so symlink them rather than copying — otherwise the two drift and you're editing the wrong one:

```bash
ln -s ~/.claude/scripts/em ~/.local/bin/em
ln -s ~/.claude/scripts/api-inventory.py ~/.local/bin/api-inventory
ln -s ~/.claude/scripts/cc-toast ~/.local/bin/cc-toast
ln -s ~/.claude/scripts/ci-watch ~/.local/bin/ci-watch
ln -s ~/.claude/scripts/cc-context.py ~/.local/bin/cc-context
ln -s ~/.claude/scripts/fleet-pull.sh ~/.local/bin/fleet-pull
ln -s ~/.claude/scripts/nvidia-underclock.sh ~/.local/bin/nvidia-underclock
ln -s ~/.claude/scripts/cpu-powercap.sh ~/.local/bin/cpu-powercap
ln -s ~/Documents/koodit/substrate-independent/scripts/cc-log-extract.py ~/.local/bin/cc-log-extract
```

The last one points outside this repo: `cc-log-extract` lives in `substrate-independent`, which has its test suite, so that clone has to exist first.

On the AI server only, three more, for its local LLM stack (they need gufo, podman and an AMD APU, so elsewhere they have nothing to run against):

```bash
ln -s ~/.claude/scripts/gufo-serve ~/.local/bin/gufo-serve
ln -s ~/.claude/scripts/open-webui-serve ~/.local/bin/open-webui-serve
ln -s ~/.claude/scripts/powerlog.py ~/.local/bin/powerlog
```

The `api-inventory`, `cc-context`, `cc-log-extract` and `powerlog` symlinks drop the `.py` because that is the name the docs invoke: without it, every documented `api-inventory …` line is a command not found, and the agent that typed it gets an empty result rather than an error it can act on.

**Which scripts get a symlink is decided by how they are invoked**, not by being in `scripts/`:

- **Typed as a bare command by an agent**, because `CLAUDE.md` or a skill says to: `em`, `api-inventory`, `cc-toast`, `ci-watch`, `cc-context`, `cc-log-extract`. A missing symlink surfaces as a command not found in the middle of unrelated work.
- **Typed by a human:** `fleet-pull` on sitting down at a machine; `nvidia-underclock` and `cpu-powercap` before a long run, to trade speed for fan noise; and on the AI server, `gufo-serve`, `open-webui-serve` and `powerlog`. `nvidia-underclock` and `cpu-powercap` take `enable` (the default) or `disable` and need sudo. `nvidia-underclock`'s clocks are tuned for specific hardware, and its header says which; `cpu-powercap`'s `disable` restores whatever limits its first `enable` found, so it carries over between machines as is. `cpu-powercap watch` shows the measured package power, to check that a cap holds.
- **Named by path wherever they appear**, so no symlink: `build-webchat.py`, `check-move.py`, `check-prose.py`, `fleet-pull-selftest.sh`, and `run-on-internal-gpu.sh`, which is `source`d and needs a path regardless.

**A machine set up before a script existed will be missing its symlink, silently**: the list grows, and nothing re-runs this section on a machine that is already up. So when adding a script here, check every machine:

```bash
ls -l ~/.local/bin/{em,api-inventory,cc-toast,ci-watch,cc-context,cc-log-extract,fleet-pull,nvidia-underclock,cpu-powercap}
ls -l ~/.local/bin/{gufo-serve,open-webui-serve,powerlog}   # the AI server only
```

**On the work machine, archive the session logs to the personal machine**, whose home-folder backup then picks them up. `cleanupPeriodDays` in `settings.json` already stops Claude Code deleting them; the copy guards against the next surprise of that kind. A daily systemd user timer — `~/.config/systemd/user/cc-log-archive.service`:

```ini
[Unit]
Description=Archive Claude Code session logs to <personal-machine>, whose home-folder backup picks them up

[Service]
Type=oneshot
# No agent under systemd anyway; unset it so an interactive `systemctl --user start` behaves the same.
UnsetEnvironment=SSH_AUTH_SOCK
# No --delete, so the archive keeps whatever this machine loses.
ExecStart=/usr/bin/rsync -a -e "ssh -o BatchMode=yes -o ConnectTimeout=10" %h/.claude/projects/ <personal-machine>:Documents/cc-logs/<work-machine>/
```

and `cc-log-archive.timer` beside it:

```ini
[Unit]
Description=Daily archive of Claude Code session logs

[Timer]
OnCalendar=daily
# Run at the next login or wake if the machine was off or asleep at midnight.
Persistent=true
RandomizedDelaySec=10min

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now cc-log-archive.timer
systemctl --user start cc-log-archive.service      # one run now, to check
journalctl --user -u cc-log-archive                # failures land here
```

A timer rather than a crontab entry: anacron catches up only the root jobs in `/etc/anacrontab`, so a user crontab entry missed during sleep is simply skipped, where `Persistent=true` runs it at the next opportunity. It runs only while the user is logged in (no lingering), which suits a laptop. The key must have no passphrase, there being no agent. It is a push because the logs belong to the work machine: if the backup target ever moves, this unit is the one place to change. The actual hostnames are in `SECRET-SAUCE.md`.

**On the AI server, the same pattern backs up its irreplaceable data**, as a stopgap until it has proper backups: `~/.config/systemd/user/pleione-backup.service` and `.timer` (daily, `Persistent=true`). Unlike the laptop, that machine runs mostly as a server without anyone logged in, so it needs **lingering**, or its user timers wait for the next login: `sudo loginctl enable-linger $USER`, then `loginctl show-user $USER -p Linger` should say `yes`. The user's systemd instance then starts at boot. One `ExecStart` per item, each an `rsync -a` with no `--delete`, to the personal machine's `Documents/backups/<hostname>/`: the machine's local setup repo (`~/Documents/<hostname>`), Open WebUI's podman volume without its `cache/`, LM Studio's `~/.lmstudio` without what it downloads or unpacks itself (`models/`, `extensions/`, `bin/`, `.internal/utils/`, `.internal/bundled-models/`), and the Claude Code session logs to `Documents/cc-logs/<hostname>/`. Two rsync details that bit while writing it, both caught by dry runs (`rsync -an --stats`) before the first real run:

- **Anchored excludes are relative to the transfer root.** With `~/.lmstudio` as the source (no trailing slash), `--exclude=/models/` matches nothing, and the copy came to 73 GB. With `~/.lmstudio/` and an explicit target directory, it is 0.6 MB.
- **rsync creates only the last directory of the target path**, so a fresh target needs `--rsync-path="mkdir -p <dir> && rsync"`.

The statusline script requires `jq`; `scripts/build-webchat.py` uses `xclip`; `em` uses `wmctrl` and `emacsclient`. The first three are in the Essentials block above; `emacsclient` comes with Emacs, under "Spacemacs".

### Adopting an existing `~/.claude` into the repo

`git clone` refuses a non-empty directory, so a machine that has already been running Claude Code — with accumulated `projects/`, `sessions/`, `memory/`, `history.jsonl` — cannot take the clone above. Turn the existing directory into the repo in place instead.

This is safe because of how `.gitignore` is built: a deny-all (`/*`) plus an explicit allowlist, so every piece of runtime state is ignored, and `git reset --hard` rewrites only *tracked* files. Memories and session logs survive untouched; the machine's stale configs are replaced by the authoritative ones. That replacement is the point of the operation, not a side effect of it.

```bash
# Safety copy — cheap, and Claude Code keeps running from the original
cp -a ~/.claude ~/.claude.pre-sync.bak

cd ~/.claude
git init -b main
git remote add origin git@github.com:Technologicat/dotclaude.git
git fetch origin
git reset --hard origin/main                  # tracked files only; ignored state stays put
git branch --set-upstream-to=origin/main main
```

The `--set-upstream-to` line is load-bearing. `git init` followed by `reset` leaves `main` tracking nothing, and with no upstream, bare `git pull` and `git push` both refuse and `git status` cannot report ahead/behind — which is the one thing worth having when the whole point is keeping two machines in step.

Then hand-carry `SECRET-SAUCE.md` and `HARDWARE-NOTES.md` as above.

Finally, sweep the leftovers. A hard reset rewrites tracked files and deletes nothing else, so anything the repo has since superseded simply stays on disk. It comes in two flavours, and `git` marks them differently:

```bash
git status --ignored --short        # ?? and !! lines are both leftovers
```

- `!!` — *ignored* cruft at the top level: old notes that now live under `skills/` or `briefs/`, stray backups, an orphaned `memory/` from a previous Claude Code layout. The deny-all hides these, so a plain `git status` reads clean while they linger and go stale.
- `??` — *untracked* stragglers inside the allowlisted directories (`commands/`, `scripts/`, `skills/`, `briefs/`). These are the sneakier ones: an old `commands/foo.md`, from before that command became a skill, is not ignored — so Claude Code still loads it as a slash command, alongside the skill that superseded it.

Anything that is neither runtime state nor one of the two private files is a superseded copy; diff it against whatever replaced it, then delete it. Machine-local Claude Code settings do not belong back in the tracked `settings.json` — put them in `settings.local.json`, which the deny-all already ignores.

### Kitty terminal workaround (currently not needed)

Older Claude Code versions left the terminal in raw mode on exit, which this wrapper repaired:

```bash
claude() { command claude "$@"; reset; }
```

Not seen recently on any machine, so it is commented out as of 2026-11-15. If a terminal comes back
garbled after quitting Claude Code, re-enable it. The `fix` alias below repairs a terminal by hand.

## Bashrc additions

Merge these into the distribution's fresh `~/.bashrc` rather than copying an old one over it.

**Before the "If not running interactively" guard**, so a non-interactive `ssh host '<cmd>'` gets them too.
That is the `PATH` line, nvm's two load lines (moved up from the end of the file, where its installer
appends them; see the Node.js section), plus the wrappers and aliases below:

```bash
export PATH=/home/jje/.local/bin/:$PATH

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm

alias fix='reset; stty sane; tput rs1; clear; echo -e "\033c"'
alias gg='git log --oneline --abbrev-commit --all --graph --decorate --color'
alias gl='git log --pretty=oneline'
alias grip='grip -b'
alias lmstudio='script -qc "lmstudio" /dev/null'
```

**After the guard**, the interactive-only settings:

```bash
# disable XON/XOFF
stty -ixon
```

Then, in the template's own lines: uncomment `shopt -s globstar`; add `export LESS="-R"` after the
`lesspipe` line; and add `xterm-kitty` to the color-prompt case
(`xterm-color|*-256color|xterm-kitty) color_prompt=yes;;`). Kitty sets `TERM=xterm-kitty`, which the
stock pattern does not match, so without that the prompt stays uncolored.

### Project commands

Several projects need venv activation and environment setup before their CLI entry points work. These shell wrappers go in `~/.bashrc` and handle the ceremony in a subshell so the caller's environment stays clean.

**Chandra** (image gen metadata tools):

```bash
export CHANDRA_MODELS_DIR=~/stable-diffusion-models/:~/ComfyUI/models/unet/:~/ComfyUI/models/vae/:~/ComfyUI/models/text_encoders/

chandra() {
    (
        cd ~/Documents/koodit/chandra/ &&
        eval "$(pdm venv activate)" &&
        cd - > /dev/null &&
        command chandra "$@"
    )
}
```

**Raven** (NLP/scientific apps): each command activates the Raven venv and sources `env.sh` (CUDA library paths). `raven-server` additionally sources `run-on-internal-gpu.sh` (to pin to the internal dGPU on multi-GPU machines; NVIDIA only, so leave it out on an AMD machine, where it would fail for lack of `nvidia-smi`) and `no-hammer-hf.sh` (to skip HuggingFace network hits at startup, once models are cached).

```bash
raven-arxiv-download() {
    (
        cd ~/Documents/koodit/raven/ &&
        eval "$(pdm venv activate)" &&
        source env.sh &&
        cd - > /dev/null &&
        command raven-arxiv-download "$@"
    )
}

raven-xdot-viewer() {
    (
        cd ~/Documents/koodit/raven/ &&
        eval "$(pdm venv activate)" &&
        source env.sh &&
        cd - > /dev/null &&
        command raven-xdot-viewer "$@"
    )
}

raven-cherrypick() {
    (
        cd ~/Documents/koodit/raven/ &&
        eval "$(pdm venv activate)" &&
        source env.sh &&
        cd - > /dev/null &&
        command raven-cherrypick "$@"
    )
}

raven-server() {
    (
        cd ~/Documents/koodit/raven/ &&
        eval "$(pdm venv activate)" &&
        source env.sh &&
        source run-on-internal-gpu.sh &&
        source no-hammer-hf.sh &&
        cd - > /dev/null &&
        command raven-server "$@"
    )
}
```

## Project setup (all projects)

The canonical dev-dependency block (editor tooling so Spacemacs finds jedi/epc/importmagic via auto-activated pyvenv), lint config, and the PDM flow live in the `project-setup` skill — see it for the authoritative version.

### Raven-specific

```bash
cd ~/Documents/koodit/raven
pdm use python3.12
pdm install -G cuda
```

- `requires-python` narrowed to `<3.13` due to kokoro/misaki TTS dependency
- After activating the venv, `source env.sh` to set up CUDA library paths (LD_LIBRARY_PATH, ptxas). The script auto-discovers all pip-installed NVIDIA lib dirs — works with CUDA 12 and 13.

## Local AI stack

LM Studio (LLM inference) and ComfyUI (image generation) form the local AI stack. On the NVIDIA machines both use CUDA with current drivers. LM Studio also runs on the AI server's AMD APU, through its Vulkan or ROCm runtime (tested November 2026); ComfyUI there is untried.

### LM Studio

**The GUI app is enough on a desktop machine.** It ships `lms`: its first-run wizard offers to add `~/.lmstudio/bin` to `PATH`, and appends the same block to `~/.bashrc` that the CLI installer writes. The separate CLI install below is for a machine without the GUI.

**Runtimes.** LM Studio downloads the llama.cpp builds it thinks fit, and on an AMD machine that included a useless CUDA one. List, add, select and remove them with `lms runtime`:

```bash
lms runtime get --list                                   # what is available
lms runtime get -y llama.cpp-linux-x86_64-amd-rocm-avx2  # e.g. the ROCm build (~1.7 GB)
lms runtime select <engine>@<version>
lms runtime remove -y <engine>@<version>                 # without -y it waits at a confirmation
lms runtime survey                                       # the GPU and memory the selected engine sees
```

On an APU, the two AMD runtimes see different memory: ROCm reports the GTT ceiling (116 GiB on the AI server), while Vulkan reports what RADV reports (78.67 GiB there). LM Studio's guardrails go by the selected runtime's figure.

**MTP heads are used automatically.** If a model's folder holds an MTP head (`mtp-*.gguf`, as in Unsloth's Qwen 3.8 repos), LM Studio uses it for speculative decoding without being told, and `lms ls` lists the head (plus the `mmproj`) as if it were another quant of the model. Don't load that entry by itself. The server log shows `creating MTP draft context` at load and the draft acceptance per request.

**CLI daemon:**

```bash
curl -fsSL https://lmstudio.ai/install.sh | bash
```

This installs `llmster` into `~/.lmstudio/` and puts `lms` on PATH via `~/.lmstudio/bin`. The installer appends a PATH export to `~/.bashrc`. Same `curl | bash` tradeoff as nvm — acceptable for a personal dev box.

**GUI app:** download the AppImage (or .deb) from https://lmstudio.ai/download — the CLI installer does not include the GUI. Symlink or place the AppImage wherever local apps live (e.g. `~/.local/bin/`).

**Models** live under `~/.lmstudio/models/PUBLISHER/MODEL/` (GGUF format) — e.g. `~/.lmstudio/models/lmstudio-community/Qwen2.5-14B-Instruct-GGUF/`. Transfer from an existing machine via Warpinator (preserve the two-level directory structure) or download through the LM Studio GUI. MCP server configuration is covered above under "LM Studio MCP servers" in the Node.js section.

**Per-model settings** — load settings and any chat-template override — are saved under `~/.lmstudio/.internal/user-concrete-model-default-config/PUBLISHER/MODEL/`, one JSON file per GGUF. They come along with a copy of `~/.lmstudio`, so check them before applying them on a new machine:

- **Keep thinking retention on for Qwen 3.8, so no `{%- set preserve_thinking = false %}` line in a template override.** The model is trained with retention on, and its stock template keeps every earlier turn's thinking unless that variable is set false. With retention on, it builds on its earlier reasoning instead of restarting its solution each turn, and writes less new thinking per turn, since much of the material is already in context (observed 2026-10-20). An override written to save context did the opposite.
- The runtime decides as much as the template. Qwen 3.6's template strips earlier thinking unless `preserve_thinking` is set, but LM Studio's runtime sets it by default for any template that has such a switch (its server log says so at load: `chat template supports preserving reasoning, it is enabled by default`). So on LM Studio 3.6 keeps it too, unless an override sets it false. A template with no switch, as Qwen 3.5's, strips regardless. Raven's `investigations/thinking-retention/` has the measurements.

**Web search** comes from a Hub plugin, not an MCP server:

```bash
lms get npacker/web-tools
```

Then enable and configure it in the LM Studio GUI. It bundles web search, image search, visit-website and fetch-images. Hub page: https://lmstudio.ai/npacker/web-tools

**Install by exact slug.** `web-tools` has a cloud of near-identical forks on the Hub (`rezet`, `webbrain`, `vanily123`, `altra`, …); `npacker/web-tools` is the maintained, widely-used one (a few thousand downloads, updated within the last month, as of mid-2026). The slug matters more than it looks, because the Hub's browse surface went dead around June 2026 — the `/plugins` index page vanished — so you can't eyeball the forks apart in a browser; grabbing by exact slug sidesteps the question.

### pi

[pi](https://pi.dev) is a terminal coding agent, pointed here at local models. Its whole managed install lives in `~/.pi/agent/`: config (`settings.json`, `models.json`, `keybindings.json`, `mcp.json`, `AGENTS.md`), extensions and packages (`extensions/`, `git/`, `npm/`), chatlogs (`sessions/`), and the release itself (`install/releases/<version>/`). So moving it to a new machine is a copy:

```bash
# From the old machine; skip releases other than the one in install/current-version
rsync -a --exclude 'install/releases/<old-version>/' ~/.pi/ newhost:.pi/
# On the new machine
ln -sfn ../../.pi/agent/bin/pi ~/.local/bin/pi
pi --version
```

- **It needs Node** (nvm, above). The release's entry point is `#!/usr/bin/env node`; the launcher would also put the pi installer's own Node (`~/.local/share/pi-node`) on PATH, but our machines have none, so nvm's has to be there.
- **Chatlogs are filed by the directory pi was started in**, encoded in the subdirectory name under `sessions/` (`--home-jje-Documents-lmstudio_mcp--`). A copied session belongs with that same path, so create the directories on the new machine if they are not there yet.
- **`models.json` names endpoints by host.** A `localhost` provider means the new machine's own LM Studio, which may not be serving yet.

How the original install was made is not recorded here yet.

### ComfyUI

```bash
cd ~
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python3.12 -m venv venv
source venv/bin/activate
pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
```

Python 3.12 is the safe choice for custom node compatibility (3.13 works, 3.14 may not with all nodes). The PyTorch install is large (~3 GB download).

**Model directories:** ComfyUI expects models under `~/ComfyUI/models/` (subdirs: `checkpoints/`, `unet/`, `vae/`, `text_encoders/`, etc.). Models shared with Chandra also live under `~/stable-diffusion-models/`. The `CHANDRA_MODELS_DIR` env var in `~/.bashrc` points at both locations.

```bash
mkdir -p ~/stable-diffusion-models
```

Transfer models selectively from an existing machine — a full collection is large and not all models are needed on every box.

**Custom nodes:** copy or clone into `~/ComfyUI/custom_nodes/`. If copying from a machine with a different Python version, clean stale bytecode first:

```bash
macropython -C ~/ComfyUI/custom_nodes
```

Then install their dependencies (with the venv active):

```bash
for req in ~/ComfyUI/custom_nodes/*/requirements.txt; do pip install -r "$req"; done
```

`comfyui_controlnet_aux` has unlisted dependencies — its `requirements.txt` is incomplete. After the batch install above, also:

```bash
pip install matplotlib scikit-image onnxruntime-gpu
```

- `matplotlib` and `scikit-image` (imported as `skimage`) are hard imports in the DWPose detector; without them the node fails to load entirely.
- `onnxruntime-gpu` provides CUDA-accelerated ONNX inference for DWPose. Without it, DWPose falls back to OpenCV on CPU (functional but slow).

**Running:** `cd ~/ComfyUI && source venv/bin/activate && python main.py` — opens a web UI on `http://127.0.0.1:8188`.

## AMD ROCm

AMD's compute stack, the counterpart of CUDA. Set up on the AI server (Strix Halo APU, gfx1151) with
ROCm 10.1.0 in November 2026; the authoritative instructions are AMD's
[install page](https://rocm.docs.amd.com/en/latest/install/rocm.html), and for Strix Halo also its
[system optimization page](https://rocm.docs.amd.com/en/latest/how-to/system-optimization/strixhalo.html).

**Kernel first.** gfx1151 needs two KFD fixes. AMD's support table lists Ubuntu 24.04 HWE
≥ 6.17.0-19.19, OEM ≥ 6.14.0-1018, Ubuntu 26.04, or any other distribution on Linux ≥ 6.18.4; check the
table for the ROCm version at hand. Mint 22.3's HWE kernel 7.0 is in range. (The install page also says
Ryzen APUs "require the OEM kernel 6.14", which contradicts the table; the table is the more specific of
the two.)

**Ryzen APUs use the kernel's own `amdgpu` driver**, so no DKMS driver package. A discrete Radeon or
Instinct card is different: see the kernel-driver step on AMD's install page.

Take a Timeshift snapshot first, as before an NVIDIA driver change (and see "Restoring a snapshot when X
won't start" under "NVIDIA driver" if it comes to that).

```bash
sudo apt install libatomic1 libquadmath0
# /dev/kfd, the compute device, belongs to group render and gets no desktop-session ACL,
# unlike the render node that OpenGL and Vulkan use. Takes effect at the next login.
sudo usermod -a -G render,video $LOGNAME

sudo mkdir --parents --mode=0755 /etc/apt/keyrings
wget https://stable.repo.amd.com/rocm/gpg/packages.gpg -O - | gpg --dearmor | sudo tee /etc/apt/keyrings/amdrocm.gpg > /dev/null
sudo tee /etc/apt/sources.list.d/amdrocm-stable.sources <<'EOF'
X-Repo-Id: amdrocm-stable
Types: deb
URIs: https://stable.repo.amd.com/rocm/core/packages/ubuntu2404/
Suites: stable
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/amdrocm.gpg
Enabled: yes
EOF
sudo apt update
sudo apt install amdrocm10.1 amdrocm10.1-gfx1151   # ~7 GB download, ~19 GB on disk
```

**GPU memory on an APU.** The GPU gets a fixed BIOS carve-out (VRAM) plus GTT, which is ordinary RAM
the GPU may map, capped by default at half of RAM. AMD recommends a small carve-out and a raised GTT
cap. The cap is the `ttm` module's `pages_limit`, in 4 KiB pages; it is a ceiling, not a reservation.
On the AI server, 116 GiB of 123 GiB visible, with a 2 GiB carve-out:

```bash
echo "options ttm pages_limit=$((116 * 1024 * 1024 / 4))" | sudo tee /etc/modprobe.d/ttm.conf
```

AMD's `amd-ttm --set <GB>` writes the same file; it is not needed. Mind earlyoom's threshold when
raising this (see the earlyoom note under "System packages").

Reboot, then verify:

```bash
id | grep -o render                                  # group membership is live
cat /sys/module/ttm/parameters/pages_limit           # the new cap
rocminfo | grep -m1 -o 'gfx1151'                     # the GPU is visible to ROCm
amd-smi version                                      # ROCm version
sudo dmesg | grep -iE 'amdgpu|kfd' | grep -iE 'error|fail|timeout'   # expect nothing
```

### gufo (Strix Halo only)

[gufo](https://github.com/gufo-org/gufo) is an inference engine written for exactly one chip, the Strix
Halo (gfx1151) with 128 GiB: one supported model per use case, kernels tuned for that GPU. On the AI
server it serves Qwen 3.8 Flash-Next. Run it from its container image, which carries its own runtime:
the `.deb` is built for Debian 13, not for Mint's Ubuntu 24.04 base.

**Host preparation**, once:

```bash
sudo apt install podman crun       # rootless podman needs crun for --group-add keep-groups
echo -e '* soft memlock unlimited\n* hard memlock unlimited' | sudo tee /etc/security/limits.d/99-gufo.conf
# then log out and back in; `ulimit -l` should say unlimited
```

The user also needs groups `render` and `video`, as for ROCm above. gufo's
[host configuration guide](https://github.com/gufo-org/toolboxes/blob/main/docs/host-configuration.md)
asks for kernel >= 6.18.4 and `linux-firmware` >= 20260110 (and to avoid 20251125). It also suggests
`amdgpu.gttsize=65536`; skip that if GTT is already raised through `ttm` as above.

**Pin the image version.** gufo releases every day or two, so pull a numbered tag rather than `latest`,
and move it deliberately:

```bash
podman pull ghcr.io/gufo-org/toolboxes/gufo-runtime:0.34.0
```

**Check the setup** (expect `Overall Status : [PASS]`):

```bash
podman run --rm --userns=keep-id:uid=1000,gid=1000 --group-add keep-groups \
  --device /dev/kfd --device /dev/dri --device /dev/accel/accel0 --ulimit memlock=-1 \
  ghcr.io/gufo-org/toolboxes/gufo-runtime:0.34.0 gufo diagnose
```

As of 0.34.0, `diagnose` does not check the firmware version, and it reports the GPU as "20 CUs" (reported upstream as gufo-org/gufo#1235): that is HIP's
`multiProcessorCount`, which counts workgroup processors (two CUs each) when the GPU runs in WGP
mode, as here. `rocminfo` shows the 40 CUs.

**Models live on the host**, outside the container, so that upgrading gufo means pulling a new image and
nothing else. Each model page in gufo's docs names the exact files and Hugging Face revision it was
validated against. For Flash-Next (~107 GiB: 103.7 GiB of UD-Q4_K_XL weights, the MTP head, the image
projector), with `hf` from `pipx install huggingface_hub`:

```bash
hf download unsloth/Qwen3.8-Flash-Next-GGUF --revision d96201194f103c906994f283f504209dc8d2a10c \
  --include "UD-Q4_K_XL/*" --include "MTP/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf" --include "mmproj-BF16.gguf" \
  --local-dir ~/models/flash-next
```

and mount `~/models` read-only into the container (`-v ~/models:/models:ro`).

**Serve** (tested November 2026 on the AI server; loads in ~20 s when the files are in the page cache):

```bash
podman run --rm --name gufo --network host \
  --userns=keep-id:uid=1000,gid=1000 --group-add keep-groups \
  --device /dev/kfd --device /dev/dri --device /dev/accel/accel0 --ulimit memlock=-1 \
  -v "$HOME/models:/models:ro" \
  ghcr.io/gufo-org/toolboxes/gufo-runtime:0.34.0 \
  gufo serve llm --served-model-name flash-next \
    --model /models/flash-next/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf \
    --speculative mtp --mtp-model /models/flash-next/MTP/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf \
    --sessions 3 --context 262144
```

It serves an OpenAI-compatible API on `http://127.0.0.1:8080/v1` (model ID `flash-next`). To serve the LAN,
bind to all interfaces with `--host 0.0.0.0`, a server option, so it goes between `serve` and `llm`
(`gufo serve --host 0.0.0.0 llm ...`; `--port` sits there too). gufo has no authentication, so anyone who can
reach the port can use the model. `--sessions` is the number of parallel requests, each with its own preallocated
context of `--context` tokens.

**Memory, as measured** (F16 KV cache, the only kind gufo 0.34.0 offers): a fixed ~85 GiB of GPU memory for
the weights and buffers, which is less than the 103.7 GiB file size, plus 6.93 GiB per 256 Ki session
(27.7 KiB per token, matching gufo's docs). Three full-length sessions take 104 GiB of a 116 GiB GTT cap
and leave ~13 GiB of host RAM; a fourth fits only by shrinking gufo's RAM prompt cache
(`--cache-ram-bytes`, by default half of free RAM up to 32 GiB), and then sits close to earlyoom's 2 GiB
threshold.

**Speed**, from `gufo bench` (greedy, 2048-token prompt, 128 generated): prefill ~1,900 tok/s at depth 0
and ~1,580 at 128 Ki; generation ~30 tok/s without MTP; with MTP ~63 tok/s on fresh text and ~120 on text
the MTP head can copy from context. Under sustained load the APU draws ~100 W in BIOS Balance mode and
settles around 66–71 °C.

**Wrappers.** `scripts/gufo-serve` and `scripts/open-webui-serve` (Open WebUI, below) wrap these commands
as `start [--lan]`, `stop`, `status` and `logs`; symlink them as under "Claude Code" above. `scripts/powerlog.py`
logs the APU's power, temperatures and clocks to CSV, for measurements like the ones above.

### Open WebUI (chat front end)

[Open WebUI](https://github.com/open-webui/open-webui) is a browser chat UI for any OpenAI-compatible
server, gufo included. Run it in podman too, pinned to a release:

```bash
podman pull ghcr.io/open-webui/open-webui:v0.13.3
podman run -d --rm --name open-webui --network host \
  -v open-webui:/app/backend/data \
  -e HOST=127.0.0.1 -e PORT=3000 \
  -e WEBUI_SECRET_KEY_FILE=/app/backend/data/.webui_secret_key \
  -e OPENAI_API_BASE_URL=http://127.0.0.1:8080/v1 -e OPENAI_API_KEY=none \
  -e ENABLE_OLLAMA_API=false \
  ghcr.io/open-webui/open-webui:v0.13.3
```

Then open `http://127.0.0.1:3000`; the first account created becomes the admin. Notes on the options:

- **Port 3000, not its default 8080**, which gufo already uses: with host networking the two share the
  host's ports.
- **`HOST=0.0.0.0`** instead serves it to the LAN. Open WebUI has its own logins, but the gufo server
  behind it has none.
- **All state lives in the volume `open-webui`** (accounts, chats, settings), so upgrading means pulling a
  new tag and nothing else.
- **`WEBUI_SECRET_KEY_FILE` puts the session signing key into that volume too.** Its default is
  `.webui_secret_key` relative to the working directory `/app/backend`, outside the volume, so a fresh
  container would generate a new key on every start and log everyone out.
- **`OPENAI_API_KEY` is a placeholder**: gufo takes no key, but Open WebUI wants a non-empty one.
- The first start takes a minute or two while it sets up its database.

## NVIDIA driver

Use the **graphics-drivers PPA**, on every machine:

```bash
sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt update

# What's actually on offer, newest last:
apt-cache search '^nvidia-driver-[0-9]+$' | sort -V

sudo apt install nvidia-driver-XXX   # XXX = a version from that list
sudo reboot
```

**Read the descriptions, don't just take the highest number.** The list interleaves two kinds of package: plain `NVIDIA driver metapackage` (desktop — what you want) and `NVIDIA Server Driver metapackage` (datacenter branch). They're numbered in one sequence, so the newest number is not reliably the newest *desktop* driver. Pick the highest-numbered plain desktop metapackage unless you have a specific reason not to.

The PPA's own page lists what it currently ships and which Ubuntu releases each supports: <https://launchpad.net/~graphics-drivers/+archive/ubuntu/ppa>

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

Take a Timeshift snapshot before any driver-stack swap — a manual one, not just whatever the schedule last produced:

```bash
sudo timeshift --create --comments 'before nvidia-driver-XXX'
```

NVIDIA's userspace + kernel module + DKMS state can end up inconsistent even when apt reports success, and a black-screen X server is much faster to roll back than to debug in place.

### Restoring a snapshot when X won't start

Timeshift is a GUI app, but **it has a full CLI** — you never need a working desktop to roll back. That's the whole reason the snapshot is worth taking before touching the driver stack.

Getting to a shell, in order of preference:

1. **A text console.** If the kernel is alive and only X is broken (the usual case for a bad driver), Ctrl+Alt+F1 gets you a TTY login. Mint keeps the graphical session on tty7 in the traditional way, so F1–F6 are all plain text consoles. This works far more often than a black screen suggests. (Distros that run the display manager on tty1 — modern Ubuntu, for one — need F2 or higher instead.)

   The console is a fresh login, not a view of the failure — to find out *why* X died, read the logs:

   ```bash
   less /var/log/Xorg.0.log              # the X server's own log; grep for (EE)
   journalctl -b -u lightdm              # display manager, this boot
   journalctl -b -k | grep -i nvidia     # kernel side: module load, DKMS
   ```
2. **GRUB recovery mode.** If even that fails: hold Shift (or Esc) during boot → *Advanced options* → the `(recovery mode)` entry → *root shell*. The root filesystem is mounted read-only there, so remount it first:

   ```bash
   mount -o remount,rw /
   ```

Then, from either shell:

```bash
sudo timeshift --list                                  # snapshot names, newest last
sudo timeshift --restore --snapshot '2026-07-13_09-00-01'
sudo reboot
```

`--restore` prompts for confirmation and for the target device; add `--scripted` to skip the prompts if you're confident. If the snapshots live on a device Timeshift isn't currently configured for, point it there with `--snapshot-device /dev/sdXN`.

Restoring `/` from the running system is supported and expected — Timeshift stages the rollback and completes it on the reboot.

**A rollback does not touch your data.** Timeshift snapshots *system* files only — it's the equivalent of a Windows system restore point, not a backup. Rolling back to a snapshot from a week ago does not cost you a week of work; what it costs is any OS package updates that landed since. (User data is a separate concern, handled here by Back in Time.) So there is no reason to hesitate over restoring an older snapshot than you'd like — hesitating is how people end up debugging a broken driver stack at 1 a.m. instead.

## Hardware

- Check the driver, and the CUDA version it supports (top right): `nvidia-smi`
- List GPUs: `nvidia-smi -L`

### The two GPU numberings disagree

On a multi-GPU box, `nvidia-smi` and CUDA index the same cards differently, and nothing reconciles them:

- **`nvidia-smi` enumerates in PCI bus order.** On a laptop + eGPU, that puts the internal dGPU first.
- **CUDA — and therefore torch — defaults to `CUDA_DEVICE_ORDER=FASTEST_FIRST`**, which puts the beefiest card first. `CUDA_VISIBLE_DEVICES` is interpreted in *this* ordering, not `nvidia-smi`'s.

So on a machine whose eGPU is the faster card, `nvidia-smi` calls the internal dGPU GPU 0 while torch calls it `cuda:1` — exactly inverted. Note that this is a *consequence*, not a rule: the eGPU sorts first because it's faster, not because it's external. A weaker eGPU would sort last, and any doc that memorized "eGPU is `cuda:0`" would then be quietly wrong.

Practical upshots:

- Identify GPUs by **name or UUID**, never by assuming the two tools agree on an index. `nvidia-smi -L` prints both. Model name alone can be ambiguous — two cards of the same model with different VRAM are indistinguishable by name.
- To pin work to a specific card, `scripts/run-on-internal-gpu.sh` in this repo is the worked example; its header comment explains why it *counts* GPUs with `nvidia-smi` but never *indexes* them with it.
- Setting `CUDA_DEVICE_ORDER=PCI_BUS_ID` makes the two agree, at the cost of reordering devices for every CUDA process in that shell.

Per-machine GPU inventory, device ordering as actually observed, and benchmark numbers live in `HARDWARE-NOTES.md` (machine-local, not in this repo).

## Gaming

Not part of baseline setup. If this machine games, see `GAMING-SETUP.md` (Steam/Proton, the Input Remapper phantom-gamepad udev rule, vkBasalt CRT post-processing, per-game launch options) and `VKBASALT-SETUP.md` for the vkBasalt build recipe. Apply only when separately requested.

The one thing baseline setup must get right for gaming's sake is the NVIDIA driver source — see above; the graphics-drivers PPA is the unconditional choice.
