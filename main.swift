// screenflow: one mouse across two Macs. The physical Mac owns the mouse. When the cursor
// leaves a linked display edge, input is forwarded to the other Mac, which moves its own cursor.
// Usage: screenflow <config.json> [--check] [--dry-run]
//   --check    print local displays and links, then exit
//   --dry-run  do not move, click or freeze anything; only log what would happen
// Escape pressed 3 times within 1.5 s takes the mouse back to this Mac.

import Foundation
import AppKit
import CoreGraphics
import Network

struct Ref: Codable { let machine: String; let display: String }
struct Edge: Codable { let from: Ref; let side: String; let to: Ref }
struct Config: Codable {
    let secret: String
    let port: UInt16
    let selfName: String
    let physical: String
    let machines: [String: String]
    let edges: [Edge]
    enum CodingKeys: String, CodingKey { case secret, port, physical, machines, edges; case selfName = "self" }
}
struct Disp { let name: String; let id: CGDirectDisplayID; let b: CGRect }

let args = CommandLine.arguments
// With no path given (for example a double-click in Finder), use the config.json next to the app itself.
let configPath: String = {
    if let a = args.dropFirst().first(where: { !$0.hasPrefix("--") }) { return a }
    let exeDir = URL(fileURLWithPath: args[0]).resolvingSymlinksInPath().deletingLastPathComponent().path
    return exeDir + "/config.json"
}()
let dryRun = args.contains("--dry-run")
let appDir = URL(fileURLWithPath: configPath).deletingLastPathComponent().path
// One status file per config, so a test instance never overwrites the live one.
let statusPath = (configPath as NSString).deletingPathExtension + ".status.json"
let cfg: Config = {
    do { return try JSONDecoder().decode(Config.self, from: Data(contentsOf: URL(fileURLWithPath: configPath))) }
    catch { fputs("cannot read \(configPath): \(error)\n", stderr); exit(1) }
}()
let isPhysical = cfg.selfName == cfg.physical
let secret: String = {
    if cfg.secret.hasPrefix("FILE:") {
        let p = appDir + "/" + String(cfg.secret.dropFirst(5))
        guard let t = try? String(contentsOfFile: p, encoding: .utf8), let line = t.split(separator: "\n").first, !line.isEmpty else {
            fputs("secret file missing or empty: \(p)\n", stderr); exit(1)
        }
        return String(line)
    }
    return cfg.secret
}()
var edges: [Edge] = cfg.edges   // the physical Mac's config is the single source of truth; peers receive it

func opposite(_ s: String) -> String {
    switch s { case "left": return "right"; case "right": return "left"; case "top": return "bottom"; default: return "top" }
}
func localDisplays() -> [Disp] {
    var ids = [CGDirectDisplayID](repeating: 0, count: 32); var n: UInt32 = 0
    CGGetActiveDisplayList(32, &ids, &n)
    var names: [CGDirectDisplayID: String] = [:]
    for s in NSScreen.screens {
        if let num = s.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber {
            names[CGDirectDisplayID(num.uint32Value)] = s.localizedName
        }
    }
    return (0..<Int(n)).map { i in Disp(name: names[ids[i]] ?? "display-\(ids[i])", id: ids[i], b: CGDisplayBounds(ids[i])) }
}
func outerEdge(_ p: CGPoint, _ displays: [Disp]) -> (Disp, String)? {
    for d in displays where p.y >= d.b.minY && p.y < d.b.maxY {
        if abs(p.x - d.b.minX) < 1.5 && !displays.contains(where: { $0.b.contains(CGPoint(x: p.x - 3, y: p.y)) }) { return (d, "left") }
        if p.x >= d.b.maxX - 1.5 && !displays.contains(where: { $0.b.contains(CGPoint(x: p.x + 3, y: p.y)) }) { return (d, "right") }
    }
    return nil
}
func entryPoint(_ d: Disp, side: String, frac: Double) -> CGPoint {
    let y = d.b.minY + min(max(frac, 0), 1) * (d.b.height - 1)
    return CGPoint(x: side == "left" ? d.b.minX + 1 : d.b.maxX - 2, y: y)
}
func fracOnSide(_ p: CGPoint, _ d: Disp) -> Double { (p.y - d.b.minY) / max(d.b.height, 1) }
func edgeFrom(_ machine: String, _ display: String, _ side: String) -> Edge? {
    edges.first { $0.from.machine == machine && $0.from.display == display && $0.side == side }
}
func log(_ s: String) { print("\(Date()) \(s)"); fflush(stdout) }

