---
name: live-gui-testing
description: How to launch, drive, screenshot, screen-record and close a running GUI app on the developer's own X session — finding the window, aiming a click at a widget, sending synthetic keystrokes that behave like real ones, capturing an animation to a GIF with ffmpeg, confirming an action landed, and shutting the app down again. Use when about to run a GUI app to look at a change, take a screenshot or a screen capture of one for documentation, inject keys or clicks with xdotool, compare layout candidates, or exercise how an app behaves when a server it talks to goes down or comes back mid-session. The safety rules that must fire *before* deciding to launch anything live in the project's CLAUDE.md, not here.
---

# Driving a live GUI on a shared desktop

The agent and the human are on the **same X session**, so every technique here has a second cost besides
the one it looks like: focus is a single-holder resource, and taking it takes it from a person who may be
mid-sentence.

**The standing constraints are in the project's `CLAUDE.md`** — announce before you take focus, put the
whole drive sequence in one Bash call, restore focus afterwards, never `pkill -f <app>`. Those have to fire
*before* the decision to launch, which is earlier than any skill can load, so they are deliberately not
duplicated here. This file is the *recipes*: what to type once the decision is made.

They divide by cost, and the cheap half is usually enough:

| | takes focus? | good for |
|---|---|---|
| screenshot an unfocused window | **no** | did it render, does it look right, did the state change |
| drive the app from inside its own process | **no**, beyond the window mapping | state machines, callbacks, anything below the X layer |
| synthetic keys and clicks | **yes** | only what genuinely needs the real input path |

**Reach for the top two first.** Most questions are answered without ever holding the keyboard.

**And the risk runs the opposite way from the obvious one.** The worry that comes to mind is a synthetic
keystroke escaping into the human's editor. The common failure is the reverse: **their typing lands in the
app.** The window took focus when it mapped, they are watching their own words rather than the screen, and
the rest of the sentence is delivered to whatever the app makes of it — a letter that means *cycle filter*,
an Enter that sends something.

That corrupts the *test* as surely as it interrupts them. The app is now in a state nobody chose and the log
has events nobody sent, so **an unexplained state change during a driven run is a stray human keystroke
until ruled out** — before it is investigated as a bug in the app, or blamed on your own injection. That
misdiagnosis has happened, in both directions, on the same incident.

It also means a window mapping is never free, even for a check that needs no focus of its own: launching is
what hands the app the keyboard, and whoever is typing finds out afterwards.

## Waiting for the app to come up

**Wait for the app's own ready line, not for a guessed number of seconds.** Startup times differ between apps
in one project and drift as a project grows, so a sleep is either a stall or a race, and picking between them
is a guess renewed every session.

**Do not carry the figures below into a `sleep`.** They are here to show that the spread is real and that it
moves, and they are the reason this section exists rather than a table of timings. The failure this warns
about has happened: a session read "Librarian takes about twenty-five" and wrote `sleep 25`, in a step whose
own instruction was not to. Whatever number is written here is measured on one machine, on one day, with
whatever else that machine was running — it is not a fact about your session.

- Raven's Visualizer, 2026-08-28: up in under ten seconds.
- Raven's Librarian, six consecutive launches 2026-09-04: **6.8–7.1 s** from the first log line to the render
  loop, with `raven-server` already up and the caches warm. The same doc said twenty-five a week earlier,
  which is the drift the rule is about.

```bash
LOG=/tmp/.../app.log
nohup <app> --log-level INFO --log "$LOG" >/dev/null 2>&1 &
# Bounded, like the shutdown loop below: an app that dies during startup writes no ready line ever, and an
# unbounded wait on one is indistinguishable from a slow boot until somebody asks what is taking so long.
for _ in $(seq 1 60); do grep -q "App render loop starting" "$LOG" 2>/dev/null && break; sleep 1; done
```

The ready line is per project. **In Raven every GUI app logs `App render loop starting.`** when its render
loop begins, which is the earliest moment a window can be driven. An app with no such line is worth giving
one; the alternative is polling for the window, which appears before the app is ready to answer.

Note the loop tests a *file*, so it cannot match itself — unlike the `pgrep -f` shape, which finds the shell
running it and waits forever.

## Testing together: you launch, they drive

**When the human is going to judge the result by using the app, launch it yourself and hand them the
keyboard** — rather than asking who should launch, or leaving it to them. They drive with real input, and
you get the log, which you would otherwise have to ask them to find and paste. (Juha, 2026-09-15.)

