// Star Monitor (Mantra): the window that runs the star. Replaces monitor.py, the page at 127.0.0.1:8851
// (Marko, 13.10.2026: "We are quitting the Lua, no more Lua, only Swift"; MANTRA_MANIFEST swift-apps.md: no web pages).
//
// Same work as the page: every app of the star with START / STOP, OPEN NOW on top in his own order, the star's
// order, the time each has run (today, 7 days, all time, from the star's ledger ~/.config/star-time.json) and the
// five views. The rows are the Swift star's table, ~/.config/star-rows.json: kind "app" is a Swift .app opened and
// quit here directly; kind "lua" rows have no hand any more (v5, 13.11.2026: no Hammerspoon, no `hs`): they show off and
// wait for their Swift version.
//
// ONE WRITER (STAR_SWIFT LESSONS 5): this window writes the two order files and the running set itself (v5, 13.11.2026:
// no Hammerspoon to ask); it never counts time (that is the Swift star's clock).
import SwiftUI
import AppKit

let VERSION = 5
let RELEASES = "https://github.com/markoboskoauroville/STAR_MONITOR/releases/latest"
let HOME = NSHomeDirectory()
let CONF = HOME + "/.config"
let ROWS_FILE = CONF + "/star-rows.json"
let ORDER_FILE = CONF + "/star-order.json"
let OPEN_FILE = CONF + "/star-open-order.json"
let RUNNING_FILE = CONF + "/star-running.json"
let TIME_FILE = CONF + "/star-time.json"
let GROUPS_FILE = CONF + "/star-groups.json"

let GREEN = Color(red: 0x33/255, green: 0xD1/255, blue: 0x7A/255)
let GREY = Color(red: 0x7A/255, green: 0x80/255, blue: 0x87/255)
let AMBER = Color(red: 0xE8/255, green: 0xA3/255, blue: 0x3D/255)
let INK = Color(red: 0x0B/255, green: 0x0D/255, blue: 0x10/255)
let LINE = Color(white: 1, opacity: 0.06)

// MARK: files

func readJSON(_ path: String) -> Any? {
    guard let d = FileManager.default.contents(atPath: path) else { return nil }
    return try? JSONSerialization.jsonObject(with: d)
}
func writeJSON(_ obj: Any, _ path: String) {
    try? FileManager.default.createDirectory(atPath: CONF, withIntermediateDirectories: true)
    if let d = try? JSONSerialization.data(withJSONObject: obj, options: [.prettyPrinted, .sortedKeys]) {
        try? d.write(to: URL(fileURLWithPath: path), options: .atomic)
    }
}

// MARK: the apps

struct Row: Codable { var key: String; var name: String; var group: String?; var kind: String; var app: String?; var about: String? }
struct RowsFile: Codable { var folders: [String]?; var rows: [Row] }

struct Times { var today = 0.0, week = 0.0, total = 0.0, starts = 0, since = 0.0 }

func dur(_ s: Double) -> String {
    let m = Int(s / 60)
    if s < 60 { return s > 0 ? "<1m" : "—" }
    if m < 60 { return "\(m)m" }
    let h = m / 60
    if h < 24 { return "\(h)h \(m % 60)m" }
    return "\(h / 24)d \(h % 24)h"
}

final class Monitor: ObservableObject {
    @Published var rows: [Row] = []
    @Published var folders: [String] = []
    @Published var on: [String: Bool] = [:]
    @Published var times: [String: Times] = [:]
    @Published var openOrder: [String] = []
    @Published var busy: Set<String> = []
    @Published var said = ""
    private var timer: Timer?
    private var asking = false

    init() {
        load(); refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { [weak self] _ in self?.refresh() }
    }

    func load() {
        guard let d = FileManager.default.contents(atPath: ROWS_FILE), let f = try? JSONDecoder().decode(RowsFile.self, from: d) else {
            said = "no row table at ~/.config/star-rows.json: build Star (Mantra) once (STAR_SWIFT build.sh)"; return
        }
        var r = f.rows; folders = f.folders ?? []
        if let o = readJSON(ORDER_FILE) as? [String: Any], let keys = o["order"] as? [String] {
            var rank: [String: Int] = [:]
            for (i, k) in keys.enumerated() where rank[k] == nil { rank[k] = i }
            let base = Dictionary(uniqueKeysWithValues: r.enumerated().map { ($1.key, $0) })
            r.sort { (rank[$0.key] ?? 10000 + base[$0.key]!) < (rank[$1.key] ?? 10000 + base[$1.key]!) }
        }
        rows = r
        openOrder = ((readJSON(OPEN_FILE) as? [String: Any])?["open"] as? [String]) ?? []
    }

