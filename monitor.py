#!/usr/bin/env python3
"""
STAR MONITOR, a page at http://127.0.0.1:8851 that manages every app of the star menu.

Marko's request, 14.9.2026: "build a star monitor, the application in a web interface which
starts and stops all applications. I can manage them, I can start, I can stop. I can also reorder
them in that view, which are most important will go to the top. Track how much time I'm running
some applications, and in a sorting order give me top, by alphabet, by application, so it's easy
to manage all these applications. The list is growing rapidly. Especially managing for the next
run: what stays, what is just when I restart, which doesn't stay: permanent application and
non-permanent one."

WHERE THE TRUTH IS: the star itself (MANTRA_STAR/star.lua, inside Hammerspoon). This server owns
nothing; it asks the star through the `hs` command line, which answers in a tenth of a second:
    STAR.state()                 every app: key, name, glyph, folder, order, running, permanent
    STAR.command(key, what)      start | stop | permanent | fornow
    STAR.order({keys})           the whole order after a drag
    STAR.openOrder({keys})       OPEN NOW's order: the running apps as he arranged them
and it reads the time ledger the star writes once a minute, ~/.config/star-time.json:
    { "<key>": { "days": { "2026-09-14": 3600 }, "starts": 3, "last_start": ts, "last_stop": ts } }

PERMANENT AND FOR NOW: a permanent app is started at every load of the star; an app that is for
now runs until it is stopped or Hammerspoon quits, and does not come back. The set is
~/.config/star-permanent.json, written by the star at this page's word. There is no "always on"
any more (Marko, 14.9.2026, 18:20): the permanent tag is the one rule, on every app alike.

    monitor.py                   the server, in the foreground (the star starts it detached)
    GET  /                       the page
    GET  /api/state              the apps, with today / 7 days / all time / running since
    POST /api/<key>/start        start one app (the star's own start(), a few seconds for a server)
    POST /api/<key>/stop         stop one app
    POST /api/<key>/permanent    { "on": true|false }   permanent, or for now
    POST /api/order              { "keys": [...] }      the new order of the star menu
    POST /api/alloff             stop every app
    GET  /health                 200 when up
    POST /quit                   stop the server

The page asks /api/state every five seconds (a setting on the page, kept in the browser) and
never while a row is being dragged. Views: MY ORDER (drag a row, or the arrows), ALPHABET,
MOST RUN (today, 7 days, all time), BY FOLDER, RUNNING FIRST. A filter box narrows the list as
he types. Nothing here needs the network or a key.
"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import date, timedelta

from flask import Flask, Response, jsonify, request

HOME = os.path.expanduser("~")
HS = "/opt/homebrew/bin/hs"
PORT = 8851
TIME_FILE = os.path.join(HOME, ".config", "star-time.json")
STATE_DIR = os.path.join(HOME, ".star_monitor")

app = Flask(__name__)
LOCK = threading.Lock()          # one question to the star at a time
CACHE = {"at": 0.0, "state": None}


# ---------------------------------------------------------------- the star
def ask_star(lua, timeout=25):
    """Run one Lua line inside Hammerspoon and return (ok, text). The hs tool prints the returned
    value; a Lua error comes back with exit code 65 and the message, a dead Hammerspoon with a
    connection error. Serialised: the star is one thread and so is this."""
    with LOCK:
        try:
            r = subprocess.run([HS, "-t", str(timeout), "-c", lua],
                               capture_output=True, text=True, timeout=timeout + 5)
        except FileNotFoundError:
            return False, "the hs command line is not installed (Hammerspoon > hs.ipc.cliInstall)"
        except subprocess.TimeoutExpired:
            return False, "the star did not answer in %d seconds" % timeout
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        return False, out or err or ("hs exited %d" % r.returncode)
    # Hammerspoon prints its console lines first (hotkey: Disabled hotkey ⌃` … when an app stops, MEASURED
    # 14.9.2026, 18:30) and the returned value last: the answer is the last line
    lines = [ln for ln in out.split("\n") if ln.strip()]
    return True, (lines[-1].strip() if lines else "")


def star_json(lua):
    ok, text = ask_star(lua)
    if not ok:
        return None, text
    try:
        return json.loads(text), None
    except ValueError:
        return None, "the star answered something that is not JSON: " + text[:200]


def star_state(fresh=False):
    """The star's view of every app, cached for a moment so a burst of requests asks once."""
    now = time.time()
    if not fresh and CACHE["state"] is not None and now - CACHE["at"] < 1.5:
        return CACHE["state"], None
    st, err = star_json("return hs.json.encode(STAR.state())")
    if st is None:
        return None, err
    if not isinstance(st, dict) or not isinstance(st.get("apps"), list):
        return None, "the star has no STAR.state(): restart Hammerspoon so the new star.lua loads"
    CACHE["state"], CACHE["at"] = st, now
    remember_state(st)
    return st, None


