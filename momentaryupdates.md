# Momentary updates

Every request from Marko, word for word, before any code. Each item has a Status line.

## 13.10.2026: convert to Swift (no more Lua / web pages)

> "go through my start menu. If any app is not a Swift app, you need to convert it to a Swift app. We are quitting the Lua, no more Lua, only Swift. And everything will be in the application folder, name of the app in parentheses. Mantra ... start code conversion." (Marko, 13.10.2026, saved word for word in MANTRA_STAR momentaryupdates.md)

Marko 13.10.2026: convert to Swift (no more Lua / web pages). This page becomes a native window, "Star Monitor (Mantra).app"
in /Applications; the Python stays in the repo until Marko confirms the Swift app.

**Status:** built v1 13.10.2026: /Applications/Star Monitor (Mantra).app, signed Mantra Apps. Rows from ~/.config/star-rows.json in the star's order; START / STOP (Swift apps directly, Lua apps through STAR.command); OPEN NOW with ▲▼ (STAR.openOrder); MY ORDER ▲▼ (STAR.order); ALPHABET, MOST RUN (TODAY / 7 DAYS / ALL TIME), BY FOLDER, RUNNING FIRST; filter; ALL OFF; NEXT RUN. Checked by screenshot: 28 rows, 13 on, the ledger's times. monitor.py kept until Marko confirms.

## 19.10.2026: ON / OFF at the top of the window

> "When I select any of the apps, the user interface opens up. In the top of every user interface, there will now be an on/off switch ... If I say on, I close it's on ... When I just switch the check mark, and that's how I activate it. This is gone. Let's work like this. This is the workflow now." (Marko, 19.10.2026; the rule in MANTRA_MANIFEST modules/swift-apps.md, "ON / OFF at the top of every window")

The first row of the main window is ON / OFF; OFF stops the engine and quits; closing the window leaves the app on; the star only opens it.

**Status:** v2 built 19.10.2026: STAR MONITOR ON OFF is the first row with v2 (moved up from the bottom); OFF = NSApp.terminate; closing the window no longer quits (applicationShouldTerminateAfterLastWindowClosed false), the reopen shows the window or SwiftUI makes a new one. Checked by screenshot (opened once, quit again: it was not running). Marko to try OFF.