    func bundleID(_ r: Row) -> String? { r.app.flatMap { Bundle(url: URL(fileURLWithPath: NSString(string: $0).expandingTildeInPath))?.bundleIdentifier } }
    func runningApps(_ r: Row) -> [NSRunningApplication] { bundleID(r).map { NSRunningApplication.runningApplications(withBundleIdentifier: $0) } ?? [] }
    func usable(_ r: Row) -> Bool { r.kind == "app" && (r.app.map { FileManager.default.fileExists(atPath: NSString(string: $0).expandingTildeInPath) } ?? false) }
    func group(_ r: Row) -> String {
        if let g = (readJSON(GROUPS_FILE) as? [String: Any])?[r.key] as? String, !g.isEmpty { return g }
        return r.group ?? "Other"
    }

    func refresh() {
        guard !asking else { return }
        asking = true
        let rows = self.rows
        DispatchQueue.global().async {
            DispatchQueue.main.async {
                self.asking = false
                var on: [String: Bool] = [:]
                for r in rows { on[r.key] = r.kind == "app" && !self.runningApps(r).isEmpty }
                self.on = on
                self.readTimes()
                let o = ((readJSON(OPEN_FILE) as? [String: Any])?["open"] as? [String]) ?? self.openOrder
                if o != self.openOrder { self.openOrder = o }
            }
        }
    }

    // the star's ledger: { key: { days: { "YYYY-MM-DD": s }, starts, last_start, last_stop } }
    func readTimes() {
        let L = (readJSON(TIME_FILE) as? [String: Any]) ?? [:]
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"
        let cal = Calendar.current
        let today = f.string(from: Date())
        let week = Set((0..<7).map { f.string(from: cal.date(byAdding: .day, value: -$0, to: Date())!) })
        let now = Date().timeIntervalSince1970
        var t: [String: Times] = [:]
        for r in rows {
            let e = L[r.key] as? [String: Any] ?? [:]
            let days = e["days"] as? [String: Any] ?? [:]
            func n(_ v: Any?) -> Double { (v as? NSNumber)?.doubleValue ?? 0 }
            var x = Times()
            x.today = n(days[today])
            x.week = days.filter { week.contains($0.key) }.reduce(0) { $0 + n($1.value) }
            x.total = days.values.reduce(0) { $0 + n($1) }
            x.starts = (e["starts"] as? NSNumber)?.intValue ?? 0
            if on[r.key] ?? false, let ls = (e["last_start"] as? NSNumber)?.doubleValue, ls > 0 { x.since = max(0, now - ls) }
            t[r.key] = x
        }
        times = t
    }

    // START or STOP, then the right owner writes down what is open
    func toggle(_ r: Row) {
        guard usable(r), !busy.contains(r.key) else { return }
        let wasOn = on[r.key] ?? false
        busy.insert(r.key)
        if r.kind == "app" {
            if wasOn {
                let apps = runningApps(r); apps.forEach { $0.terminate() }
                DispatchQueue.main.asyncAfter(deadline: .now() + 4) { apps.filter { !$0.isTerminated }.forEach { $0.forceTerminate() } }
            } else if let p = r.app {
                let c = NSWorkspace.OpenConfiguration(); c.activates = false
                NSWorkspace.shared.openApplication(at: URL(fileURLWithPath: NSString(string: p).expandingTildeInPath), configuration: c) { _, err in
                    if let err = err { DispatchQueue.main.async { self.said = "\(r.name) did not open: \(err.localizedDescription)" } }
                }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                self.rememberHere()
                self.busy.remove(r.key); self.refresh()
            }
        }
    }
    // what is open stays open; a Lua row's wish is kept until its Swift version exists
    func rememberHere() {
        let before = Set((readJSON(RUNNING_FILE) as? [String]) ?? [])
        writeJSON(rows.filter { $0.kind == "app" ? (on[$0.key] ?? false) || !runningApps($0).isEmpty : before.contains($0.key) }.map { $0.key }, RUNNING_FILE)
    }

    func allOff() {
        let list = rows.filter { on[$0.key] ?? false }
        said = "stopping \(list.count) apps…"
        DispatchQueue.global().async {
            for r in list {
                if r.kind == "app" { DispatchQueue.main.sync { self.runningApps(r).forEach { $0.terminate() } } }
            }
            Thread.sleep(forTimeInterval: 1.5)
            DispatchQueue.main.async {
                writeJSON([String](), RUNNING_FILE)
                self.said = "all off"; self.refresh()
            }
        }
    }

