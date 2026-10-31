// Original Dungeon1 geometric artwork, MIT, 2026 ohxiaoguang contributors.
import AppKit
let size = 1024
let image = NSImage(size: NSSize(width:size,height:size))
image.lockFocus()
NSColor(calibratedRed:0.075,green:0.085,blue:0.12,alpha:1).setFill()
NSBezierPath(rect:NSRect(x:0,y:0,width:size,height:size)).fill()
let arch=NSBezierPath(roundedRect:NSRect(x:224,y:128,width:576,height:768),xRadius:272,yRadius:272)
NSColor(calibratedRed:0.62,green:0.39,blue:0.20,alpha:1).setFill(); arch.fill()
let door=NSBezierPath(roundedRect:NSRect(x:320,y:128,width:384,height:656),xRadius:184,yRadius:184)
NSColor(calibratedRed:0.13,green:0.12,blue:0.17,alpha:1).setFill(); door.fill()
NSColor(calibratedRed:0.96,green:0.77,blue:0.42,alpha:1).setFill()
NSBezierPath(rect:NSRect(x:492,y:190,width:40,height:480)).fill()
let mark=NSBezierPath(); mark.move(to:NSPoint(x:432,y:594)); mark.line(to:NSPoint(x:512,y:674)); mark.line(to:NSPoint(x:532,y:624)); mark.line(to:NSPoint(x:466,y:558)); mark.close(); mark.fill()
image.unlockFocus()
let bitmap=NSBitmapImageRep(data:image.tiffRepresentation!)!
try bitmap.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:CommandLine.arguments[1]))
