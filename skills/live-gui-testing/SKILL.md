---
name: live-gui-testing
description: How to launch, drive, screenshot and close a running GUI app on the developer's own X session — finding the window, aiming a click at a widget, sending synthetic keystrokes that behave like real ones, confirming an action landed, and shutting the app down again. Use when about to run a GUI app to look at a change, take a screenshot of one, inject keys or clicks with xdotool, compare layout candidates, or exercise how an app behaves when a server it talks to goes down or comes back mid-session. The safety rules that must fire *before* deciding to launch anything live in the project's CLAUDE.md, not here.
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
- **Guard the empty result before the first injection.** `xdotool windowactivate --sync ""` *blocks*
  waiting for an activation that will never happen, until the Bash timeout kills the whole call — taking
  the app with it, that being the same process group. A two-minute hang that looks like a slow app.

## Screenshots

`import -window <id> shot.png` captures an **unfocused** window fine, so a screenshot-only check is never
intrusive. `wmctrl -l` also lists window ids.

**The capture is in client-area coordinates**, which matters for the arithmetic below.

**When tuning placement or sizing, render the candidates side by side** into one image rather than asking
about them one at a time. The eye ranks a comparison and cannot rank a sequence, so serial single-shot
proposals cost a restart per candidate.

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

When the question is about the app's own state machine rather than about input handling, **skip synthetic
input entirely**: launch a host script that builds the widget under test, then feed it stages through a file
it polls.

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
service. Starting and stopping the relay is then an event timed to the millisecond. Twenty lines of
`socket` and two `threading.Thread`s is the whole relay; `socat` does it too, where installed.

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

`xdotool`, `xclip`, `wmctrl`, and ImageMagick's `import`. X11 — none of this is Wayland-tested.
