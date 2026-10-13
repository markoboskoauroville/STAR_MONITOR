// The icon, drawn: the monitor's list, rows with a green dot when the app runs and a bar for the time it ran,
// under a small six-pointed star; the version under it.
import AppKit
let S: CGFloat = 1024
let version = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "1"
let img = NSImage(size: NSSize(width: S, height: S)); img.lockFocus()
let ctx = NSGraphicsContext.current!.cgContext
ctx.addPath(CGPath(roundedRect: CGRect(x: 100, y: 100, width: 824, height: 824), cornerWidth: 180, cornerHeight: 180, transform: nil))
ctx.setFillColor(NSColor(calibratedRed: 0.04, green: 0.05, blue: 0.06, alpha: 1).cgColor); ctx.fillPath()
// the star, two triangles
func tri(_ c: CGPoint, _ r: CGFloat, _ up: Bool) {
    let p = CGMutablePath()
    for i in 0..<3 {
        let a = (up ? CGFloat.pi / 2 : -CGFloat.pi / 2) + CGFloat(i) * 2 * .pi / 3
        let q = CGPoint(x: c.x + r * cos(a), y: c.y + r * sin(a))
        i == 0 ? p.move(to: q) : p.addLine(to: q)
    }
    p.closeSubpath(); ctx.addPath(p)
}
ctx.setStrokeColor(NSColor(calibratedWhite: 0.85, alpha: 1).cgColor); ctx.setLineWidth(14)
tri(CGPoint(x: 512, y: 770), 84, true); ctx.strokePath(); tri(CGPoint(x: 512, y: 770), 84, false); ctx.strokePath()
// the rows
let green = NSColor(calibratedRed: 0.2, green: 0.82, blue: 0.48, alpha: 1), amber = NSColor(calibratedRed: 0.91, green: 0.64, blue: 0.24, alpha: 1)
let rows: [(Bool, CGFloat)] = [(true, 0.85), (true, 0.6), (false, 0.4), (true, 0.3), (false, 0.15)]
for (i, r) in rows.enumerated() {
    let y = 600 - CGFloat(i) * 82
    ctx.setFillColor((r.0 ? green : NSColor(calibratedWhite: 0.3, alpha: 1)).cgColor)
    ctx.fillEllipse(in: CGRect(x: 230, y: y, width: 40, height: 40))
    ctx.addPath(CGPath(roundedRect: CGRect(x: 300, y: y + 8, width: 494, height: 24), cornerWidth: 12, cornerHeight: 12, transform: nil))
    ctx.setFillColor(NSColor(calibratedWhite: 0.18, alpha: 1).cgColor); ctx.fillPath()
    ctx.addPath(CGPath(roundedRect: CGRect(x: 300, y: y + 8, width: 494 * r.1, height: 24), cornerWidth: 12, cornerHeight: 12, transform: nil))
    ctx.setFillColor(amber.cgColor); ctx.fillPath()
}
("v" + version as NSString).draw(at: NSPoint(x: 170, y: 150), withAttributes: [.font: NSFont.systemFont(ofSize: 92, weight: .semibold), .foregroundColor: NSColor(calibratedWhite: 0.78, alpha: 1)])
img.unlockFocus()
try! NSBitmapImageRep(data: img.tiffRepresentation!)!.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "icon_1024.png"))