The shape is the recipe above with two differences:

- **Log to a file you can read**, in your scratchpad, and read it while they drive — so what they report
  seeing can be lined up against what the app did, as it happens.
- **Do not restore focus afterwards.** They are about to take the keyboard, and restoring raises your
  terminal over the app they were meant to be looking at.

The announcement and the toast are still owed: the window takes focus when it maps, whoever launched it.
Then say what to try and what you will be watching for in the log, and wait for them to report.

## Finding the window

```bash
WID=$(xdotool search --onlyvisible --name "raven" | head -1)
[ -n "$WID" ] || { echo "no window"; exit 1; }
```

- **`--name` is a regexp and already matches case-insensitively.** There is no `-i`, and passing one is how
  the lookup comes back empty. Measured 2026-08-19: an all-caps pattern returns the same window id as the
  exact-case one. Worth knowing because app titles are rarely consistent — in Raven, `raven-cherrypick` is
  lowercase, `Raven-librarian` and `Raven-visualizer` are not, and the xdot viewer is `Raven XDot Viewer`.
- **`--onlyvisible`**, so a stale or unmapped window cannot answer instead.
- **Guard the empty result before *anything* uses it** — not only before injection, which is where this
  warning used to stop. An empty `$WID` does not make the next command fail; it makes it wait, and the two
  ways it waits look like different bugs:
  - `xdotool windowactivate --sync ""` blocks on an activation that will never happen, until the Bash
    timeout kills the whole call — taking the app with it, that being the same process group.
  - `import -window "" shot.png` falls back to ImageMagick's **click-to-select-a-window** mode, which
    holds a pointer grab until somebody clicks. That freezes the whole desktop rather than just the run,
    so it is the one that costs the human instead of you. (Live case 2026-09-14: a couple of minutes of
    unresponsive desktop, ended by the Bash timeout. The guard one line above was already in this file;
    the command that skipped it was a screenshot, which never reads as *driving* a GUI.)

  **Both present as a slow app**, which is the misdiagnosis to expect: the call hangs somewhere after the
  launch, so the launch gets blamed. The app's own log settles it in one line — read when it wrote its
  ready line before believing anything about startup time. In that live case the app had been up in 2.5 s.

## Screenshots

`import -window <id> shot.png` captures an **unfocused** window fine, so a screenshot-only check is never
intrusive — provided the id is a real one. Check it first: an empty `<id>` turns the same command into a
desktop-freezing pointer grab, as the previous section says. `wmctrl -l` also lists window ids.

**The capture is in client-area coordinates**, which matters for the arithmetic below.

**A still with the window frame — title bar and rounded corners — comes from the desktop's own screenshot
service**, which `import` cannot reach. On Cinnamon (verified 2026-09-24):

```bash
gdbus call --session --dest org.gnome.Shell.Screenshot --object-path /org/gnome/Shell/Screenshot \
      --method org.gnome.Shell.Screenshot.ScreenshotWindow true false false /abs/path/shot.png
```

The arguments are `include_frame`, `include_cursor`, `flash` and `filename`, and it returns `(true, path)`
once the file is written. It has **no window argument: it captures the focused window**, so time it for
when the app has focus — which, while the human is driving it, it does. The output is RGBA; whether the
rounded corners come out transparent has not been checked on an unmaximized window. `org.Cinnamon`'s own
`ScreenshotWindow` does the same but returns before the file exists, so a check straight after it finds
nothing.

**When tuning placement or sizing, render the candidates side by side** into one image rather than asking
about them one at a time. The eye ranks a comparison and cannot rank a sequence, so serial single-shot
proposals cost a restart per candidate.

## Capturing motion

The protocol that worked on its first real use (Raven's documentation pass, 2026-09-24, on Cinnamon with
its compositor): `ffmpeg`'s `x11grab`, run by you while the human drives the app. Being scriptable is what
decides it over a GUI recorder such as `peek` — a recorder that needs a rectangle dragged and a button
clicked puts both jobs on the person at the keyboard.

**Grab the window, not the screen: `-window_id`.** A screen-region grab reads the composited screen, and on
a compositing desktop it catches frames where the compositor has painted the region *without* the window's
contents — the wallpaper shows through, whole or in strips. Measured: 17 of 105 frames in one take while
the app was redrawing, most of them only in a 45 px header strip. A screen grab also records any window
that passes over the region (a file manager, in the same session). Grabbing by window id had neither, in
360 frames over two takes. Offset and size are then *relative to the window*, which crops to one panel for
free:

