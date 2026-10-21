import Foundation
import IOKit.hid

// Only opens Flydigi vendor HID collections; optional identity/status queries.
// No takeover, configuration or motor writes.
let query = CommandLine.arguments.contains("--query")
let manager = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
let match: [String: Any] = [kIOHIDVendorIDKey: 0x37d7, kIOHIDProductIDKey: 0x2502]
IOHIDManagerSetDeviceMatching(manager, match as CFDictionary)
let status = IOHIDManagerOpen(manager, IOOptionBits(kIOHIDOptionsTypeNone))
print(String(format: "manager_open=0x%08x", UInt32(bitPattern: status)))
let devices = IOHIDManagerCopyDevices(manager) as? Set<IOHIDDevice> ?? []
var buffers: [UnsafeMutablePointer<UInt8>] = []
var count = 0
var shown = Set<String>()
let callback: IOHIDReportCallback = { _, result, _, _, reportID, bytes, length in
    guard result == kIOReturnSuccess else { return }
    count += 1
    let hex = UnsafeBufferPointer(start: bytes, count: min(length, 64)).map { String(format: "%02x", $0) }.joined(separator: " ")
    if shown.count < 12 && shown.insert(hex).inserted {
        print("input reportID=\(reportID) length=\(length) data=\(hex)")
        fflush(stdout)
    }
}
for device in devices {
    let usage = IOHIDDeviceGetProperty(device, kIOHIDPrimaryUsagePageKey as CFString) as? Int ?? -1
    guard usage >= 0xff00 else { continue }
    let result = IOHIDDeviceOpen(device, IOOptionBits(kIOHIDOptionsTypeNone))
    print(String(format: "vendor_usage=0x%04x open=0x%08x", usage, UInt32(bitPattern: result)))
    if let descriptor = IOHIDDeviceGetProperty(device, kIOHIDReportDescriptorKey as CFString) as? Data {
        print("descriptor=" + descriptor.map { String(format: "%02x", $0) }.joined(separator: " "))
    }
    guard result == kIOReturnSuccess else { continue }
    let buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: 1024)
    buffers.append(buffer)
    IOHIDDeviceRegisterInputReportCallback(device, buffer, 1024, callback, nil)
    IOHIDDeviceScheduleWithRunLoop(device, CFRunLoopGetCurrent(), CFRunLoopMode.defaultMode.rawValue)
    if query && usage == 0xffa0 {
        for prefix: [UInt8] in [[0x5a, 0xa5, 0x01, 0x02, 0x00], [0x5a, 0xa5, 0x10]] {
            var request = prefix + [UInt8](repeating: 0, count: 32 - prefix.count)
            let sent = request.withUnsafeMutableBufferPointer {
                IOHIDDeviceSetReport(device, kIOHIDReportTypeOutput, 0, $0.baseAddress!, $0.count)
            }
            print(String(format: "query_cmd=0x%02x result=0x%08x", prefix[2], UInt32(bitPattern: sent)))
            RunLoop.current.run(until: Date().addingTimeInterval(0.3))
        }
    }
}
print(query ? "Listening for 20 seconds after identity/status queries only." : "Listening for vendor input reports for 20 seconds; no output commands sent.")
fflush(stdout)
RunLoop.current.run(until: Date().addingTimeInterval(20))
for device in devices {
    IOHIDDeviceUnscheduleFromRunLoop(device, CFRunLoopGetCurrent(), CFRunLoopMode.defaultMode.rawValue)
    IOHIDDeviceClose(device, IOOptionBits(kIOHIDOptionsTypeNone))
}
IOHIDManagerClose(manager, IOOptionBits(kIOHIDOptionsTypeNone))
buffers.forEach { $0.deallocate() }
print("reports=\(count) unique_shown=\(shown.count)")
