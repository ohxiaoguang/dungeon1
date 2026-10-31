# Dungeon1

[English](README.md)

Dungeon1 是仅维护《暗黑地牢》1.3.0 的独立社区项目，面向 Apple silicon
macOS、iOS 和 iPadOS。游戏 Title ID 为 `01008F1008DA6000`，更新版本为
v393216。项目基于 [seedds/nxnative](https://github.com/seedds/nxnative)：
对 Apple 内核不兼容部分进行重写后执行游戏 ARM64 程序，以 Metal 实现本作
的桌面 OpenGL 调用。本项目与 Red Hook Studios、Nintendo、Apple 无官方关系。

## 功能

- 专用 Dungeon1 单游戏启动器，无需选择 Title ID。应用标识为
  `com.ohxiaoguang.dungeon1`，可与旧应用共存。
- iOS 战斗、扎营技能短按聚焦与长按操作，城镇右侧英雄头像长按；保留原有
  虚拟手柄、控制器设置、触摸取消、多指和输入所有权隔离。
- 普通 Nomad Wagon 与 DLC/Comet 饰品商店均支持短按聚焦和 Tooltip，按住约
  0.5 秒后松手执行一次游戏原生购买。DLC 使用自己的回调并正常检查碎片、
  库存和容量；适配层不直接改写货币或物品。
- Mac 原生 Mouse HID、Pointer Bridge、Hover、拖拽、滚轮与手柄。
- 存档、DLC 和外部 MOD 覆盖加载；保留 `1099001958` 相关兼容代码，不包含
  该 MOD 原始资源。
- 可用自己的游戏资源构建内置 Mac App 和未签名 IPA。公开仓库仅发布源码。

实验触控策略默认开启，可在启动器关闭。Mac Mouse HID 与 Pointer Bridge
默认开启。Hook 保留准确的主程序和 SDK Build ID 校验，不对未知版本套用偏移。
基础版标识仅供构建联合 Shader 库使用，当前支持和验收基线是 1.3.0。

## 构建环境与命令

需要 Apple silicon Mac、macOS 26 或更新系统、带 Metal 工具的 Xcode、
XcodeGen、Python 3.12+、capstone/lz4/fonttools、.NET 10 及 Shader 工具。
游戏输入和密钥由用户自行提供，项目不会下载游戏内容。

```sh
./scripts/build-mac.sh --nsp-dir /private/game --keys /private/prod.keys \
  --work /private/build-mac --out /private/Dungeon1.app
./scripts/build-ios.sh --nsp-dir /private/game --keys /private/prod.keys \
  --work /private/build-ios --out /private/Dungeon1.ipa
```

也可传入 `--prepared` 复用准备目录；脚本校验 Build ID、重写器源码指纹、
输入 Gate 与 Mac/iOS GL 库覆盖。详见[构建指南](docs/building.md)。所有构建
缓存应放在空间充足的数据卷。App/IPA、资源、日志均不进入公开仓库。

## 使用与存档

Mac 打开 Dungeon1.app，选择可写的数据目录，检查设置后启动。IPA 必须使用
自己的签名和安装工具，未签名包不能直接安装；Mac 包仅作本地 ad-hoc 签名，
未做 Developer ID 签名或公证。触摸操作、MOD 目录和排错详见
[使用指南](docs/user-guide.md)。

新 Bundle ID 的 Documents 与旧应用隔离，旧存档不会自动出现，也不会被删除。
先导出备份旧应用 Documents/save，再手动导入新应用；Mac 对选定数据目录中的
`Dungeon1-01008F1008DA6000/save` 进行同样操作。请关闭游戏后复制整个存档目录。

## 验证边界

[兼容性记录](docs/compatibility.md)分别记录新工程编译、Mac 运行、Mac 模拟
手机输入和用户真机实测。旧版普通商店已获用户 iPhone 验收；DLC 原生购买有
Mac Host 的实际扣款和入库证据，**Dungeon1 新 IPA 的 iPhone 真机验收仍待完成**。
第二指及长按时关闭页面仍需设备实测；不能把单元测试当成完整游戏验收。

## 来源与发布边界

保留 nxnative 的 MIT 授权、seedds 版权及所有第三方声明。
[来源记录](docs/UPSTREAM.md)说明准确的拆分提交；独立 Git 历史不代表代码
全部原创。[第三方声明](THIRD_PARTY_NOTICES.md)和[发布审查](docs/public-release-audit.md)
不授予游戏内容的分发权。不得向 GitHub、Releases 或公开 CI 上传含程序、RomFS、
DLC、派生 Shader、字体、密钥、存档或无授权 MOD 资源的内置包。项目图标为
自有几何绘图，保留生成源码，未使用原游戏图片或商标。

本轮本地 App/IPA 使用用户提供的提灯图标，可通过 `--icon /private/icon.png` 指定。
图片未附公开再分发许可，因此两个原始 PNG 保留为私有构建输入，不提交公开仓库。
公开源码保留可重生成的自有几何备用图标。