# THE LIST IS NEVER EMPTY (Marko, 15.9.2026: "the list is empty. It should always show all my apps"). The
# last answer of the star is kept on disk; when the star does not answer, the page shows that list with
# the error above it, every row as it last was, instead of nothing.
LAST_FILE = os.path.join(STATE_DIR, "last-state.json")


def remember_state(st):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(LAST_FILE, "w") as f:
            json.dump(st, f)
    except OSError:
        pass


def last_state():
    try:
        with open(LAST_FILE) as f:
            st = json.load(f)
        return st if isinstance(st, dict) and isinstance(st.get("apps"), list) else None
    except (OSError, ValueError):
        return None


def star_command(key, what):
    ok, res = ask_star('return hs.json.encode({STAR.command(%s, %s)})' % (json.dumps(key), json.dumps(what)))
    CACHE["state"] = None
    if not ok:
        return False, res
    try:
        pair = json.loads(res)
        return bool(pair[0]), str(pair[1]) if len(pair) > 1 else ""
    except (ValueError, IndexError, TypeError):
        return False, "the star answered: " + res[:200]


# ---------------------------------------------------------------- the ledger
def read_ledger():
    try:
        with open(TIME_FILE) as f:
            t = json.load(f)
        return t if isinstance(t, dict) else {}
    except (OSError, ValueError):
        return {}


def times_of(entry, running, now):
    """today, the last seven days, all time, in seconds; starts; since (seconds running now)."""
    entry = entry if isinstance(entry, dict) else {}
    days = entry.get("days")
    if not isinstance(days, dict):
        days = {}
    today = date.today()
    week_keys = {(today - timedelta(days=i)).isoformat() for i in range(7)}
    tod = float(days.get(today.isoformat(), 0) or 0)
    week = sum(float(v or 0) for k, v in days.items() if k in week_keys)
    total = sum(float(v or 0) for v in days.values())
    since = 0
    ls = entry.get("last_start")
    if running and isinstance(ls, (int, float)) and ls > 0:
        since = max(0, int(now - ls))
    return {
        "today": int(tod), "week": int(week), "total": int(total),
        "starts": int(entry.get("starts") or 0), "since": since,
        "last_stop": entry.get("last_stop"), "last_start": ls,
    }


def full_state(fresh=False):
    st, err = star_state(fresh)
    now = time.time()
    if st is None:
        st = last_state()
        if st is None:
            return {"error": err, "apps": [], "time": now}
        err = "the star did not answer (" + err + "); this is the list as it last was"
    ledger = read_ledger()
    apps = []
    for a in st["apps"]:
        a = dict(a)
        a.update(times_of(ledger.get(a["key"]), a.get("running"), now))
        apps.append(a)
    return {"apps": apps, "folders": st.get("folders", True), "groups": st.get("groups", []),
            "open_order": st.get("open_order", []), "time": now, "error": err}


# ---------------------------------------------------------------- the routes
@app.route("/health")
def health():
    return "ok"


@app.route("/api/state")
def api_state():
    return jsonify(full_state(fresh=request.args.get("fresh") == "1"))


@app.route("/api/<key>/<what>", methods=["POST"])
def api_command(key, what):
    if what == "permanent":
        body = request.get_json(silent=True) or {}
        what = "permanent" if body.get("on", True) else "fornow"
    if what not in ("start", "stop", "permanent", "fornow"):
        return jsonify({"ok": False, "msg": "unknown command"}), 400
    ok, msg = star_command(key, what)
    return jsonify({"ok": ok, "msg": msg, "state": full_state(fresh=True)})


@app.route("/api/order", methods=["POST"])
def api_order():
    body = request.get_json(silent=True) or {}
    keys = body.get("keys")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        return jsonify({"ok": False, "msg": "keys must be a list of strings"}), 400
    lua = "return hs.json.encode({STAR.order(hs.json.decode(%s))})" % json.dumps(json.dumps(keys))
    ok, res = ask_star(lua)
    CACHE["state"] = None
    return jsonify({"ok": ok, "msg": res if not ok else "ordered", "state": full_state(fresh=True)})


# OPEN NOW (Marko, 17.9.2026: "before my order there should be open now and anything what is right now
# open can be rearranged"). The page sends the running apps in the order he wants them; the star keeps the
# list and builds its own first section from it.
@app.route("/api/open-order", methods=["POST"])
def api_open_order():
    body = request.get_json(silent=True) or {}
    keys = body.get("keys")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        return jsonify({"ok": False, "msg": "keys must be a list of strings"}), 400
    lua = "return hs.json.encode({STAR.openOrder(hs.json.decode(%s))})" % json.dumps(json.dumps(keys))
    ok, res = ask_star(lua)
    if not ok and "openOrder" in str(res):
        res = "the star has no STAR.openOrder(): restart Hammerspoon so the new star.lua loads"
    CACHE["state"] = None
    return jsonify({"ok": ok, "msg": res if not ok else "open now is in this order", "state": full_state(fresh=True)})