// ---- live state (main thread only)
var connection: NWConnection?
var authed = false                 // handshake finished on this link
var peerMachine = ""
var peerDisplays: [[String: Any]] = []
var onPeer = false                 // physical: cursor is on the other Mac
var simulating = false             // peer: the other Mac's mouse moves my cursor
var escapeTimes: [Date] = []
var pendingBuffer = Data()

func displayDicts() -> [[String: Any]] {
    localDisplays().map { ["name": $0.name, "x": Int($0.b.minX), "y": Int($0.b.minY), "w": Int($0.b.width), "h": Int($0.b.height)] }
}
func send(_ dict: [String: Any]) {
    guard let c = connection else { return }
    var d = (try? JSONSerialization.data(withJSONObject: dict)) ?? Data(); d.append(0x0A)
    c.send(content: d, completion: .contentProcessed { _ in })
}
func setAssociate(_ on: Bool) { if !dryRun { CGAssociateMouseAndMouseCursorPosition(on ? 1 : 0) } }
func warp(_ p: CGPoint) { if dryRun { log("warp \(Int(p.x)),\(Int(p.y))") } else { CGWarpMouseCursorPosition(p) } }
func postEvent(_ e: CGEvent?, _ what: String) { if dryRun { log(what) } else { e?.post(tap: .cghidEventTap) } }
func cursor() -> CGPoint { CGEvent(source: nil)?.location ?? .zero }

func writeStatus() {
    let state: [String: Any] = [
        "self": cfg.selfName, "physical": cfg.physical, "dryRun": dryRun,
        "connected": authed, "peer": peerMachine, "peerDisplays": peerDisplays,
        "localDisplays": displayDicts(), "cursor": ["x": Int(cursor().x), "y": Int(cursor().y)],
        "onPeer": onPeer, "simulating": simulating,
        "links": edges.map { ["from": "\($0.from.machine)/\($0.from.display)", "side": $0.side, "to": "\($0.to.machine)/\($0.to.display)"] },
        "updated": ISO8601DateFormatter().string(from: Date()),
    ]
    if let data = try? JSONSerialization.data(withJSONObject: state, options: [.prettyPrinted, .sortedKeys]) {
        try? data.write(to: URL(fileURLWithPath: statusPath), options: .atomic)
    }
}

// Take the mouse back here, whatever state the other Mac is in.
func takeBack(_ reason: String) {
    if onPeer { onPeer = false; setAssociate(true); log("mouse back on this Mac (\(reason))") }
    send(["t": "stop"])
}

// ---- physical side: forward input while the cursor is on the other Mac
func handleTap(_ type: CGEventType, _ event: CGEvent) -> Bool {   // returns true to swallow the event
    if type == .keyDown {
        if event.getIntegerValueField(.keyboardEventKeycode) == 53 {       // Escape
            let now = Date()
            escapeTimes = escapeTimes.filter { now.timeIntervalSince($0) < 1.5 } + [now]
            if escapeTimes.count >= 3 { escapeTimes = []; takeBack("Escape x3") }
        }
        return false                                                       // keyboard always stays local
    }
    if !onPeer {
        guard [.mouseMoved, .leftMouseDragged, .rightMouseDragged, .otherMouseDragged].contains(type) else { return false }
        if connection != nil && authed,
           let (d, side) = outerEdge(event.location, localDisplays()), let e = edgeFrom(cfg.selfName, d.name, side),
           peerDisplays.contains(where: { ($0["name"] as? String) == e.to.display }) {   // target must exist on the peer
            onPeer = true
            setAssociate(false)
            log("cursor -> \(e.to.machine) \(e.to.display) (\(opposite(side)) edge)")
            send(["t": "enter", "display": e.to.display, "side": opposite(side), "frac": fracOnSide(event.location, d)])
        }
        return false
    }
    switch type {
    case .mouseMoved, .leftMouseDragged, .rightMouseDragged, .otherMouseDragged:
        send(["t": "move", "dx": event.getIntegerValueField(.mouseEventDeltaX), "dy": event.getIntegerValueField(.mouseEventDeltaY)])
    case .leftMouseDown, .rightMouseDown, .otherMouseDown:
        send(["t": "button", "btn": Int(event.getIntegerValueField(.mouseEventButtonNumber)), "down": true])
    case .leftMouseUp, .rightMouseUp, .otherMouseUp:
        send(["t": "button", "btn": Int(event.getIntegerValueField(.mouseEventButtonNumber)), "down": false])
    case .scrollWheel:
        send(["t": "scroll", "dy": event.getIntegerValueField(.scrollWheelEventDeltaAxis1), "dx": event.getIntegerValueField(.scrollWheelEventDeltaAxis2)])
    default: break
    }
    return !dryRun   // dry-run never swallows the real mouse
}

