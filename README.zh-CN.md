# Dungeon1

[English](README.md)

Dungeon1 是基于 [seedds/nxnative](https://github.com/seedds/nxnative) 开发、独立维护的
**非官方单游戏移植适配项目**，用于在 Apple silicon Mac、iPhone 和 iPad 上运行
**Nintendo Switch 版本的《暗黑地牢》（Darkest Dungeon）**。
本构建流程不接受 PC/Steam 版文件，并非 Red Hook Studios、Nintendo 或 Apple 官方产品。

| 项目 | 当前适配基线 |
| --- | --- |
| 游戏 / 来源平台 | Darkest Dungeon / Nintendo Switch |
| 版本 / 更新编号 | **1.3.0 / v393216** |
| Title ID | `01008F1008DA6000` |
| 目标平台 | Apple silicon macOS / iOS / iPadOS，部署目标均为 26.0 |
| 应用标识 | `com.ohxiaoguang.dungeon1`，与旧版应用分开 |

## 主要功能

继承原生 ARM64 Host 重写能力，以 Metal 实现本作的 OpenGL 调用。提供单游戏启动器、
存档、外部 MOD、Mac Mouse HID / Pointer Bridge Hover 和 iPhone/iPad 虚拟手柄。
实验触控策略默认开启、可关闭：包含战斗/扎营技能长按、城镇头像长按，普通与 DLC
饰品商店短按聚焦、长按后松手执行一次原生购买。余额、库存和容量仍由游戏检查。

正式**灯笼图标**已纳入源码并作为两平台默认图标。设置内新增**关于 Dungeon1**，
显示同一图标、应用元数据版本/构建号、中英文介绍和有效的源码/许可链接，跟随系统
深浅色。[图标来源与授权](assets/app-icon/USAGE.md)单独记录，不自动套用代码 MIT。

## DLC 支持

| DLC 名称 | 内部标识 | 资源目录 / 游戏挂载名 |
| --- | --- | --- |
| The Crimson Court | `crimson_court` | `aoc/1` / `dlc0:` |
| The Shieldbreaker | `shieldbreaker` | `aoc/2` / `dlc1:` |
| The Musketeer | `musketeer` | `aoc/3` / `dlc2:` |
| The Color of Madness | `color_of_madness` | `aoc/4` / `dlc3:` |
| The Fire's Edge | `fires_edge` | `aoc/5` / `dlc4:` |

五项本地 DLC 均有 Mac Host 识别与挂载记录。疯狂之色 Comet 商店有 Mac 模拟 iPhone
输入的真实碎片扣除、入库和余额不足拒绝证据。**成功挂载不等于全部 DLC 剧情和玩法
均已完成验收。** CNMT、激活状态及限制见 [DLC 说明](docs/dlc.md)。

## 游戏资源、构建与安装

用户需自行提供合法取得的 **Switch 本体、匹配的 1.3.0 更新**、所需 DLC 和本地
`prod.keys`；仓库不下载、不提供这些内容。基础版 v0 用于准备联合 Shader 库，
不是另一项完整验收的运行版本。准备流程校验已注册 Build ID，PC/Steam 文件不能替代。

需要 Apple silicon Mac、macOS 26+、带 Metal 工具的 Xcode、XcodeGen、Python 3.12+
与 capstone/lz4/fonttools、.NET 10 及 Shader 工具，详见[构建指南](docs/building.md)：

```sh
./scripts/build-mac.sh --nsp-dir /private/game --keys /private/prod.keys \
  --work /private/work-mac --out /private/Dungeon1.app
./scripts/build-ios.sh --nsp-dir /private/game --keys /private/prod.keys \
  --work /private/work-ios --out /private/Dungeon1.ipa
```

`--prepared` 可复用经校验的程序和平台 Shader 缓存。内置模式将用户资源封装到
**私有本地** App/IPA；外置模式将容器/密钥保留在所选存储，其 DLC 和准备限制见指南。
不依赖旧仓库或 Touchline 目录。IPA 为未签名文件，需自行签名安装；Mac 本地包仅作
ad-hoc 签名，未做 Developer ID 签名或公证。操作、关于页面和存档导入见
[使用指南](docs/user-guide.md)。

## 已验证范围

用户已确认：**新版独立 Dungeon1 IPA 在 iPhone 成功安装、启动，并能与旧版应用
共存而不覆盖旧应用**。旧版的技能、普通商店和头像等真机实测作为历史证据保留，
不自动等同于所有交互在新版均重新验收。独立 Mac GUI/鼠标、Mac 模拟手机输入交易和
自动化结果分别记录，见 [A–F 验收矩阵](docs/compatibility.md)。
本轮**新 About 页的 iPhone/iPad 真机 UI**仍待确认；全部 DLC 剧情、所有 MOD 组合、
长时间游戏及所有多指/生命周期边界未作全面通过声明。

## 来源与许可证

[UPSTREAM](docs/UPSTREAM.md)记录准确来源和独立历史边界。保留 [LICENSE](LICENSE)
中的 seedds MIT 归属与[第三方声明](THIRD_PARTY_NOTICES.md)，各组件遵循自己的许可；
[AI 图标授权](assets/app-icon/USAGE.md)单独说明。这些许可不授予游戏、更新、DLC、固件或
密钥分发权。不得向公共 GitHub、Releases 或 CI 上传内置产物、程序、RomFS、派生
Shader/字体、密钥、存档、游戏截图或 MOD 原始资源。见[公开审查](docs/public-release-audit.md)。
