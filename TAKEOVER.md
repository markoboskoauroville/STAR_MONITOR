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