    // MY ORDER: one place up or down, written by the star (it rebuilds its menu), or here when it is gone
    func move(_ key: String, by d: Int) {
        var keys = rows.map { $0.key }
        guard let i = keys.firstIndex(of: key), i + d >= 0, i + d < keys.count else { return }
        keys.swapAt(i, i + d)
        let byKey = Dictionary(uniqueKeysWithValues: rows.map { ($0.key, $0) })
        rows = keys.compactMap { byKey[$0] }
        DispatchQueue.global().async { writeJSON(["order": keys], ORDER_FILE) }
    }

    // OPEN NOW: the running apps in his order; an app that is off keeps its slot (star.lua M.openOrder)
    var openNow: [Row] {
        let rank = Dictionary(openOrder.enumerated().map { ($1, $0) }, uniquingKeysWith: { a, _ in a })
        let base = Dictionary(uniqueKeysWithValues: rows.enumerated().map { ($1.key, $0) })
        return rows.filter { on[$0.key] ?? false }.sorted { (rank[$0.key] ?? 10000 + base[$0.key]!) < (rank[$1.key] ?? 10000 + base[$1.key]!) }
    }
    func moveOpen(_ key: String, by d: Int) {
        var want = openNow.map { $0.key }
        guard let i = want.firstIndex(of: key), i + d >= 0, i + d < want.count else { return }
        want.swapAt(i, i + d)
        let seen = Set(want)
        var out: [String] = [], taken = Set<String>(), n = 0
        for k in openOrder {
            if seen.contains(k) { out.append(want[n]); taken.insert(want[n]); n += 1 }
            else if !taken.contains(k) { out.append(k); taken.insert(k) }
        }
        for k in want[n...] where !taken.contains(k) { out.append(k); taken.insert(k) }
        openOrder = out
        DispatchQueue.global().async { writeJSON(["open": out], OPEN_FILE) }
    }
}

// MARK: the window

struct Word: View {
    let text: String; let on: Bool; var dim = false; let action: () -> Void
    var body: some View {
        Text(text).font(.system(size: 12, weight: .bold, design: .monospaced)).foregroundColor(on ? GREEN : dim ? GREY.opacity(0.4) : GREY)
            .padding(.horizontal, 5).padding(.vertical, 3).contentShape(Rectangle()).onTapGesture(perform: action)
    }
}

// ✕ at the far upper-right corner closes the window only; the app stays ON (Marko, 19.10.2026: "please unify the
// position of the close button on every application. It's far upper right corner.")
struct CloseX: View {
    var body: some View {
        Image(systemName: "xmark").font(.system(size: 14, weight: .semibold)).foregroundColor(GREY)
            .frame(width: 28, height: 28).contentShape(Rectangle())
            .onTapGesture { NSApp.keyWindow?.performClose(nil) }
            .help("close the window; Star Monitor stays on")
    }
}

enum View_: String, CaseIterable { case order = "MY ORDER", alpha = "ALPHABET", most = "MOST RUN", folder = "BY FOLDER", running = "RUNNING FIRST" }
enum Span: String, CaseIterable { case today = "TODAY", week = "7 DAYS", all = "ALL TIME" }

struct AppRow: View {
    @ObservedObject var m: Monitor
    let r: Row; let place: Int; let span: Span; let arrows: ((Int) -> Void)?
    var body: some View {
        let on = m.on[r.key] ?? false, t = m.times[r.key] ?? Times()
        HStack(spacing: 10) {
            Text("\(place)").frame(width: 24, alignment: .trailing).foregroundColor(GREY)
            if let a = arrows {
                HStack(spacing: 0) { Word(text: "▲", on: false) { a(-1) }; Word(text: "▼", on: false) { a(1) } }
            }
            Circle().fill(on ? GREEN : Color(white: 0.25)).frame(width: 9, height: 9)
            VStack(alignment: .leading, spacing: 1) {
                Text(r.name).font(.system(size: 13, weight: .semibold)).foregroundColor(.white).lineLimit(1)
                Text(on ? "on for \(dur(t.since))" : (r.kind == "lua" ? "Lua · " : "Swift · ") + m.group(r))
                    .font(.system(size: 10, design: .monospaced)).foregroundColor(on ? GREEN.opacity(0.8) : GREY)
            }.frame(width: 250, alignment: .leading)
            Text(dur(t.today)).frame(width: 64, alignment: .trailing).foregroundColor(span == .today ? AMBER : GREY)
            Text(dur(t.week)).frame(width: 64, alignment: .trailing).foregroundColor(span == .week ? AMBER : GREY)
            Text(dur(t.total)).frame(width: 72, alignment: .trailing).foregroundColor(span == .all ? AMBER : GREY)
            Text("\(t.starts)×").frame(width: 44, alignment: .trailing).foregroundColor(GREY)
            Spacer()
            Text(on ? "COMES BACK" : "STAYS OFF").font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundColor(on ? GREEN.opacity(0.8) : GREY.opacity(0.7)).frame(width: 86, alignment: .trailing)
            Word(text: m.busy.contains(r.key) ? "…" : on ? "STOP" : "START", on: !on && m.usable(r), dim: !m.usable(r)) { m.toggle(r) }
                .frame(width: 60, alignment: .trailing)
        }
        .font(.system(size: 12, design: .monospaced))
        .padding(.vertical, 5).padding(.horizontal, 8)
        .background(LINE.opacity(place % 2 == 0 ? 1 : 0))
        .help(r.about ?? "")
    }
}