@app.route("/api/alloff", methods=["POST"])
def api_alloff():
    ok, res = ask_star("STAR.allOff(); return 'all off'", timeout=60)
    CACHE["state"] = None
    return jsonify({"ok": ok, "msg": res, "state": full_state(fresh=True)})


@app.route("/quit", methods=["POST"])
def quit_server():
    threading.Timer(0.3, lambda: os._exit(0)).start()
    return "bye"


# THE ICON: the David star of the menu bar, two equilateral triangles at 60 % white on the page's dark ground
# (Marko, 14.9.2026, 18:10: "all my pages should have icons; Star Monitor doesn't have any; make it David star")
FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect width="64" height="64" rx="14" fill="#151517"/>'
    '<g fill="none" stroke="#ffffff" stroke-opacity="0.6" stroke-width="3.6" stroke-linejoin="round">'
    '<path d="M32 9 L52.8 45 L11.2 45 Z"/><path d="M32 55 L11.2 19 L52.8 19 Z"/></g></svg>'
)


@app.route("/favicon.svg")
@app.route("/favicon.ico")
def favicon():
    return Response(FAVICON, mimetype="image/svg+xml")


@app.route("/")
def page():
    return Response(PAGE, mimetype="text/html")


# ---------------------------------------------------------------- the page
PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Star Monitor</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
  :root { color-scheme: dark; }
  html, body { margin: 0; background: #151517; color: #e8e8e8; font: 14px/1.4 -apple-system, "Helvetica Neue", sans-serif; }
  body { padding: 18px 22px 40px; -webkit-user-select: none; }
  h1 { font-size: 20px; font-weight: 600; margin: 0; color: #fff; letter-spacing: .2px; }
  h1 .star { color: rgba(255,255,255,.6); margin-right: 8px; }
  .sub { color: #8e8e93; font-size: 12.5px; margin: 3px 0 14px; }
  .bar { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; margin-bottom: 14px; }
  .seg { display: inline-flex; background: #1f1f22; border: 1px solid #2c2c2e; border-radius: 9px; overflow: hidden; }
  .seg button { background: none; border: 0; color: #b5b5ba; padding: 6px 11px; font: 12.5px -apple-system, sans-serif; cursor: pointer; letter-spacing: .3px; }
  .seg button:hover { color: #fff; background: #26262a; }
  .seg button.on { background: #3a3a40; color: #fff; }
  .seg button.on.today, .seg button.on.week, .seg button.on.total { background: #2f4a6a; }
  input.filter { background: #1f1f22; border: 1px solid #2c2c2e; border-radius: 9px; color: #fff; padding: 6px 10px; font: 13px -apple-system, sans-serif; width: 190px; }
  input.filter:focus { outline: none; border-color: #4a6fa5; }
  .spacer { flex: 1; }
  .count { color: #8e8e93; font-size: 12.5px; }
  .count b { color: #4cd964; font-weight: 600; }
  .danger { background: #2a1d1d; border: 1px solid #5a2a2a; color: #ff6b6b; border-radius: 9px; padding: 6px 11px; font: 12.5px -apple-system, sans-serif; cursor: pointer; }
  .danger:hover { background: #3a2222; }
  .danger.sure { background: #7a2a2a; color: #fff; border-color: #a33; }
  .danger[disabled] { opacity: .35; cursor: default; }
  table { border-collapse: collapse; width: 100%; }
  th { text-align: left; color: #6e6e73; font-size: 11px; font-weight: 600; letter-spacing: .6px; text-transform: uppercase; padding: 4px 8px 8px; border-bottom: 1px solid #2c2c2e; }
  th.r, td.r { text-align: right; }
  td { padding: 7px 8px; border-top: 1px solid #222225; vertical-align: middle; white-space: nowrap; }
  tr:first-child td { border-top: 0; }
  tr.row { transition: background .15s; }
  tr.row:hover { background: #1c1c1f; }
  tr.row.dragging { opacity: .35; }
  tr.row.over-top td { border-top: 2px solid #4a8cff; }
  tr.row.over-bottom td { border-bottom: 2px solid #4a8cff; }
  tr.head td { padding: 14px 8px 4px; color: #8e8e93; font-size: 11.5px; font-weight: 600; letter-spacing: .6px; text-transform: uppercase; border-top: 0; }
  td.n { width: 28px; text-align: right; color: #6e6e73; font-variant-numeric: tabular-nums; }
  td.h { width: 18px; color: #48484c; cursor: grab; font-size: 15px; text-align: center; }
  td.h:hover { color: #9a9a9e; }
  td.g { width: 28px; text-align: center; font-size: 16px; opacity: .5; }
  tr.on td.g { opacity: 1; }
  td.name { white-space: normal; min-width: 180px; }
  td.name .nm { color: #f2f2f2; font-weight: 500; }
  tr.on td.name .nm { color: #fff; }
  td.name .desc { display: block; color: #6e6e73; font-size: 11.5px; margin-top: 1px; white-space: normal; }
  td.name .tag { display: inline-block; margin-left: 8px; color: #8e8e93; background: #232326; border-radius: 5px; padding: 0 6px; font-size: 10.5px; vertical-align: 1px; }
  td.st { width: 130px; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #48484c; margin-right: 7px; vertical-align: 0; }
  tr.on .dot { background: #4cd964; box-shadow: 0 0 6px #4cd96488; }
  .since { color: #8e8e93; font-size: 12px; }
  tr.on .since { color: #cfd; }
  td.t { width: 78px; font-variant-numeric: tabular-nums; color: #b5b5ba; }
  td.t.big { color: #fff; font-weight: 500; }
  td.t .meter { display: block; height: 3px; background: #2f4a6a; border-radius: 2px; margin-top: 3px; }
  td.t .zero { color: #48484c; }
  td.act { width: 92px; text-align: right; }
  td.perm { width: 108px; text-align: right; }
  td.mv { width: 46px; text-align: right; white-space: nowrap; }
  button.b { border: 1px solid #3a3a3c; background: #232326; color: #e8e8e8; border-radius: 7px; padding: 4px 10px; font: 12px -apple-system, sans-serif; cursor: pointer; min-width: 62px; letter-spacing: .3px; }
  button.b:hover { background: #2c2c30; border-color: #4a4a4e; }
  button.b.start { color: #4cd964; border-color: #2e5c3a; }
  button.b.start:hover { background: #1f3a27; }
  button.b.stop { color: #ff7b72; border-color: #5a2f2c; }
  button.b.stop:hover { background: #3a2321; }
  button.b.busy { color: #8e8e93; border-color: #3a3a3c; cursor: default; }
  button.b.always { color: #6e6e73; border-color: #2c2c2e; cursor: default; }
  button.pill { border: 1px solid #3a3a3c; background: #1f1f22; color: #8e8e93; border-radius: 12px; padding: 3px 10px; font: 11.5px -apple-system, sans-serif; cursor: pointer; min-width: 96px; letter-spacing: .4px; }
  button.pill.permanent { color: #f7c948; border-color: #6b5a20; background: #2a2510; }
  button.pill.permanent:hover { background: #3a3315; }
  button.pill.fornow:hover { color: #fff; background: #26262a; }
  button.pill.locked { cursor: default; opacity: .8; }
  button.arrow { border: 0; background: none; color: #6e6e73; cursor: pointer; font-size: 12px; padding: 2px 3px; }
  button.arrow:hover { color: #fff; }
  button.arrow[disabled] { opacity: .2; cursor: default; }
  .foot { margin-top: 16px; color: #6e6e73; font-size: 12px; display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }
  .foot select { background: #1f1f22; color: #ddd; border: 1px solid #2c2c2e; border-radius: 6px; padding: 2px 5px; font: 12px -apple-system, sans-serif; }
  .err { background: #3a1e1e; border: 1px solid #6a2a2a; color: #ffb4b0; border-radius: 9px; padding: 10px 14px; margin-bottom: 14px; white-space: pre-wrap; }
  .msg { color: #8e8e93; font-size: 12px; min-height: 16px; margin: 0 0 8px; }
  .legend { color: #6e6e73; font-size: 12px; margin-top: 8px; }
  .legend b { color: #f7c948; font-weight: 500; }
  /* OPEN NOW, the first section (17.9.2026) */
  .open { border: 1px solid #2c2c2e; border-radius: 12px; background: #151517; padding: 12px 14px; margin: 0 0 14px; }
  .open h2 { margin: 0 0 3px; font: 600 12px -apple-system, sans-serif; letter-spacing: .09em; color: #f7c948; text-transform: uppercase; }
  .open .why { color: #6e6e73; font-size: 12px; margin: 0 0 10px; line-height: 1.45; }
  .open ol { list-style: none; margin: 0; padding: 0; }
  .open li { display: flex; align-items: center; gap: 10px; padding: 7px 9px; margin-bottom: 6px; border-radius: 8px;
             background: #1b1b1e; border: 1px solid #232326; }
  .open li:last-child { margin-bottom: 0; }
  .open li.dragging { opacity: .35; }
  .open li.over-top { box-shadow: inset 0 2px 0 #f7c948; }
  .open li.over-bottom { box-shadow: inset 0 -2px 0 #f7c948; }
  .open .h { cursor: grab; color: #55555a; letter-spacing: -2px; }
  .open .n { color: #6e6e73; font-size: 12px; width: 16px; text-align: right; }
  .open .gl { width: 18px; text-align: center; }
  .open .nm { flex: 1; color: #f2f2f4; }
  .open .gear { color: #55555a; font-size: 11px; }
  .open .when { color: #6e6e73; font-size: 12px; }
  .open select { background: #1f1f22; color: #ddd; border: 1px solid #2c2c2e; border-radius: 6px; padding: 2px 4px; font: 12px -apple-system, sans-serif; }
  .open .none { color: #6e6e73; font-size: 12px; }
  @media (max-width: 760px) { td.name .desc { display: none; } th.t7, td.t7, th.tall, td.tall { display: none; } }
</style></head><body>
<h1><span class="star">✡</span>Star Monitor</h1>
<div class="sub">Every app of the star: start, stop, put the important ones on top, and say which come back after a restart.</div>
<div id="err" class="err" hidden></div>
<div id="opennow" class="open"></div>
<div class="bar">
  <div class="seg" id="views">
    <button data-view="order">MY ORDER</button>
    <button data-view="alpha">ALPHABET</button>
    <button data-view="top">MOST RUN</button>
    <button data-view="folder">BY FOLDER</button>
    <button data-view="running">RUNNING FIRST</button>
  </div>
  <div class="seg" id="spans">
    <button data-span="today" class="today">TODAY</button>
    <button data-span="week" class="week">7 DAYS</button>
    <button data-span="total" class="total">ALL TIME</button>
  </div>
  <input class="filter" id="filter" placeholder="filter by name…" autocomplete="off">
  <div class="spacer"></div>
  <span class="count" id="count"></span>
  <button class="danger" id="alloff">ALL OFF</button>
</div>
<div class="msg" id="msg"></div>
<table>
  <thead><tr id="thead"></tr></thead>
  <tbody id="rows"></tbody>
</table>
<div class="legend"><b>PERMANENT</b> comes back at every start of the star. <span style="color:#b5b5ba">FOR NOW</span> runs until you stop it or Hammerspoon quits, and stays off after a restart. The star adds a minute of running time to every app that is on, once a minute; a sleeping Mac counts nothing.</div>
<div class="foot">
  <span>refresh every <select id="every"><option value="2">2 s</option><option value="5" selected>5 s</option><option value="10">10 s</option><option value="30">30 s</option><option value="0">never</option></select></span>
  <span id="asked"></span>
</div>
<script>
(function () {
  var S = { apps: [], openOrder: [], view: 'order', span: 'today', filter: '', busy: {}, dragging: null, odragging: null, timer: null, every: 5, sure: null };
  try {
    S.view = localStorage.getItem('sm.view') || 'order';
    S.span = localStorage.getItem('sm.span') || 'today';
    S.every = parseInt(localStorage.getItem('sm.every') || '5', 10);
  } catch (e) {}
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };

  function fmt(sec) {
    sec = Math.round(sec || 0);
    if (sec <= 0) return '';
    if (sec < 60) return sec + 's';
    var m = Math.round(sec / 60);
    if (m < 60) return m + 'm';
    var h = Math.floor(m / 60); m = m % 60;
    if (h < 24) return h + 'h ' + (m < 10 ? '0' : '') + m + 'm';
    var d = Math.floor(h / 24); h = h % 24;
    return d + 'd ' + h + 'h';
  }
  function shortName(n) { var i = n.indexOf(' ('); return i > 0 ? n.slice(0, i) : n; }
  function descOf(n) { var i = n.indexOf(' ('); return i > 0 ? n.slice(i + 2).replace(/\)\s*$/, '') : ''; }

  function setView(v) { S.view = v; try { localStorage.setItem('sm.view', v); } catch (e) {} render(); }
  function setSpan(v) { S.span = v; try { localStorage.setItem('sm.span', v); } catch (e) {} render(); }

  function sorted() {
    var apps = S.apps.slice();
    var f = S.filter.trim().toLowerCase();
    if (f) apps = apps.filter(function (a) { return (a.name + ' ' + a.key + ' ' + a.group).toLowerCase().indexOf(f) >= 0; });
    var byOrder = function (a, b) { return a.order - b.order; };
    var byName = function (a, b) { return shortName(a.name).localeCompare(shortName(b.name), undefined, { sensitivity: 'base' }); };
    if (S.view === 'alpha') apps.sort(byName);
    else if (S.view === 'top') apps.sort(function (a, b) { return (b[S.span] - a[S.span]) || byName(a, b); });
    else if (S.view === 'running') apps.sort(function (a, b) { return ((b.running ? 1 : 0) - (a.running ? 1 : 0)) || byOrder(a, b); });
    else apps.sort(byOrder);
    return apps;
  }

  // OPEN NOW: what is running, in his order, above everything else (Marko, 17.9.2026)
  function openApps() {
    var rank = {};
    (S.openOrder || []).forEach(function (k, i) { rank[k] = i; });
    return S.apps.filter(function (a) { return a.running; }).sort(function (a, b) {
      var ra = rank[a.key] === undefined ? 10000 + a.order : rank[a.key];
      var rb = rank[b.key] === undefined ? 10000 + b.order : rank[b.key];
      return ra - rb;
    });
  }

  function renderOpen() {
    var on = openApps();
    var h = '<h2>Open now</h2><div class="why">What is running, in the order you want it. The first section of the star menu \u2014 the settings of every running app, above the app list \u2014 follows this order, so whatever you put on top is the first thing under the star. Drag a row by its handle, use the arrows, or pick a place from the number. An app you have placed keeps that place while it is off.</div>';
    if (!on.length) { $('opennow').innerHTML = h + '<div class="none">nothing is running</div>'; return; }
    h += '<ol id="openlist">';
    on.forEach(function (a, i) {
      var opts = '';
      for (var n = 1; n <= on.length; n++) opts += '<option value="' + n + '"' + (n === i + 1 ? ' selected' : '') + '>' + n + '</option>';
      h += '<li draggable="true" data-key="' + esc(a.key) + '">' +
        '<span class="h" title="drag to move">\u22ee\u22ee</span>' +
        '<span class="n">' + (i + 1) + '</span>' +
        '<span class="gl">' + esc(a.glyph || '') + '</span>' +
        '<span class="nm">' + esc(shortName(a.name)) + (a.settings ? ' <span class="gear" title="has a settings submenu in the star">\u2699</span>' : '') + '</span>' +
        '<span class="when">' + (a.since ? 'on for ' + fmt(a.since) : 'on') + '</span>' +
        '<button class="arrow" data-omove="-1" data-key="' + esc(a.key) + '"' + (i === 0 ? ' disabled' : '') + ' title="up">\u25b2</button>' +
        '<button class="arrow" data-omove="1" data-key="' + esc(a.key) + '"' + (i === on.length - 1 ? ' disabled' : '') + ' title="down">\u25bc</button>' +
        '<select class="opos" data-key="' + esc(a.key) + '" title="move to this place">' + opts + '</select>' +
        '</li>';
    });
    $('opennow').innerHTML = h + '</ol>';
    wireOpenDrag();
  }

  function sendOpenOrder(keys) {
    S.openOrder = keys.concat((S.openOrder || []).filter(function (k) { return keys.indexOf(k) < 0; }));
    renderOpen();
    say('reordering open now\u2026');
    post('/api/open-order', { keys: keys })
      .then(function (r) { say(r.ok ? 'open now is in this order, and so is the top of the star menu' : r.msg); take(r.state); })
      .catch(function (e) { say('failed: ' + e); });
  }

  function placeOpen(key, pos) {
    var keys = openApps().map(function (a) { return a.key; });
    var i = keys.indexOf(key), j = Math.max(0, Math.min(keys.length - 1, pos - 1));
    if (i < 0 || i === j) return;
    keys.splice(i, 1); keys.splice(j, 0, key);
    sendOpenOrder(keys);
  }

  function moveOpen(key, delta) {
    var keys = openApps().map(function (a) { return a.key; });
    var i = keys.indexOf(key);
    if (i < 0) return;
    placeOpen(key, i + 1 + delta);
  }

  function wireOpenDrag() {
    var items = document.querySelectorAll('#openlist li[draggable]');
    items.forEach(function (li) {
      li.addEventListener('dragstart', function (e) {
        S.odragging = li.dataset.key; li.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move'; try { e.dataTransfer.setData('text/plain', li.dataset.key); } catch (x) {}
      });
      li.addEventListener('dragend', function () {
        S.odragging = null; li.classList.remove('dragging');
        items.forEach(function (o) { o.classList.remove('over-top', 'over-bottom'); });
      });
      li.addEventListener('dragover', function (e) {
        if (!S.odragging || S.odragging === li.dataset.key) return;
        e.preventDefault(); e.dataTransfer.dropEffect = 'move';
        var r = li.getBoundingClientRect(), before = (e.clientY - r.top) < r.height / 2;
        li.classList.toggle('over-top', before); li.classList.toggle('over-bottom', !before);
      });
      li.addEventListener('dragleave', function () { li.classList.remove('over-top', 'over-bottom'); });
      li.addEventListener('drop', function (e) {
        e.preventDefault();
        var from = S.odragging; if (!from || from === li.dataset.key) return;
        var r = li.getBoundingClientRect(), before = (e.clientY - r.top) < r.height / 2;
        var keys = openApps().map(function (a) { return a.key; });
        keys.splice(keys.indexOf(from), 1);
        keys.splice(keys.indexOf(li.dataset.key) + (before ? 0 : 1), 0, from);
        S.odragging = null;
        sendOpenOrder(keys);
      });
    });
  }

  function render() {
    renderOpen();
    document.querySelectorAll('#views button').forEach(function (b) { b.classList.toggle('on', b.dataset.view === S.view); });
    document.querySelectorAll('#spans button').forEach(function (b) { b.classList.toggle('on', b.dataset.span === S.span); });
    var apps = sorted();
    var on = S.apps.filter(function (a) { return a.running; }).length;
    $('count').innerHTML = '<b>' + on + '</b> of ' + S.apps.length + ' on';
    $('alloff').disabled = on === 0;
    var draggable = S.view === 'order' && !S.filter.trim();
    var max = 1; apps.forEach(function (a) { max = Math.max(max, a[S.span] || 0); });
    var spanName = { today: 'today', week: '7 days', total: 'all time' };
    $('thead').innerHTML = (draggable ? '<th></th>' : '') + '<th>#</th><th></th><th>App</th><th>Status</th>' +
      '<th class="r ' + (S.span === 'today' ? 'big' : '') + '">Today</th><th class="r t7">7 days</th><th class="r tall">All time</th>' +
      '<th class="r">Starts</th><th></th><th class="r">Next run</th>' + (draggable ? '<th></th>' : '');
    var html = '', lastGroup = null;
    apps.forEach(function (a, i) {
      if (S.view === 'folder' && a.group !== lastGroup) {
        lastGroup = a.group;
        html += '<tr class="head"><td colspan="12">' + esc(a.group) + '</td></tr>';
      }
      var busy = S.busy[a.key];
      var act;
      if (busy) act = '<button class="b busy" disabled>' + esc(busy) + '</button>';
      else if (a.running) act = '<button class="b stop" data-act="stop" data-key="' + esc(a.key) + '">STOP</button>';
      else act = '<button class="b start" data-act="start" data-key="' + esc(a.key) + '">START</button>';
      var perm = a.permanent
          ? '<button class="pill permanent" data-perm="0" data-key="' + esc(a.key) + '" title="comes back at every start of the star; click to make it for now">PERMANENT</button>'
          : '<button class="pill fornow" data-perm="1" data-key="' + esc(a.key) + '" title="does not come back after a restart; click to make it permanent">FOR NOW</button>';
      var status = '<span class="dot"></span><span class="since">' + (a.running ? (a.since ? 'on for ' + fmt(a.since) : 'on') : (a.last_stop ? 'off' : 'off')) + '</span>';
      var cell = function (k, cls) {
        var v = a[k] || 0;
        var meter = (S.view === 'top' && S.span === k && v > 0) ? '<span class="meter" style="width:' + Math.max(4, Math.round(100 * v / max)) + '%"></span>' : '';
        return '<td class="t r ' + cls + (S.span === k ? ' big' : '') + '">' + (v > 0 ? fmt(v) : '<span class="zero">—</span>') + meter + '</td>';
      };
      var desc = descOf(a.name);
      html += '<tr class="row' + (a.running ? ' on' : '') + '" data-key="' + esc(a.key) + '"' + (draggable ? ' draggable="true"' : '') + '>' +
        (draggable ? '<td class="h" title="drag to move">⋮⋮</td>' : '') +
        '<td class="n">' + a.order + '</td><td class="g">' + esc(a.glyph) + '</td>' +
        '<td class="name"><span class="nm">' + esc(shortName(a.name)) + '</span>' + (S.view !== 'folder' ? '<span class="tag">' + esc(a.group) + '</span>' : '') +
        (desc ? '<span class="desc">' + esc(desc) + '</span>' : '') + '</td>' +
        '<td class="st">' + status + '</td>' + cell('today', '') + cell('week', 't7') + cell('total', 'tall') +
        '<td class="t r">' + (a.starts ? a.starts : '<span class="zero">—</span>') + '</td>' +
        '<td class="act">' + act + '</td><td class="perm">' + perm + '</td>' +
        (draggable ? '<td class="mv"><button class="arrow" data-move="-1" data-key="' + esc(a.key) + '"' + (i === 0 ? ' disabled' : '') + ' title="up">▲</button><button class="arrow" data-move="1" data-key="' + esc(a.key) + '"' + (i === apps.length - 1 ? ' disabled' : '') + ' title="down">▼</button></td>' : '') +
        '</tr>';
    });
    $('rows').innerHTML = html || '<tr><td colspan="12" style="color:#6e6e73;padding:18px 8px">nothing matches</td></tr>';
    if (draggable) wireDrag();
  }

  function say(t) { $('msg').textContent = t || ''; }
  function showErr(t) { var e = $('err'); if (t) { e.textContent = t; e.hidden = false; } else { e.hidden = true; } }

  function take(state) {
    if (!state) return;
    if (state.error) { showErr(state.error); } else { showErr(null); }
    if (state.apps && state.apps.length) S.apps = state.apps;
    if (state.open_order) S.openOrder = state.open_order;
    render();
  }

  function refresh(fresh) {
    if (S.dragging || S.odragging) return;
    var t0 = Date.now();
    fetch('/api/state' + (fresh ? '?fresh=1' : '')).then(function (r) { return r.json(); }).then(function (st) {
      take(st);
      $('asked').textContent = 'the star answered in ' + (Date.now() - t0) + ' ms';
    }).catch(function (e) { showErr('the monitor does not answer: ' + e); });
  }

  function post(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); });
  }

  function command(key, act) {
    var a = S.apps.filter(function (x) { return x.key === key; })[0];
    S.busy[key] = act === 'start' ? 'starting…' : 'stopping…'; render();
    say((act === 'start' ? 'starting ' : 'stopping ') + (a ? shortName(a.name) : key) + '…');
    post('/api/' + encodeURIComponent(key) + '/' + act).then(function (r) {
      delete S.busy[key];
      say(r.msg || '');
      take(r.state);
    }).catch(function (e) { delete S.busy[key]; say('failed: ' + e); render(); });
  }

  function permanent(key, on) {
    post('/api/' + encodeURIComponent(key) + '/permanent', { on: on }).then(function (r) { say(r.msg || ''); take(r.state); })
      .catch(function (e) { say('failed: ' + e); });
  }

  function sendOrder(keys) {
    say('reordering…');
    post('/api/order', { keys: keys }).then(function (r) { say(r.ok ? 'the star menu is in this order now' : r.msg); take(r.state); })
      .catch(function (e) { say('failed: ' + e); });
  }

  function move(key, delta) {
    var keys = S.apps.slice().sort(function (a, b) { return a.order - b.order; }).map(function (a) { return a.key; });
    var i = keys.indexOf(key), j = i + delta;
    if (i < 0 || j < 0 || j >= keys.length) return;
    keys.splice(i, 1); keys.splice(j, 0, key);
    keys.forEach(function (k, n) { var a = S.apps.filter(function (x) { return x.key === k; })[0]; if (a) a.order = n + 1; });
    render();
    sendOrder(keys);
  }

  function wireDrag() {
    var rows = document.querySelectorAll('tr.row[draggable]');
    rows.forEach(function (tr) {
      tr.addEventListener('dragstart', function (e) {
        S.dragging = tr.dataset.key; tr.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move'; try { e.dataTransfer.setData('text/plain', tr.dataset.key); } catch (x) {}
      });
      tr.addEventListener('dragend', function () {
        S.dragging = null; tr.classList.remove('dragging');
        rows.forEach(function (r) { r.classList.remove('over-top', 'over-bottom'); });
      });
      tr.addEventListener('dragover', function (e) {
        if (!S.dragging || S.dragging === tr.dataset.key) return;
        e.preventDefault(); e.dataTransfer.dropEffect = 'move';
        var r = tr.getBoundingClientRect(), before = (e.clientY - r.top) < r.height / 2;
        tr.classList.toggle('over-top', before); tr.classList.toggle('over-bottom', !before);
      });
      tr.addEventListener('dragleave', function () { tr.classList.remove('over-top', 'over-bottom'); });
      tr.addEventListener('drop', function (e) {
        e.preventDefault();
        var from = S.dragging; if (!from || from === tr.dataset.key) return;
        var r = tr.getBoundingClientRect(), before = (e.clientY - r.top) < r.height / 2;
        var keys = S.apps.slice().sort(function (a, b) { return a.order - b.order; }).map(function (a) { return a.key; });
        keys.splice(keys.indexOf(from), 1);
        var at = keys.indexOf(tr.dataset.key) + (before ? 0 : 1);
        keys.splice(at, 0, from);
        keys.forEach(function (k, n) { var a = S.apps.filter(function (x) { return x.key === k; })[0]; if (a) a.order = n + 1; });
        S.dragging = null; render(); sendOrder(keys);
      });
    });
  }

  document.body.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    if (b.dataset.view) return setView(b.dataset.view);
    if (b.dataset.span) return setSpan(b.dataset.span);
    if (b.dataset.act) return command(b.dataset.key, b.dataset.act);
    if (b.dataset.perm !== undefined) return permanent(b.dataset.key, b.dataset.perm === '1');
    if (b.dataset.move) return move(b.dataset.key, parseInt(b.dataset.move, 10));
    if (b.dataset.omove) return moveOpen(b.dataset.key, parseInt(b.dataset.omove, 10));
    if (b.id === 'alloff') {
      if (!b.classList.contains('sure')) {
        b.classList.add('sure'); b.textContent = 'SURE? ALL OFF';
        clearTimeout(S.sure); S.sure = setTimeout(function () { b.classList.remove('sure'); b.textContent = 'ALL OFF'; }, 4000);
        return;
      }
      b.classList.remove('sure'); b.textContent = 'ALL OFF'; say('stopping every app…');
      post('/api/alloff').then(function (r) { say(r.ok ? 'all off' : r.msg); take(r.state); });
    }
  });
  document.body.addEventListener('change', function (e) {
    var sel = e.target.closest('select.opos'); if (!sel) return;
    placeOpen(sel.dataset.key, parseInt(sel.value, 10));
  });
  $('filter').addEventListener('input', function () { S.filter = this.value; render(); });
  $('every').value = String(S.every);
  $('every').addEventListener('change', function () {
    S.every = parseInt(this.value, 10); try { localStorage.setItem('sm.every', this.value); } catch (e) {} schedule();
  });
  function schedule() {
    clearInterval(S.timer); S.timer = null;
    if (S.every > 0) S.timer = setInterval(function () { refresh(false); }, S.every * 1000);
  }
  refresh(true); schedule();
})();
</script></body></html>
"""


# ---------------------------------------------------------------- main
def main(argv):
    if argv[1:] == ["open"]:
        subprocess.call(["open", "-a", "Google Chrome", "http://127.0.0.1:%d" % PORT])
        return 0
    os.makedirs(STATE_DIR, exist_ok=True)
    app.run(host="127.0.0.1", port=PORT, threaded=True, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