```bash
WID=$(xdotool search --onlyvisible --name "Raven-librarian" | head -1); [ -n "$WID" ] || exit 1
cc-toast "● RECORDING — wait..."
( sleep 2; cc-toast "▶ GO" ) &
ffmpeg -hide_banner -loglevel error -y -f x11grab -window_id "$WID" -framerate 30 \
       -video_size 922x784 -i ":0.0+991,7" -t 7 -c:v libx264 -crf 12 -pix_fmt yuv444p cap.mp4
cc-toast "■ Recording stopped"
```

**The human needs a cue, and it has to fire when recording starts.** Without one they cue off whatever the
terminal happens to show, and when that changes the take is empty — one was: five seconds of a still
picture. So the toasts go in the same command as `ffmpeg`, as the launch toast goes with a launch.

**Record a lead-in, and trim to equal holds.** A couple of seconds of the resting state lets a viewer
orient before anything moves. Record it rather than padding a still frame in afterwards: the resting state
is rarely still (a pulsing keyboard mark, an idle animation), and a frozen frame stops it mid-breath. Then
trim so the hold after the motion matches the hold before it — unequal holds look odd on a loop. Record a
little long, so there is enough tail to match.

**Grab above the rate you are capturing.** An app that throttles itself while idle — Raven drops to twelve
— returns to full speed only while something animates, so a capture pinned at the idle rate aliases the
motion being recorded. Grab at 30, keep the intermediate near-lossless (`-crf 12`, `yuv444p`), decimate on
the way out.

**Check the take before encoding it**, each check with its control:

- **Motion**: count the frames that differ from the first (`compare -metric AE -fuzz 8%`). An empty take and
  a clean take look alike to every other check; only this tells them apart.
- **Foreign content**: per-frame brightness of *every* region, header strip included — a check that
  skipped the top 100 px passed all 17 bad frames above but two. A clean take sits in a narrow band (225–240
  on a dark Raven panel); a wallpaper frame reads far outside it.
- **A contact sheet** is the fastest look at the whole take:
  `ffmpeg -i cap.mp4 -vf "select='not(mod(n\,10))',scale=307:-1,tile=5x3" -frames:v 1 sheet.png`.
- **Where the motion starts and ends**, for the trim: `-vf "select='gt(scene,0.004)',metadata=print:file=-"`
  prints each change's timestamp. Find a threshold above whatever pulses at rest.

**Then two passes for the GIF**, because a single-pass encode quantizes per frame and looks it. 20 fps is
smooth enough for a morph that takes a second; `stats_mode=diff` and `diff_mode=rectangle` spend the
palette and the bytes on what moves:

```bash
ffmpeg -y -ss 0.3 -t 6.7 -i cap.mp4 -vf "fps=20,palettegen=stats_mode=diff" pal.png
ffmpeg -y -ss 0.3 -t 6.7 -i cap.mp4 -i pal.png \
       -lavfi "fps=20[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" out.gif
```

**GIF, for anything in a repo's Markdown: GitHub will not play a repo-relative video.** Tested 2026-09-24
on a scratch branch, in the web UI and the API's rendering alike: a `<video>` tag is stripped whole,
relative `src` or absolute raw URL, and Markdown image syntax pointing at an `.mp4` becomes an `<img>`,
which Chrome and Firefox show as a broken image. Video plays only from GitHub's own attachment CDN, which
is not versioned with the repo. The size cost is real — a 922×784 panel for 6.7 s came to 3.1 MB as GIF
against 0.34 MB as H.264.

**So finish with `gifsicle -O3 --lossy=30 out.gif -o final.gif`.** Measured on that capture: `-O3` alone
saved 3%, `--lossy=30` saved 34% with no difference visible at 2× magnification, and 80 and above started
to speckle the dark background. Dropping the palette pass's dither saved only 5% on its own, so the
dither can stay. `gifsicle` is in the machine setup's apt line.

## Aiming a click

**Get the window origin from `xwininfo -id <wid>`, never from `xdotool getwindowgeometry`:**

```
screen = xwininfo "Absolute upper-left X/Y"  +  the coordinate read off the screenshot
```

