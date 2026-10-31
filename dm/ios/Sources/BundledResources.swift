// SPDX-License-Identifier: MIT
import Foundation

/// Whether an embedded-mode App still has everything the host will read, judged by the host's own paths.
///
/// main.m resolves the RomFS before any UI (`romfs_locate`: `Documents/romfs` first, then the App's own `romfs`, each
/// counting only when it holds the game profile's `romfs_marker`) and exports the root it chose as `DM_ROMFS`; the GL
/// layer reads `DM_MSL_DIR`. The launcher accepts these same roots. The marker must be exported as a C string:
/// passing an NSString object to setenv corrupted it and made this check fail even with a complete bundled RomFS.
///
/// Nothing here scans, versions or selects files: that is external mode's job. A missing piece is still reported, so
/// an App that really cannot start says which part is gone instead of looking healthy.
enum BundledResources {
    static let missingGameFiles = "This App does not contain the game files (romfs). Install the IPA again."
    static let missingShaders = "This App does not contain its Shader library (msl). Install the IPA again."

    /// -> nil when the host would find its files, else the message naming what is missing.
    static func problem(environment: [String: String], documents: String, bundle: String) -> String? {
        let marker = environment["DM_ROMFS_MARKER"] ?? ""
        guard romfsRoots(environment: environment, documents: documents, bundle: bundle)
            .contains(where: { holdsGameFiles($0, marker: marker) }) else { return missingGameFiles }
        guard let msl = shaderRoot(environment: environment, bundle: bundle), holdsShaderLibrary(msl) else {
            return missingShaders
        }
        return nil
    }

    /// The roots the host accepts, the one it already resolved first. Empty strings are skipped so a caller that
    /// could not read a path cannot match by accident.
    static func romfsRoots(environment: [String: String], documents: String, bundle: String) -> [String] {
        var roots: [String] = []
        if let resolved = environment["DM_ROMFS"], !resolved.isEmpty { roots.append(resolved) }
        if !documents.isEmpty { roots.append(documents + "/romfs") }
        if !bundle.isEmpty { roots.append(bundle + "/romfs") }
        return roots
    }

    /// A root counts only when it is a directory holding the profile's marker — the same test `romfs_locate` makes.
    /// With no marker known (a profile without one, which the build script refuses) the directory itself is enough.
    static func holdsGameFiles(_ root: String, marker: String) -> Bool {
        let fm = FileManager.default
        var isDirectory: ObjCBool = false
        guard fm.fileExists(atPath: root, isDirectory: &isDirectory), isDirectory.boolValue else { return false }
        return marker.isEmpty || fm.fileExists(atPath: root + "/" + marker)
    }

    /// `DM_MSL_DIR` is what the GL layer reads (<App>/msl, set by main.m); the bundle path is the fallback.
    static func shaderRoot(environment: [String: String], bundle: String) -> String? {
        if let msl = environment["DM_MSL_DIR"], !msl.isEmpty { return msl }
        return bundle.isEmpty ? nil : bundle + "/msl"
    }

    /// Every backend writes a metallib into its own sub-folder (gl/vk/b-<chain>), so one anywhere under the root is
    /// what the host needs; the exact folder is the build's business, not the launcher's.
    static func holdsShaderLibrary(_ folder: String) -> Bool {
        FileManager.default.enumerator(atPath: folder)?
            .contains { ($0 as? String)?.hasSuffix(".metallib") == true } ?? false
    }
}
