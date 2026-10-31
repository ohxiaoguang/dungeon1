// SPDX-License-Identifier: MIT
// Shared presentation only: no resource scan, game settings or storage mutation.
import SwiftUI
#if os(macOS)
import AppKit
#else
import UIKit
#endif

struct DungeonProjectIcon: View {
    private var path: String? {
        Bundle.main.url(forResource: "project-icon", withExtension: "png", subdirectory: "dm")?.path
            ?? Bundle.main.url(forResource: "project-icon", withExtension: "png")?.path
    }
    var body: some View {
        #if os(macOS)
        if let path, let image = NSImage(contentsOfFile: path) {
            Image(nsImage: image).resizable().scaledToFit().accessibilityLabel("Dungeon1")
        } else { Image(systemName: "lantern.fill").resizable().scaledToFit().accessibilityLabel("Dungeon1") }
        #else
        if let path, let image = UIImage(contentsOfFile: path) {
            Image(uiImage: image).resizable().scaledToFit().accessibilityLabel("Dungeon1")
        } else { Image(systemName: "lantern.fill").resizable().scaledToFit().accessibilityLabel("Dungeon1") }
        #endif
    }
}

struct AboutDungeon1View: View {
    @EnvironmentObject private var language: LanguagePreferences
    @Environment(\.dismiss) private var dismiss
    private var chinese: Bool { language.language.resolved == .simplifiedChinese }
    private func t(_ en: String, _ zh: String) -> String { chinese ? zh : en }
    private func value(_ key: String) -> String { Bundle.main.object(forInfoDictionaryKey: key) as? String ?? "—" }
    private let home = "https://github.com/ohxiaoguang/dungeon1"

    var body: some View {
        #if os(macOS)
        VStack(spacing: 0) {
            content
            Divider()
            HStack { Spacer(); done.keyboardShortcut(.defaultAction) }.padding(16)
        }
        .frame(width: 600, height: 650)
        #else
        NavigationStack {
            content
                .navigationTitle(t("About Dungeon1", "关于 Dungeon1"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { done } }
        }
        #endif
    }

    private var done: some View { Button(t("Done", "完成")) { dismiss() }.accessibilityIdentifier("dungeon1.about.done") }
    private var content: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack(alignment: .center, spacing: 18) {
                    DungeonProjectIcon().frame(width: 88, height: 88)
                    VStack(alignment: .leading, spacing: 5) {
                        Text("Dungeon1").font(.largeTitle.bold())
                        Text(t("Version", "版本") + " " + value("CFBundleShortVersionString")
                             + " · " + t("Build", "构建") + " " + value("CFBundleVersion"))
                            .font(.callout).foregroundStyle(.secondary)
                    }
                }
                Text(t("Dungeon1 is an unofficial port adaptation based on nxnative, bringing the Nintendo Switch version of Darkest Dungeon to Apple silicon Mac, iPhone and iPad.",
                       "Dungeon1 是基于 nxnative 开发的非官方移植适配项目，用于在 Apple silicon Mac、iPhone 和 iPad 上运行 Nintendo Switch 版本的《暗黑地牢》。"))
                VStack(alignment: .leading, spacing: 10) {
                    Text(t("Supported game", "支持信息")).font(.headline)
                    Text("Darkest Dungeon · Nintendo Switch · 1.3.0")
                    Text("macOS / iOS / iPadOS").foregroundStyle(.secondary)
                    Text(t("Five DLC resource packs can be loaded. The Color of Madness shop has verified native Shards purchases on the Mac host; complete DLC campaigns are not claimed as tested.",
                           "可加载五项 DLC 资源。疯狂之色商店已有 Mac Host 原生碎片购买验证；不代表全部 DLC 剧情与玩法均已完成验收。"))
                        .font(.callout)
                }
                VStack(alignment: .leading, spacing: 12) {
                    Text(t("Project and open source", "项目与开源信息")).font(.headline)
                    projectLink("Dungeon1 · GitHub", home, "house")
                    projectLink("nxnative · seedds", "https://github.com/seedds/nxnative", "chevron.left.forwardslash.chevron.right")
                    projectLink(t("MIT license", "MIT 许可证"), home + "/blob/main/LICENSE", "doc.text")
                    projectLink(t("Third-party notices", "第三方声明"), home + "/blob/main/THIRD_PARTY_NOTICES.md", "doc.on.doc")
                    projectLink(t("DLC and validation details", "DLC 与验收详情"), home + "/blob/main/docs/dlc.md", "checkmark.seal")
                }
                Text(t("Based on seedds/nxnative and its contributors. Retained components include Ryujinx / Spv.Generator, libvpx, stb_vorbis and others with their own licenses. The project code's MIT grant does not replace those terms or the icon's separate usage notice.",
                       "基于 seedds/nxnative 及其贡献者的代码。保留的 Ryujinx / Spv.Generator、libvpx、stb_vorbis 等组件各有许可；项目代码的 MIT 不替代其条款或图标的单独使用说明。"))
                    .font(.footnote).foregroundStyle(.secondary)
                Divider()
                Text(t("Unofficial community project; not a Red Hook Studios product and not affiliated with Nintendo or Apple. This source project does not supply the game, updates, DLC or keys.",
                       "非官方社区项目，并非 Red Hook Studios 官方产品，与 Nintendo、Apple 无官方关联。源码项目不提供游戏本体、更新包、DLC 或密钥。"))
                    .font(.footnote).foregroundStyle(.secondary)
            }
            .frame(maxWidth: 680, alignment: .leading)
            .padding(24)
            .frame(maxWidth: .infinity)
            .textSelection(.enabled)
        }
        .background(.background)
        .accessibilityIdentifier("dungeon1.about.content")
    }
    private func projectLink(_ title: String, _ destination: String, _ symbol: String) -> some View {
        Link(destination: URL(string: destination)!) { Label(title, systemImage: symbol).fixedSize(horizontal: false, vertical: true) }
    }
}