struct MonitorView: View {
    @ObservedObject var m: Monitor
    @AppStorage("view") var view = View_.order.rawValue
    @AppStorage("span") var span = Span.week.rawValue
    @AppStorage("onTop") private var onTop = false
    @State var filter = ""

    var shown: [Row] {
        let f = filter.lowercased()
        let list = m.rows.filter { f.isEmpty || $0.name.lowercased().contains(f) || ($0.about ?? "").lowercased().contains(f) || m.group($0).lowercased().contains(f) }
        let sp = Span(rawValue: span) ?? .week
        func val(_ r: Row) -> Double { let t = m.times[r.key] ?? Times(); return sp == .today ? t.today : sp == .week ? t.week : t.total }
        let idx = Dictionary(uniqueKeysWithValues: m.rows.enumerated().map { ($1.key, $0) })
        func on(_ r: Row) -> Int { (m.on[r.key] ?? false) ? 0 : 1 }
        switch View_(rawValue: view) ?? .order {
        case .order: return list
        case .alpha: return list.sorted { $0.name.lowercased() < $1.name.lowercased() }
        case .most: return list.sorted { val($0) > val($1) }
        case .running: return list.sorted { (on($0), idx[$0.key] ?? 0) < (on($1), idx[$1.key] ?? 0) }
        case .folder:
            let order = m.folders
            return list.sorted { (order.firstIndex(of: m.group($0)) ?? 99, idx[$0.key] ?? 0) < (order.firstIndex(of: m.group($1)) ?? 99, idx[$1.key] ?? 0) }
        }
    }
    func place(_ r: Row) -> Int { (m.rows.firstIndex { $0.key == r.key } ?? 0) + 1 }
    func head(_ s: String) -> some View {
        Text(s).font(.system(size: 10, weight: .bold, design: .monospaced)).foregroundColor(GREY).padding(.top, 6)
    }

