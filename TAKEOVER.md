# TAKEOVER: the Star Monitor on a fresh Mac

1. Python 3.10 at `~/.pyenv/versions/3.10.14/bin/python3` with Flask (`pip install flask`).
2. Hammerspoon with the star (MANTRA_STAR) loaded and its command line installed (`hs.ipc.cliInstall()`
   in `~/.hammerspoon/init.lua`, the tool at `/opt/homebrew/bin/hs`). The star must be the one of
   14.9.2026 or later: `STAR.state`, `STAR.command`, `STAR.order` in `star.lua`.
3. Clone: `git clone https://github.com/markoboskoauroville/STAR_MONITOR ~/Developer/STAR_MONITOR`
4. The star's switch is `MANTRA_STAR/apps/monitor.lua`, pointing at that folder and that python. Tick
   "Star Monitor" (folder The Mac), or the row "Start the Star Monitor…" at the bottom of the menu; the
   page opens at http://127.0.0.1:8851.
5. Without the star: `python3 monitor.py` in the foreground, `python3 monitor.py open` for the page,
   `curl -X POST http://127.0.0.1:8851/quit` to stop it.
6. State is the star's: `~/.config/star-running.json` (what is open, so what comes back; the permanent
   file was taken out 20.9.2026), `~/.config/star-time.json`,
   `~/.config/star-order.json`. The log is `~/.star_monitor/monitor.log`. Nothing generated is in the repository.

7. The first row (v4, 31.10.2026): STAR MONITOR ON OFF … v4 TOP ✕; TOP keeps the window above the others (UserDefaults `onTop`); OFF, TOP and ✕ answer Accessibility as `off`, `top`, `close`.


## From the former README (13.11.2026)

# STAR_MONITOR, the page that manages the star

**One page, http://127.0.0.1:8851, for every app of the star menu: start, stop, put the important ones on top, see how long each has run, and say which come back after a restart.**

Marko's request, 14.9.2026: "build a star monitor, the application in a web interface which starts and
stops all applications. I can manage them, I can start, I can stop. I can also reorder them in that view,
which are most important will go to the top. Track how much time I'm running some applications, and in a
sorting order give me top, by alphabet, by application, so it's easy to manage all these applications. The
list is growing rapidly. Especially managing for the next run: what stays, what is just when I restart,
which doesn't stay: permanent application and non-permanent one."

And 20.9.2026, the answer to that last sentence: "we are removing all applications which are persistent.
I am choosing what is persistent. What I open stays open between sessions. What I close stays closed
between sessions." The PERMANENT / FOR NOW tag is gone; opening an app is what makes it come back.

## ON / OFF at the top (v2, 19.10.2026)

The first row of the window is **STAR MONITOR ON OFF** with the version (Marko, 19.10.2026: "In the top of every
user interface, there will now be an on/off switch"). ON is lit while it runs; OFF quits the app. Closing the window
leaves it on, and the star's open (a reopen) brings the window back. v3: a **✕** at the far upper-right corner, on
the same row, closes the window only; the app stays on (Marko, 19.10.2026: "It's far upper right corner").

## What it does

- **OPEN NOW, the first section** (Marko, 17.9.2026: "before my order there should be open now and
  anything what is right now open can be rearranged"): above everything else, what is running right now,
  in an order of his own — drag a row by its handle, the arrows, or the number picks a place. The star
  menu's own first section, the settings submenu of every running app above the app list, is built in
  that same order, so whatever he puts on top is the first thing under the star. An app he has placed
  keeps its place while it is off and is back there the moment it starts again; one he has never placed
  sorts after the placed ones, so a new app appears at the end and nothing jumps by itself.
- **Every app, one row:** number in the star menu, glyph, name, folder, a green dot and "on for 1h 12m"
  while it runs, the time it ran today, in the last 7 days and all time, how many times it was started,
  START or STOP, and NEXT RUN: COMES BACK if it is open, STAYS OFF if it is not.
- **Five views:** MY ORDER (the star menu's order; drag a row by its handle, or the arrows, and the menu
  changes at once), ALPHABET, MOST RUN (TODAY, 7 DAYS or ALL TIME picks the column; a bar under the time),
  BY FOLDER (the star's five folders), RUNNING FIRST. A filter box narrows the list as he types. The view,
  the span and the refresh rate are remembered in the browser.
- **What comes back is what is open** (20.9.2026). The apps that are on when Hammerspoon stops are the
  apps that start with it again; the ones he closed stay closed. **NEXT RUN** is that reading, not a
  switch: COMES BACK while an app is on, STAYS OFF while it is not, so START and STOP here are also the
  decision about the next session. The star writes the set to `~/.config/star-running.json` at every
  START, STOP and tick, once a minute, and once more as Hammerspoon quits. The PERMANENT / FOR NOW
  button of 14.9.2026 and its `~/.config/star-permanent.json` are gone, and there is no "always on"
  either (Marko, 14.9.2026, 18:20): the Dock Switcher, the menu bar key, the Speechify splash closer and
  Ableton Assistant A1 come back only because they are open, and STOP ends that like any other app. An
  app whose start fails at the next load keeps its place in the file and is tried again the time after.
- **The time an app runs** is counted by the star itself, not by this page: once a minute, and at every
  toggle, the seconds since the last look go to today's line of every app that is on, in
  `~/.config/star-time.json`. A gap longer than three minutes (the Mac slept) counts for nobody. So the
  ledger grows whether or not this page is open.
- **ALL OFF** asks once ("SURE? ALL OFF") and then stops every app, the star's own All off.

## The shape

```
monitor.py         the server (Flask, port 8851) and the page, one file
MANTRA_STAR/apps/monitor.lua      the switch in the star: the tick starts this server and opens the page
MANTRA_STAR/star.lua              STAR.state(), STAR.command(key, what), STAR.order(keys),
                                  STAR.openOrder(keys): the API this page calls,
                                  what is open, the time ledger
~/.config/star-running.json       ["dock", "a1", ...] — what is open, so what comes back
~/.config/star-time.json          { "<key>": { "days": { "2026-09-14": 3600 }, "starts": 3, "last_start": ts, "last_stop": ts } }
~/.config/star-order.json         the order of the menu (reorder.lua, shared with the star's own Reorder page)
~/.config/star-open-order.json    OPEN NOW's order: { "open": ["a1", "monitor", …] }, his priority for what is running
~/.star_monitor/monitor.log       the server's log
```

The server owns nothing. It asks the star through the `hs` command line (`hs -c 'return
hs.json.encode(STAR.state())'`, a tenth of a second for all apps), and every START, STOP and
reorder is the star's own function, the same one the tick in the menu calls. If Hammerspoon is down the page
says so in red and shows the last list it saw.

```
GET  /                       the page
GET  /api/state              the apps with today / 7 days / all time / running since
POST /api/<key>/start        POST /api/<key>/stop
POST /api/order              { "keys": [...] }
POST /api/open-order         { "keys": [...] }  OPEN NOW's order: the running apps as he arranged them
POST /api/alloff
GET  /health                 POST /quit
```

## The rules it keeps

- Nothing starts by itself: the star's tick (or the row "Start the Star Monitor…" at the bottom of the
  menu) starts this server; its submenu stops it. The ledger is the star's and runs without it.
- No key, no network. Everything is on 127.0.0.1.

**The list is never empty** (15.9.2026). The star's last answer is kept in `~/.star_monitor/last-state.json`; when the star does not answer, the page shows that list as it last was, with the error above it. The only time the page shows fewer than all the apps is the filter by name.