// ---- messages
func handleMessage(_ m: [String: Any]) {
    guard let t = m["t"] as? String else { return }
    if !authed {
        // Mutual check: both sides must present the shared secret before anything else.
        // The physical side answers with "hello" (not "hello_ok") so older peer builds accept it too.
        let expected = isPhysical ? ["hello"] : ["hello", "hello_ok"]
        guard expected.contains(t), (m["secret"] as? String) == secret else {
            log("rejected connection: bad hello"); connection?.cancel(); connection = nil; return
        }
        authed = true
        peerMachine = m["machine"] as? String ?? "?"
        peerDisplays = m["displays"] as? [[String: Any]] ?? []
        log("connected to \(peerMachine), displays: \(peerDisplays.compactMap { $0["name"] as? String })")
        if isPhysical {
            let edgeList = edges.map { ["from": ["machine": $0.from.machine, "display": $0.from.display], "side": $0.side, "to": ["machine": $0.to.machine, "display": $0.to.display]] }
            send(["t": "hello", "secret": secret, "machine": cfg.selfName, "displays": displayDicts(), "edges": edgeList])
        } else if let list = m["edges"] as? [[String: Any]],
                  let data = try? JSONSerialization.data(withJSONObject: list),
                  let got = try? JSONDecoder().decode([Edge].self, from: data), !got.isEmpty {
            edges = got
            log("using \(got.count) links from \(peerMachine)")
        }
        return
    }
    switch t {
    case "hello_ok":
        peerMachine = m["machine"] as? String ?? peerMachine
        peerDisplays = m["displays"] as? [[String: Any]] ?? []
        log("connected to \(peerMachine), displays: \(peerDisplays.compactMap { $0["name"] as? String })")
    case "enter":   // the other Mac hands the cursor to one of my displays
        guard let d = localDisplays().first(where: { $0.name == (m["display"] as? String ?? "") }) else { return }
        let p = entryPoint(d, side: m["side"] as? String ?? "left", frac: m["frac"] as? Double ?? 0.5)
        if isPhysical { onPeer = false; setAssociate(true) } else { simulating = true }
        log("cursor on this Mac at \(d.name)")
        warp(p)
    case "move":
        guard simulating else { return }
        let dx = CGFloat(m["dx"] as? Int ?? 0), dy = CGFloat(m["dy"] as? Int ?? 0)
        let cur = cursor()
        let next = CGPoint(x: cur.x + dx, y: cur.y + dy)
        let displays = localDisplays()
        if let (d, side) = outerEdge(next, displays), let e = edgeFrom(cfg.selfName, d.name, side) {
            simulating = false
            log("cursor back to \(e.to.machine) (\(opposite(side)) edge)")
            send(["t": "enter", "display": e.to.display, "side": opposite(side), "frac": fracOnSide(next, d)])
            return
        }
        var target = next
        if !displays.contains(where: { $0.b.contains(next) }), let cd = displays.first(where: { $0.b.contains(cur) }) {
            target = CGPoint(x: min(max(next.x, cd.b.minX), cd.b.maxX - 1), y: min(max(next.y, cd.b.minY), cd.b.maxY - 1))
        }
        warp(target)
        postEvent(CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: target, mouseButton: .left), "move \(Int(target.x)),\(Int(target.y))")
    case "button":
        guard simulating else { return }
        let btn = CGMouseButton(rawValue: UInt32(m["btn"] as? Int ?? 0)) ?? .left
        let down = m["down"] as? Bool ?? false
        let type: CGEventType = btn == .left ? (down ? .leftMouseDown : .leftMouseUp)
            : btn == .right ? (down ? .rightMouseDown : .rightMouseUp) : (down ? .otherMouseDown : .otherMouseUp)
        postEvent(CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: cursor(), mouseButton: btn), "button \(btn.rawValue) \(down ? "down" : "up")")
    case "scroll":
        guard simulating else { return }
        postEvent(CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2,
                          wheel1: Int32(m["dy"] as? Int ?? 0), wheel2: Int32(m["dx"] as? Int ?? 0), wheel3: 0), "scroll")
    case "stop":
        if simulating { simulating = false; log("control returned to \(peerMachine)") }
    default: break
    }
}

