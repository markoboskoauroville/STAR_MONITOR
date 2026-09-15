# STAR_MONITOR, the page that manages the star

**One page, http://127.0.0.1:8851, for every app of the star menu: start, stop, put the important ones on top, see how long each has run, and say which come back after a restart.**

Marko's request, 14.9.2026: "build a star monitor, the application in a web interface which starts and
stops all applications. I can manage them, I can start, I can stop. I can also reorder them in that view,
which are most important will go to the top. Track how much time I'm running some applications, and in a
sorting order give me top, by alphabet, by application, so it's easy to manage all these applications. The
list is growing rapidly. Especially managing for the next run: what stays, what is just when I restart,
which doesn't stay: permanent application and non-permanent one."

## What it does

- **Every app, one row:** number in the star menu, glyph, name, folder, a green dot and "on for 1h 12m"
  while it runs, the time it ran today, in the last 7 days and all time, how many times it was started,
  START or STOP, and PERMANENT or FOR NOW.
- **Five views:** MY ORDER (the star menu's order; drag a row by its handle, or the arrows, and the menu
  changes at once), ALPHABET, MOST RUN (TODAY, 7 DAYS or ALL TIME picks the column; a bar under the time),
  BY FOLDER (the star's five folders), RUNNING FIRST. A filter box narrows the list as he types. The view,
  the span and the refresh rate are remembered in the browser.
- **Permanent and for now.** A permanent app is started at every load of the star, ticked or not when
  Hammerspoon quit. An app that is for now runs until it is stopped or Hammerspoon quits, and stays off
  after a restart. The set is `~/.config/star-permanent.json`. There is no "always on" any more (Marko,
  14.9.2026, 18:20: "we don't need that, now we have the permanent tag"): the Dock Switcher, the menu bar key,
  the Speechify splash closer and Ableton Assistant A1 are permanent like any other app, and can be stopped or
  made FOR NOW like any other. Until 14.9.2026 the star
  brought back whatever was ticked when it quit; the first time the permanent file is missing it is filled
  from those ticks, so nothing changed by itself on the day this arrived.
- **The time an app runs** is counted by the star itself, not by this page: once a minute, and at every
  toggle, the seconds since the last look go to today's line of every app that is on, in
  `~/.config/star-time.json`. A gap longer than three minutes (the Mac slept) counts for nobody. So the
  ledger grows whether or not this page is open.
- **ALL OFF** asks once ("SURE? ALL OFF") and then stops every app, the star's own All off.

## The shape

    monitor.py         the server (Flask, port 8851) and the page, one file
    MANTRA_STAR/apps/monitor.lua      the switch in the star: the tick starts this server and opens the page
    MANTRA_STAR/star.lua              STAR.state(), STAR.command(key, what), STAR.order(keys): the API this page calls,
                                      the permanent set, the time ledger
    ~/.config/star-permanent.json     { "permanent": ["dock", "a1", ...] }
    ~/.config/star-time.json          { "<key>": { "days": { "2026-09-14": 3600 }, "starts": 3, "last_start": ts, "last_stop": ts } }
    ~/.config/star-order.json         the order of the menu (reorder.lua, shared with the star's own Reorder page)
    ~/.star_monitor/monitor.log       the server's log

The server owns nothing. It asks the star through the `hs` command line (`hs -c 'return
hs.json.encode(STAR.state())'`, a tenth of a second for all apps), and every START, STOP, PERMANENT and
reorder is the star's own function, the same one the tick in the menu calls. If Hammerspoon is down the page
says so in red and shows the last list it saw.

    GET  /                       the page
    GET  /api/state              the apps with today / 7 days / all time / running since
    POST /api/<key>/start        POST /api/<key>/stop
    POST /api/<key>/permanent    { "on": true|false }
    POST /api/order              { "keys": [...] }
    POST /api/alloff
    GET  /health                 POST /quit

## The rules it keeps

- Nothing starts by itself: the star's tick (or the row "Start the Star Monitor…" at the bottom of the
  menu) starts this server; its submenu stops it. The ledger is the star's and runs without it.
- No key, no network. Everything is on 127.0.0.1.

**The list is never empty** (15.9.2026). The star's last answer is kept in `~/.star_monitor/last-state.json`; when the star does not answer, the page shows that list as it last was, with the error above it. The only time the page shows fewer than all the apps is the filter by name.