    var body: some View {
        let sp = Span(rawValue: span) ?? .week
        VStack(alignment: .leading, spacing: 10) {
            // the first row is ON / OFF (Marko, 19.10.2026: "In the top of every user interface, there will now be an
            // on/off switch"; MANTRA_MANIFEST swift-apps.md). Running is ON; OFF quits the window and its timer.
            HStack(spacing: 4) {
                Text("STAR MONITOR").font(.system(size: 11, weight: .bold, design: .monospaced)).foregroundColor(GREY)
                Word(text: "ON", on: true) {}
                Word(text: "OFF", on: false) { NSApp.terminate(nil) }
                    .axButton("Off", id: "off") { DispatchQueue.main.async { NSApp.terminate(nil) } }
                Spacer()
                Text("v\(VERSION)").font(.system(size: 11, design: .monospaced)).foregroundColor(GREY)
                    .onTapGesture { NSWorkspace.shared.open(URL(string: RELEASES)!) }
                // v4: TOP beside ✕ (Marko, 31.10.2026: "On, off and top. Please build it in every application"):
                // green = the window stays above every other window; remembered in "onTop", applied at launch
                Word(text: "TOP", on: onTop) { onTop.toggle(); floatMonitor(onTop) }
                    .axButton("Top", id: "top", value: onTop ? "on" : "off") { onTop.toggle(); floatMonitor(onTop) }
                    .help("Always on top: green, the window stays above every other window")
                CloseX()
                    .axButton("Close window", id: "close") { (NSApp.keyWindow ?? NSApp.windows.first { $0.isVisible })?.performClose(nil) }
            }
            .onAppear { DispatchQueue.main.async { floatMonitor(onTop) } }
            HStack {
                Text("\(m.on.values.filter { $0 }.count) of \(m.rows.count) on").font(.system(size: 15, weight: .bold, design: .monospaced)).foregroundColor(AMBER)
                Spacer()
                if m.rows.contains(where: { $0.kind == "lua" }) { Text("a Lua row waits for its Swift version").font(.system(size: 11, design: .monospaced)).foregroundColor(AMBER) }
                Word(text: "ALL OFF", on: false) { m.allOff() }
            }
            HStack(spacing: 0) {
                ForEach(View_.allCases, id: \.self) { v in Word(text: v.rawValue, on: view == v.rawValue) { view = v.rawValue } }
                Spacer()
                ForEach(Span.allCases, id: \.self) { s in Word(text: s.rawValue, on: span == s.rawValue) { span = s.rawValue } }
            }
            TextField("filter", text: $filter).textFieldStyle(.plain).font(.system(size: 13, design: .monospaced))
                .padding(6).background(Color(white: 0.12)).cornerRadius(4)
            HStack(spacing: 10) {
                Text("").frame(width: 24 + 9 + 250 + 20)
                Text("TODAY").frame(width: 64, alignment: .trailing); Text("7 DAYS").frame(width: 64, alignment: .trailing)
                Text("ALL TIME").frame(width: 72, alignment: .trailing); Text("STARTS").frame(width: 44, alignment: .trailing)
                Spacer(); Text("NEXT RUN").frame(width: 86, alignment: .trailing); Text("").frame(width: 60)
            }.font(.system(size: 9, weight: .bold, design: .monospaced)).foregroundColor(GREY).padding(.horizontal, 8)
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    if !m.openNow.isEmpty && filter.isEmpty {
                        head("OPEN NOW, IN YOUR ORDER")
                        ForEach(Array(m.openNow.enumerated()), id: \.element.key) { i, r in
                            AppRow(m: m, r: r, place: i + 1, span: sp, arrows: { d in m.moveOpen(r.key, by: d) })
                        }
                        head("EVERY APP · " + (View_(rawValue: view) ?? .order).rawValue)
                    }
                    ForEach(shown, id: \.key) { r in
                        if (View_(rawValue: view) ?? .order) == .folder, shown.first(where: { m.group($0) == m.group(r) })?.key == r.key {
                            head(m.group(r).uppercased())
                        }
                        AppRow(m: m, r: r, place: place(r), span: sp,
                               arrows: (View_(rawValue: view) ?? .order) == .order && filter.isEmpty ? { d in m.move(r.key, by: d) } : nil)
                    }
                }
            }
            HStack {
                Text(m.said).font(.system(size: 11, design: .monospaced)).foregroundColor(GREY).lineLimit(1)
                Spacer()
            }
        }
        .padding(.horizontal, 20).padding(.bottom, 20).padding(.top, 8).padding(.trailing, -12).frame(minWidth: 900, minHeight: 560).background(INK).preferredColorScheme(.dark)
    }
}

// v4: TOP lifts every Star Monitor window above the others (.floating) or lets it back (.normal)
func floatMonitor(_ on: Bool) {
    for w in NSApp.windows where w.title.hasPrefix("Star Monitor") { w.level = on ? .floating : .normal }
}

// v4: every control of the first row is an Accessibility button (MANTRA_MANIFEST swift-apps.md, "Accessibility built in")
extension View {
    func axButton(_ label: String, id: String, value: String? = nil, _ action: @escaping () -> Void) -> some View {
        accessibilityElement(children: .ignore)
            .accessibilityLabel(label)
            .accessibilityIdentifier(id)
            .accessibilityValue(value ?? "")
            .accessibilityAddTraits(.isButton)
            .accessibilityAction(.default, action)
    }
}

final class Delegate: NSObject, NSApplicationDelegate {
    // closing the window leaves it ON; the star's open (a reopen) brings the window back (Marko, 19.10.2026)
    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { false }
    func applicationShouldHandleReopen(_ s: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag, let w = s.windows.first(where: { $0.canBecomeMain }) { w.makeKeyAndOrderFront(nil); s.activate(ignoringOtherApps: true); return false }
        return true   // no window left: SwiftUI's WindowGroup makes a new one
    }
}

@main struct StarMonitor: App {
    @NSApplicationDelegateAdaptor(Delegate.self) var delegate
    @StateObject var m = Monitor()
    var body: some Scene { WindowGroup("Star Monitor (Mantra)") { MonitorView(m: m) } }
}