func receiveLoop(_ c: NWConnection) {
    c.receive(minimumIncompleteLength: 1, maximumLength: 65536) { data, _, isComplete, error in
        if let data = data, !data.isEmpty {
            pendingBuffer.append(data)
            while let nl = pendingBuffer.firstIndex(of: 0x0A) {
                let line = pendingBuffer.subdata(in: pendingBuffer.startIndex..<nl)
                pendingBuffer.removeSubrange(pendingBuffer.startIndex...nl)
                if let obj = try? JSONSerialization.jsonObject(with: line) as? [String: Any] { handleMessage(obj) }
            }
        }
        if isComplete || error != nil {
            c.cancel()
            if connection === c {
                log("link to \(peerMachine.isEmpty ? "the other Mac" : peerMachine) closed")
                connection = nil; authed = false; peerMachine = ""; peerDisplays = []
                takeBack("link closed")
                simulating = false
            }
            return
        }
        receiveLoop(c)
    }
}
func attach(_ c: NWConnection) { connection = c; pendingBuffer = Data(); receiveLoop(c) }

func startPhysicalSide() {
    guard let listener = try? NWListener(using: .tcp, on: NWEndpoint.Port(rawValue: cfg.port)!) else {
        fputs("cannot listen on \(cfg.port)\n", stderr); exit(1)
    }
    listener.newConnectionHandler = { c in
        if connection != nil { c.cancel(); return }   // one peer at a time
        c.start(queue: .main); attach(c)
    }
    listener.start(queue: .main)
    log("waiting for the other Mac on port \(cfg.port) (physical mouse owner: \(cfg.selfName))")
}

func connectToPhysical() {
    guard let host = cfg.machines[cfg.physical] else { fputs("no host for \(cfg.physical)\n", stderr); exit(1) }
    let c = NWConnection(host: NWEndpoint.Host(host), port: NWEndpoint.Port(rawValue: cfg.port)!, using: .tcp)
    c.stateUpdateHandler = { state in
        switch state {
        case .ready:
            log("link up to \(cfg.physical), checking the shared secret")
            attach(c)
            send(["t": "hello", "secret": secret, "machine": cfg.selfName, "displays": displayDicts()])
        case .failed(let err):
            log("cannot reach \(cfg.physical): \(err)")
            fallthrough
        case .cancelled:
            if connection === c { connection = nil; authed = false }
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) { if connection == nil { connectToPhysical() } }
        default: break
        }
    }
    c.start(queue: .main)
}

if args.contains("--check") {
    print("self: \(cfg.selfName)   physical mouse owner: \(cfg.physical)")
    print("local displays:")
    for d in localDisplays() { print("  \(d.name)  \(Int(d.b.minX)),\(Int(d.b.minY))  \(Int(d.b.width))x\(Int(d.b.height))") }
    print("links from this machine:")
    for e in cfg.edges where e.from.machine == cfg.selfName { print("  \(e.from.display) \(e.side) -> \(e.to.machine) \(e.to.display)") }
    exit(0)
}

_ = AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true] as CFDictionary)
Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in writeStatus() }

if isPhysical {
    startPhysicalSide()
    let types: [CGEventType] = [.mouseMoved, .leftMouseDragged, .rightMouseDragged, .otherMouseDragged,
                                .leftMouseDown, .leftMouseUp, .rightMouseDown, .rightMouseUp,
                                .otherMouseDown, .otherMouseUp, .scrollWheel, .keyDown]
    let mask: CGEventMask = types.reduce(0) { $0 | (1 << $1.rawValue) }
    guard let tap = CGEvent.tapCreate(tap: .cgSessionEventTap, place: .headInsertEventTap, options: .defaultTap,
                                      eventsOfInterest: mask, callback: { _, type, event, _ in
        if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput { return Unmanaged.passUnretained(event) }
        return handleTap(type, event) ? nil : Unmanaged.passUnretained(event)
    }, userInfo: nil) else {
        fputs("cannot create event tap: grant Accessibility and Input Monitoring permission.\n", stderr); exit(1)
    }
    CFRunLoopAddSource(CFRunLoopGetMain(), CFMachPortCreateRunLoopSource(nil, tap, 0), .commonModes)
    CGEvent.tapEnable(tap: tap, enable: true)
} else {
    connectToPhysical()
}
log(dryRun ? "running in dry-run mode" : "running")
RunLoop.main.run()
