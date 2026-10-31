// SPDX-License-Identifier: MIT
import Foundation

enum ModOverlay {
    /// Accept a RomFS overlay, its enclosing folder, or the mods/ directory
    /// containing individual projects. Never copy or modify the chosen files.
    static func applying(folder: URL?, to environment: [String: String]) throws -> [String: String] {
        var result = environment
        result.removeValue(forKey: "DM_ROMFS_OVERLAY")
        guard let folder else { return result }
        let fm = FileManager.default
        func directory(_ url: URL) -> Bool {
            var isDirectory: ObjCBool = false
            return fm.fileExists(atPath: url.path, isDirectory: &isDirectory) && isDirectory.boolValue
        }
        guard directory(folder), fm.isReadableFile(atPath: folder.path) else {
            throw CocoaError(.fileReadNoSuchFile)
        }
        var root = folder
        if directory(folder.appendingPathComponent("mods")) {
            root = folder
        } else if directory(folder.appendingPathComponent("romfs")) {
            root = folder.appendingPathComponent("romfs")
        } else if folder.lastPathComponent == "mods" {
            let children = try fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)
            if children.contains(where: { fm.fileExists(atPath: $0.appendingPathComponent("project.xml").path) }) {
                root = folder.deletingLastPathComponent()
            }
        }
        let path = root.resolvingSymlinksInPath().path
        guard directory(root), fm.isReadableFile(atPath: path) else { throw CocoaError(.fileReadNoPermission) }
        // The host uses ':' as a separator and a 4096-byte root list.
        guard !path.contains(":"), path.utf8.count < 4094 else { throw CocoaError(.fileReadInvalidFileName) }
        result["DM_ROMFS_OVERLAY"] = path
        return result
    }
}