`xdotool getwindowgeometry` reports something else. Measured across every decorated window on one desktop,
its `Position` equals `xwininfo`'s **Absolute + Relative upper-left** — the client's offset inside its
window-manager frame, counted twice. The error is exactly the decoration size (32 px for a plain title bar;
10 px + 40 px on one app's window), which is about one toolbutton — enough to land on empty panel, where a
click silently does nothing rather than failing loudly. The one window that matched `xwininfo` was the
unreparented desktop, which has no frame to double-count. (The arithmetic is measured; that reparenting is
the mechanism inside xdotool is inferred from it, not read from its source.)

**The in-app half of the sum can come from the toolkit instead of from the eye.** In Raven that is
`raven.common.gui.utils.get_widget_pos(widget)`, which reports a viewport position for anything — including
the windows and child windows that have no `rect_min` — so a click is aimed at a widget *by name*:
`screen = xwininfo origin + get_widget_pos`. Reading a coordinate off a screenshot still works and needs no
running Python, but it has to be re-read whenever the layout moves.

**A click has to survive a frame, twice over** — and both halves fail silently, so a correctly aimed click
does nothing and reads as a wrong coordinate. An immediate-mode toolkit samples the pointer *and* the
button once per frame, and an idle-throttled app is not running at 60 fps: Raven's Librarian drops to
~12 fps when nothing is happening, which is 80 ms a frame.

- **`mousemove` and `click` in one command register at the old position.** The pointer has moved on the X
  server, but the app has not read it yet, so the press is attributed to wherever the pointer was.
- **`xdotool click 1` is about 12 ms down-to-up**, which can fall entirely between two frames and never be
  observed at all.

```bash
xdotool mousemove --sync $X $Y
sleep 0.4                                  # let the app read the new pointer position
xdotool mousedown 1; sleep 0.3; xdotool mouseup 1
```

**Hover first when a click seems not to land.** A toolkit that highlights the widget under the pointer —
DPG does — turns a bare `mousemove` plus a screenshot into a test of the *arithmetic alone*, with the click
question held apart. That is the negative control for this whole section: without it, a coordinate error
and a timing error look identical, and 2026-09-07 was spent proving the coordinates twice before suspecting
the timing.

**In a throwaway probe, pin the window to the origin instead.** With DearPyGui,
`dpg.set_primary_window(win, True)` drops the title bar and pins the window to the viewport origin, so the
arithmetic is the widget's own offset and nothing else. Worth the line because the failure without it is
silent: a click 25 px too high lands on the title bar and starts a *window drag*, and the probe then
reports that typing went nowhere.

## Synthetic keys are not keypresses

The single largest source of invented findings here. Three ways a synthetic key differs from a finger, all
of which make a working app look broken:

- **A chord sent as one word loses its modifier.** `xdotool key ctrl+b` presses and releases both in well
  under a millisecond. A toolkit that samples modifier state when its handler *runs* — one frame later —
  sees the modifier already gone. Send it as `xdotool keydown ctrl` / `xdotool key b` / `xdotool keyup ctrl`.
- **A held modifier auto-repeats** as repeated *press* events (~50 ms apart), often with a companion
  pseudo-key the toolkit's own constants do not name. A handler acting on a bare modifier keycode fires
  over and over.
- **A synthetic tap is far shorter than a human press** — `xdotool key Escape` holds it about 12 ms against
  a hundred and something for a finger. Anything that depends on *how long* a key is held is invisible to
  it, so a driven test passes where a real press fails, which is the worst direction for a check to be
  wrong in. Drive such keys as `keydown` / `sleep` / `keyup`, and pick the sleep against the machine's
  **keyboard repeat delay** (250 ms on both machines here, and a per-machine setting rather than a constant
  to hard-code): below it for one press, above it to additionally exercise auto-repeat. The two are
  different tests, so a 600 ms hold that reproduces a bug has not said which of them it found.

**In Raven, the mechanism behind the first two is in `dpg-notes.md` → "Keyboard input" →
"`is_key_down` is sampled when the callback runs, not when the key was pressed"**, together with the
observed pseudo-key codes. That file stays authoritative for the *why*; this section is the practice.

**Synthetic input needs real focus.** GLFW-backed apps ignore the `XSendEvent`-based
`xdotool key --window <id>`, so driving one means actually activating the window.

## Focus is not the caret — DearPyGui lore, not a driving technique

Kept here only because it *presents* as a driving failure. A window can be focused while no widget owns the
caret: met in the wild with `windowactivate --sync` succeeding, the window reporting focused, and every
keystroke going nowhere, because the field was merely *focused* and not *active*. **Click the target field
first, then type.**

Whether your toolkit draws that distinction is its own business — in Raven, `dpg-notes.md` → "Keyboard
input" → "Focus is not the same as the caret: gate hotkeys on `is_item_active`" is authoritative, and this
paragraph is only the consequence for someone holding an `xdotool`.

## Confirming it landed

**Never conclude from "the command exited 0".** `xdotool` reports success having typed into the wrong
window. The tells of a miss are a screenshot byte-identical to the one before, and a log with no new lines.

For a clipboard round-trip, **put a sentinel in first**:

```bash
printf SENTINEL | xclip -selection clipboard
# ...press the hotkey under test...
xclip -o -selection clipboard
```

Without it, a missed click reads as a pass against whatever the previous step left there.

## Closing the app

**Prefer the window manager: `wmctrl -i -c <window-id>`.** SIGTERM to the correct PID left the process
running (twice, tens of seconds apart) while `wmctrl -c` shut it down within seconds. It is also the
graceful path — it runs the app's own shutdown, so state is saved. Reserve a PID kill for a process with no
window, or one that ignores the close.

**Assume this of any DPG app rather than testing it each time** (Juha, 2026-08-31, after a second app
behaved identically — `raven-avatar-settings-editor`, still running its render loop some seconds after a
SIGTERM it never acted on). Why the signal goes unanswered has not been established; what is established
is that it does, on two apps on two occasions.

**The confusing part is that the kill *looks* like it worked.** The shell reports success, `pgrep` in the
same pipeline has already listed the process, and the next thing you see is a second window beside the
first. Check with `ps -p <pid>` before relaunching, not after.

**Never `xdotool windowclose`, which is not the polite version of that.** Its man page is explicit: *"This
action will destroy the window, but will not try to kill the client controlling it."* It is `XDestroyWindow`
— the window is yanked out from under the app, with no `WM_DELETE_WINDOW` and no chance to object, so the
toolkit's connection breaks and the process dies without running its `atexit` handlers. `wmctrl -i -c` sends
`_NET_CLOSE_WINDOW` and lets the window manager ask the app to close, which is the entirely different thing
the name suggests.

The failure is silent and lands somewhere else. On 2026-08-26 it cost a Raven-librarian session: the app
vanished from the screen looking exactly like a clean exit, and the chat datastore's last write turned out
to be from *startup* — every message of the session gone, with no crash, no core dump and no log line. The
first reading was a data-loss bug in the app under test, and the app was innocent. If state that should have
been saved is missing after a driven run, check how the app was closed before believing anything else.

**It does not always kill the client, and the case where it does not is worse.** Later the same day, the
same call on a DPG app left the process *immortal*: the window was gone from the screen and from
`xdotool search`, while the process ran on with 107 threads. `py-spy dump` put MainThread inside
`render_dearpygui_frame` — the render loop still spinning against a destroyed window — and because
MainThread never returns to the interpreter from that C call, Python never gets to run a signal handler, so
**SIGTERM is ignored too** and only SIGKILL ends it. Two `kill`s and a two-minute wait said nothing.

The tell that separates this from a genuine shutdown bug is what is *missing* from the log: teardown never
**began**, so there are no teardown lines at all, as opposed to a hang that logs its first phase and stops.
That reading cost most of an hour spent suspecting the session's own changes to the app's cancellation
paths — which could not have run, because nothing had asked the app to shut down. **If a driven app will
not exit, establish whether teardown started before investigating why it did not finish.**

**Then wait for it to be gone before relaunching**, in the same Bash call:

```bash
for i in $(seq 1 25); do [ "$(pgrep -af myapp | awk '$2 ~ /python/' | wc -l)" = 0 ] && break; sleep 2; done
```

Skip the wait and you get *two* instances, after which `xdotool search --name` returns two ids and a
`head -1` picks an arbitrary one. A screenshot of the stale window then reads as "my edit didn't take" — and
the tell is that its text matches an *earlier* revision of the source. Check that before concluding anything
about the change itself.

## Driving from inside the process, when the X layer is not the point

**Where the app has an in-process REPL this works on the real app, and the client is pipe-scriptable.** In
Raven every GUI app takes `--repl`; each piped line executes in the app's own namespace:

```bash
printf '%s\n' \
  'from raven.visualizer import importer_gui as ig' \
  'ig._input_files_box << ["/path/to/one.bib"]' \
  'ig._output_file_box << "/tmp/out.pickle"' \
  'ig.show_window()' \
  'ig.start_or_stop()' \
  | timeout 30 python -m unpythonic.net.client localhost
```

Reach for it when the state you need is **expensive to reach through the UI**. Above, starting an import
would otherwise mean driving two file dialogs with synthetic keys — holding the human's keyboard for the
whole sequence — where the pipe costs one window mapping and no injected input at all.

**Verify the pipe against a sentinel first, headless, before taking any focus.** The throwaway host is one
command — `unpythonic.net.server` runs a demo of itself when run as main, which exists for exactly this —
so the check needs nothing from the project under test:

```bash
python -m unpythonic.net.server &                     # binds 1337, control 8128; the client's defaults
printf 'print("SENTINEL-OK")\n' | timeout 12 python -m unpythonic.net.client localhost | grep SENTINEL-OK
```

**The sentinel has to *print*.** The session echoes the *value* of an expression and a statement has none,
so an assignment shows nothing at all, where `print(...)` is visible because `print` writes to stdout
itself. A pipe made only of assignments therefore looks identical whether it executed or not: the connect
banner, the prompts and `Session closed.` all arrive either way. Discovering
that afterwards means discovering it with the window already up and the keyboard already taken. (Live case
2026-09-14, Raven's importer fallback notice — whose own check piped an assignment and needed a purpose-built
host to read it back, which is the work this recipe removes.)

It inherits this section's ceiling: it proves the app's own state machine and says nothing about input
delivery.

---

With no such REPL, the same idea needs a host of its own: launch a script that builds the widget under
test, then feed it stages through a file it polls.

```python
# in the render loop
stage = read(MARKER)                      # a file this shell writes to
if stage and stage != seen:
    seen = stage
    threading.Thread(target=run, args=(stage,), daemon=True).start()
```

Two things make or break it:

- **Run each stage on a worker thread, not in the render loop.** Toolkits dispatch event callbacks off the
  render thread, and code that waits for frames cannot do so from the thread that renders them. Driving from
  the loop silently changes the timing you are trying to observe.
- **It proves the state machine and nothing below it.** A bug that lives between the X key and the handler
  will not reproduce this way — which is itself diagnostic: *if direct calls behave and real keys do not,
  the fault is in delivery.* That is how one Tab bug was localized on 2026-08-21 after two probes came back
  clean.

**When even that is not enough, log the state transitions with a stack and a thread name.** Two writes
arriving from the toolkit's own handlers, on either side of the app's, are invisible in the key path and
obvious in such a log.

## Testing what an app does when a server goes down, or comes back

**Own the moment it happens.** Point the app at a port you control — in Raven, every app that talks to a
server takes `--backend-url` and `--server-url` for exactly this — and put a TCP relay in front of the real
service. Starting and stopping the relay is then an event timed to the millisecond.

**In Raven the relay already exists**: `investigations/backend-fault-injection/tcprelay.py`, run as
`python tcprelay.py --port 8999 --upstream localhost:5100`. Kill it and the server has vanished; run it
again and it is back, with the real server and its models untouched — which matters, since restarting
Raven-server costs a model reload of half a minute or so. Its sibling `faultproxy.py` is for the other
question, a server that *misbehaves* rather than disappears, and is HTTP-aware for that reason; do not put
it in front of Raven-server, whose API carries real data in headers an HTTP proxy will not think to copy.

Elsewhere, twenty lines of `socket` and two `threading.Thread`s is the whole relay; `socat` does it too,
where installed.

**Prefer a command-line override to editing configuration**, wherever the app offers one. Config edited for
a test has to be edited back, and it is the file most likely to be carrying settings that are not yours to
change — in Raven specifically, each app's `config.py` is tracked *and* holds machine-local overrides, so a
stray edit there is one commit away from publishing somebody's paths.

The reason it is worth the setup: the interesting behaviour usually lives in a window narrower than the
thing that would otherwise close it. Librarian's backend-status pill wanted a backend that came up *during*
a one-second acknowledgment flash, while a three-second poll raced to notice it first — unwinnable by hand,
and turning the real service off and on just produces whichever outcome the poll picks. With the relay, the
click follows the port opening by 400 ms and the state is whatever you decided it should be.

## Requirements

`xdotool`, `xclip`, `wmctrl`, ImageMagick's `import`, and `ffmpeg` for the capture section. X11 — none of
this is Wayland-tested.
