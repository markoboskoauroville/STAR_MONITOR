# LESSONS — Star Monitor

1. **The star is the only truth; the page owns nothing.** Every START, STOP, reorder and PERMANENT is
   the star's own function, called through the `hs` command line, so the page and the menu can never
   disagree. Measured 14.9.2026: `hs -c` with all 26 `running()` checks answers in 93 ms; a trivial
   line in 7 ms. One lock around the call: the star is one thread.

2. **Count the running time in the star, not in the page.** A page that is closed counts nothing. The
   star already looks at every app once a minute to remember the ticks; the same look feeds the ledger.
   One reading of `running()` per minute, used twice.

3. **A gap is not running time.** The minute timer does not fire while the Mac sleeps; the next tick sees
   hours since the last look. Anything over three minutes is dropped, so a night of sleep does not become
   a night of use.

4. **Permanent replaces "remembered", with a migration.** The old rule brought back whatever was ticked;
   the new file is filled from that list the first time it is missing, so the day the rule changed nothing
   changed by itself. An always-on or on-by-default app is permanent whatever the file says.

5. **A Lua error through `hs` comes back with exit code 65 and the message on stdout,** not stderr; a
   star without the new functions says "attempt to call a nil value (field 'state')". The page turns that
   into "restart Hammerspoon so the new star.lua loads" instead of a blank list.
