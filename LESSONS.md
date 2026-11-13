# LESSONS — Star Monitor

1. **The star is the only truth; the page owns nothing.** Every START, STOP and reorder is
   the star's own function, called through the `hs` command line, so the page and the menu can never
   disagree. Measured 14.9.2026: `hs -c` with all 26 `running()` checks answers in 93 ms; a trivial
   line in 7 ms. One lock around the call: the star is one thread.

2. **Count the running time in the star, not in the page.** A page that is closed counts nothing. The
   star already looks at every app once a minute to remember the ticks; the same look feeds the ledger.
   One reading of `running()` per minute, used twice.

3. **A gap is not running time.** The minute timer does not fire while the Mac sleeps; the next tick sees
   hours since the last look. Anything over three minutes is dropped, so a night of sleep does not become
   a night of use.

4. **"Remembered" was replaced by a tag on 14.9.2026, and the tag was taken out again on 20.9.2026.**
   For six days what came back was `~/.config/star-permanent.json`, set on this page, and what he ticked
   was only a record — so ticking an app on and restarting lost it. Marko: "I am choosing what is
   persistent. What I open stays open between sessions. What I close stays closed between sessions." A
   second list of what should be running is a second truth, and someone has to keep it true; his own open
   and close already say everything the tag said. The page keeps the column as a reading, NEXT RUN, so the
   rule is visible without being a third thing to set.

5. **A Lua error through `hs` comes back with exit code 65 and the message on stdout,** not stderr; a
   star without the new functions says "attempt to call a nil value (field 'state')". The page turns that
   into "restart Hammerspoon so the new star.lua loads" instead of a blank list.

6. **An empty list was never the page's fault, and the page must not show one.** (15.9.2026) The list came
   up empty because the star itself was dead: Hammerspoon's main thread sat in hs.task's exit handler,
   reading to the end of a pipe that the shell which had started monitor.py still held (MANTRA_STAR
   LESSONS 24; `sample` and `lsof` found it, killing the subshell freed the star). The `hs` timeout of
   25 s under one lock then made every request wait half a minute for nothing. Two things changed: the
   shell the star spawns drops its pipes first (spawn.lua), and the page keeps the star's last answer in
   ~/.star_monitor/last-state.json and shows it, with the error above, when the star is silent.


## 13.11.2026

- 13.11.2026: a public unpromoted repo has no README and no description; what it is lives in TAKEOVER.
