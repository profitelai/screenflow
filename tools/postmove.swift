// postmove x y dx dy : posts one mouseMoved event at (x,y) carrying the given deltas (test helper)
import CoreGraphics
let a = CommandLine.arguments
let p = CGPoint(x: Double(a[1])!, y: Double(a[2])!)
let e = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left)!
e.setIntegerValueField(.mouseEventDeltaX, value: Int64(a[3])!)
e.setIntegerValueField(.mouseEventDeltaY, value: Int64(a[4])!)
e.post(tap: .cghidEventTap)
