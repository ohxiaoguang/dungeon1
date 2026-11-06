# 地牢英雄状态栏：可行性结论与阻塞项

范围：Darkest Dungeon 1.3.0 main `ff2bf22565188d11ea0981ee0e2b53ce`，SDK `b33804825108340e4cad9d080a636a3f`。这是技术调查结果，不代表面板已实现或已经真机验收。

## 已确认的现有数据入口

- `hle_dd_touch.c` 的 CharacterDisplay 技能回调能取得该详情页绑定的 Hero：面板 `+0x120`；技能包装对象 `+0x50`；面板状态 `+0x2c0` 的 1/2 用于开/关生命周期检查。已有 close/destroy 观测会清理触控动作。
- 这些入口表示“详情页绑定的英雄”，不能当作“地牢当前选中英雄”。英雄详情页在城镇也可打开，关闭时该页绑定对象不能继续留作地牢快照。
- 既有审计识别到 raid `Panel_Hero` 装备/物品 UI 路径 `0xd1ff30`、`0xd20a30`，但它们表示交互上下文，未验证是否覆盖探索与战斗中的全局英雄切换、取消选择与所有模态界面。
- Host 输入 ABI 的触点和 GestureStates 只有坐标、来源、时序，不能从触点可靠推导选中英雄。当前 UIKit Overlay 也没有游戏语义数据。

## 尚未可靠验证的必要信息

| 项目 | 现状 | 后果 |
|---|---|---|
| 地牢选中英雄及场景边界 | 没有覆盖探索/战斗/离开地牢的已验证统一入口 | 不能安全决定何时显示、切换或清除人物 |
| 姓名与职业 | 尚未验证字段、字符串编码和对象寿命 | 不向 SwiftUI 暴露猜测的字符串指针 |
| 当前/最大生命、压力 | 没有经运行时变化验证的字段或取值函数 | 不显示猜测数值 |
| 有效 buff/debuff/异常 | 未验证集合结构、临时对象寿命与本地化 | 不能安全枚举 |
| 线程安全快照 | 缺少上面可验证的数据生产入口 | 仅设计快照结构不能构成有效数据桥接 |

## 结论

当前不能安全交付实时英雄状态栏。没有新增 UI，也没有将城镇/详情页 Hero 指针冒充地牢选择结果；没有 OCR、硬编码人物属性或向 UI 透传游戏指针。可确认的数据尚不足以产生符合需求的快照，因此本轮没有可启用的数据桥。

可靠实现的前置条件是：在同一进程内动态验证探索/战斗中 A→B 切换及离开地牢的选择入口，找到游戏自身计算/渲染姓名、职业、HP、压力的调用路径，并用状态变化验证其取值和寿命。之后在 guest 线程复制值为有界 UTF-8/数值快照，通过 mutex 或双缓冲供 UIKit 主线程读取；场景退出/对象销毁时清零并增加 generation。Overlay 应只读该快照、关闭命中测试，并按 Safe Area 与实际游戏画面布局。

以上前置条件未满足，不能以显示一个空面板或静态人物资料宣称需求完成。第 2 项维持阻塞状态；第 3、4 项已由用户验收，本轮不修改其行为。

## 2026-11-03：原生 UI / Tooltip 路径补充调查

本节取代上文“本轮”的时间含义；此前结论不是本次动态测试记录。
**本次仍未交付实时面板。** 下列地址均为指定 main 的静态映像相对偏移，
不得直接当运行时地址使用，也不是可发布的字段读取契约。

### 可重复的只读调查

新增 `dm/tools/dd_hero_ui_audit.py`，使用仓库 NSO 解压及段校验，先同时验证
main `ff2bf22565188d11ea0981ee0e2b53ce` 与 SDK
`b33804825108340e4cad9d080a636a3f`，再关联 callable 的 RTTI 名称、
typeinfo 引用及 vtable `+0x30`。不导出游戏代码、资源或存档。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 dm/tools/dd_hero_ui_audit.py /private/ExeFS
```

在本机私有 1.3.0 ExeFS 上获得 25 个候选 callable。工具输出是静态指针关联，
仍须逐项检查代码及动态调用；不是函数签名恢复或运行安全证明。
输出留在忽略目录 `out/hero-audit/ui-callables.json`。

### 路径与证据

| 路径 | 本次获得的证据 | 尚未确认 |
|---|---|---|
| RomFS `shared/character/character.layout.darkest` | 包含 name、class、base_stats、resistances、技能区及上一/下一英雄位置 | 这是详情页布局，不提供当前选中英雄、实时数值或对象所有权 |
| RomFS `shared/tooltip/tooltip.layout.darkest` | 提供背景阈值、偏移、文字偏移 | 无文本生成回调、参数和生命周期绑定 |
| `Panel_Hero::ShowSelectedHero` | 三个 callable vtable `0x11886d0/0x1188750/0x11887d0`，调用槽分别 `0xd1ec00/0xd1ea40/0xd1e8a0`；第一个 vtable 在 `0xd1e20c` 被引用，所在 FDE 起点 `0xd1d890` | callable 参数分别涉及物品合法性、unsigned、InventorySlotInterface，不能把这些物品回调当英雄选择通知 |
| `Panel_Banner::ShowSelectedHero(RaidDisplay&)` | vtable `0x1187738`、调用槽 `0xd05be0`；引用点 `0xcfe398`，FDE 起点 `0xcfdf70` | 还未证明它对探索/战斗的每次选择变化都执行，也未验证退出清理 |
| `Overlay_Basic::ShowBuffIconTooltip` | RTTI 签名包含 Actor*、TrayIconType、unsigned long、vec2、LayoutAnchor、RaidDisplay&、unsigned；11 个 `bool(const Buff::GroupEntry&)` callable | 这些是分组谓词，不是返回 Tooltip 文本的生成函数 |
| 上述 Tooltip 的第一个谓词 | vtable `0x11846c0`，调用槽 `0xcd9700`；代码读取入参 `+8` 的 word 并比较 4；第二个调用槽 `0xcd9650` 比较 5 | 不能凭常量命名为某种 Buff，也不能据此推导数值或剩余回合 |
| Tooltip 构建候选 | FDE `0xcd3d10` 在 `0xcd492c` 构造上述第一个谓词；`0xcd4940` 传 Actor 候选 `+0x460` 至 `0xb3cfe0`；函数入口通过第二个参数的虚表 `+0x20` 调用；存在大量栈上临时数据 | 需要运行时确认参数身份、调用前提、文字最终提交点和临时文本销毁；不能直接从 Host 任意线程调用 |
| `GetBuffTrayBuffInstanceList(const Actor*, bool)` 谓词 | vtable `0x1184c40`、调用槽 `0xcd8fc0`；在 FDE `0xcd27c0` 和 `0xcd3d10` 中都有构造引用 | 还没有恢复集合元素生命周期及全部筛选条件 |
| 其他效果集合 | RTTI 分别指向 DeathsDoor、DeathsDoorRecovery、Riposte、ResolveXpBonus、TownEvent、NeverAgain、BattleModifier、Trait 的 InstanceList 谓词 | 类型名不能证明每类效果已能枚举、格式化或展示 |
| `HeroDisplay::App::StatAddAdditionalTooltipBuffLines` | RTTI 含 GuiTooltipParameters&、`vector<const Buff::Instance*>` 及格式化参数；vtable `0x1192888`、谓词槽 `0xe04680`；FDE `0xe04430` 中构造该谓词 | 尚未定位本地化输出和持续时间格式化入口 |
| 同类效果聚合 | `0xe044ac` 取 vector 首尾，按 8 字节遍历指针，经 callable `+0x30` 筛选；`0xe044d0..dc` 累加元素 `+0x48` 的浮点值并计数 | 这里只能证明该路径有聚合；不可把浮点值解释成 HP、百分比或英雄最终属性，不能替代原版公式 |

这些证据来自 RTTI→typeinfo→vtable→指令引用与 FDE/反汇编检查，超出了单纯
字符串搜索；但仍全部属于静态分析。以上字段候选没有进入产品读取代码。

### 实际运行尝试与边界

- 开始时指定 `out/macOS/Dungeon1.app` 与 `out/iOS/Dungeon1.ipa` 均不存在；
  找到现存内置资源产品位于 `/Volumes/MacData/game1/dungeon1`。
- 用 APFS 副本将保存数据复制到 `out/hero-audit/save`，以独立 `DM_SAVE`、
  `DM_TEMP` 和现存只读内置资源启动 Mac dmhost。日志到达视频解码和输出阶段，
  保留 `out/hero-audit/runtime.log`。没有使用正常存档运行这次 Host。
- 原生 UI 控制未能将独立 dmhost 绑定为应用（返回 Invalid app）。另复制完整
  App 到 `out/hero-audit/Dungeon1.app`，可以打开启动器；启动器仍读取原存储位置
  偏好。尝试选择隔离目录时 Open 不可用，已取消，没有点击开始游戏。
- 独立 Host 已终止；没有完成进入地牢、选择 A/B、悬停实际 Buff、增减效果、
  离开地牢或 LLDB 命中记录。不能把启动日志称为地牢功能验证。

### 设置、共享桥与交付状态

已检查共享 `LauncherSettings.swift`：普通设置由 JSON/Setting 列表提供，默认
归入 common；`launcher.<env>` 持久化，环境文件值受保护，`apply()` 传给游戏。
新增独立变量可以沿用这一体系，但本次没有添加无数据源的可用性开关。
现有 Localization.swift 和 LauncherSettingsChecks.swift 是后续双语与迁移检查入口。

| 验收项 | 本次状态 |
|---|---|
| 地牢选中英雄的可靠身份、场景退出边界 | 未动态验证 |
| 姓名、职业、HP、压力 | 未建立产品数据源 |
| Buff/Debuff 名称、数值、持续回合 | 尚无一种完成实际提取；已定位分组及属性聚合候选路径 |
| 原版语言、多行文本、重复效果 | 未恢复文本输出契约，不能宣称支持 |
| 双端共享快照、线程与对象寿命 | 未实现；需要先在游戏线程验证生产入口 |
| 独立持久化开关 | 未实现；没有更改现有用户配置或输入设置 |
| 双端面板与输入穿透、屏幕适配 | 未实现；无新增面板遮挡或输入接收区域 |
| 三种 iOS 模式、Mac 鼠标/触控板/手柄回归 | 未进行真实游戏验证；产品输入代码未修改 |
| 自动化调查验证 | 25 个 callable；分别替换 main/SDK Build ID 的拒绝路径通过；这不是游戏数据测试 |
| 双端新构建产物 | 未生成含面板的新 App/IPA；现存移出目录的产品不代表本次成果 |

后续应在可操作的隔离游戏窗口中，对 `0xd1d890`、`0xcfdf70`、
`0xcd3d10` 和 `0xe04430` 的动态调用先记录线程、参数身份、A/B 变化与文本
提交/释放链，再追到原版数值/百分比/回合本地化函数。最关键阻塞是尚未有
**动态选择身份与可复制的原版文本输出契约**，不是仅仅“找不到 Hero 字段”。
本次没有 commit、push，也没有替换翻译器或改变 Build ID 检查。

## 2026-11-04：真实进入地牢、动态验证选中英雄、Tooltip 仍未截获

本节记录一次真实的 macOS 运行与调试会话。证据等级按四级标注：
**静态分析 / 动态调用证据 / 真实游戏行为验证 / 生产代码可安全复用**。
本轮只读：没有写游戏内存、没有改存档、没有改游戏数据。

### 运行环境（真实游戏行为验证）

| 项目 | 实际值 |
|---|---|
| 可运行产品 | `/Volumes/MacData/game1/dungeon1/Dungeon1.app`（`out/macOS/Dungeon1.app` 仍不存在，未重新构建） |
| 启动方式 | 直接运行 `Contents/MacOS/dmhost Contents/Resources/program`，不经过启动器 GUI |
| 关键环境 | `DM_ROOT/DM_SAVE/DM_TEMP` 指向 `out/hero-audit2`，`DM_ROMFS=$APP/Contents/Resources/romfs`，`DM_FONT_DIR/DM_MSL_DIR/DM_NVN_SHMAP/DM_AOC_DIR` 指向 App 内对应目录，`DM_RESOURCE_BACKEND=directory`，`DM_WINDOW=1`，`DM_CTL=out/hero-audit2/control.txt` |
| 存档隔离 | `out/hero-audit2/save` 是 `out/hero-audit/save`（用户存档副本）的 APFS 副本；原存档未被读写 |
| 游戏内语言 | 中文（随存档设置，含“汉化测试”底栏，属 App 自带资源现状） |
| 进入地牢 | 标题 → 战役 → 槽位“极暗”（第 5 周）→ 继续 → 任务开场 → 遗迹·中型·学徒(1级) 走廊。全程用 `DM_CTL` 的 tap/press 完成，截图逐帧确认 |

`DM_CTL` 提供 `tap/itap/drag/drag/key/shot/memdump/peek` 等命令，是本次主要的
输入与观测通道。宿主的“下一帧截图”只在窗口位于前台、且 display link 正常时
生效；窗口失焦或 display link 卡住时不产出文件，因此另配了
`screencapture` + 按窗口几何裁剪的抓取路径（`grab.sh`），用于纯观察。

### 调试器方式（动态调用证据）

`lldb -b -p <dmhost pid>` 可直接附着成功，**未关闭 SIP、未改签名、未加
get-task-allow**。断点用 main 模块相对偏移加实际基址（日志首行
`main: base 0x7002000000`）设置，命中后读寄存器、`memory read` 与
guest 栈回溯。三个只读脚本放在 `out/hero-audit2/`：

- `hero_lldb.py`：定位 `Panel_Hero` 实例并对其字段下硬件写断点；
- `onehit.py`：单次命中读取面板指针、`+0xa0` 句柄与对象池条目；
- `trace.py`：对任意一组 main 偏移做带寄存器/回溯的命中记录（本轮用于
  `0xcfdf70`、`0xd1d890`、`0xcd3d10`、`0xe04430`、`0xd05be0`、`0xcd9700`）。

同时可用 `DM_CTL memdump` 在不停进程的前提下取任意 guest 地址快照，
用快照差分定位“切换英雄时真正变化的字段”。

### 动态结论一：两个 ShowSelectedHero 都是逐帧刷新，不是选择通知

在走廊里 60 fps 运行期间：

```
main+0xd1d890  x0=0x70081dc1c0 x1=0x700923c000
  bt: main+0xd1d890 main+0x8f85a8 main+0x8b7448 main+0x8b9d28 …
main+0xcfdf70  x0=0x7008120000 x1=0x700923c000
  bt: main+0xcfdf70 main+0xd6b460 main+0x8f85a8 main+0x8b7448 main+0x8b9d28 …
```

- 两者**每帧各调用一次**，参数恒定，上游是同一条 raid UI 更新链
  (`0x8f85a8 → 0x8b7448 → 0x8b9d28`)。
- `x1` 恒为同一个 `RaidDisplay`（本轮 `0x700923c000`），`x0` 分别是
  Banner 面板与 Hero 面板实例。
- `main+0xd05be0`（Banner 的 `std::function` 调用槽）在走廊里**从未命中**；
  `main+0xd1e8a0`（Panel_Hero 的第三个 callable）只在进入 raid 时命中过两次。
- 因此“函数名 + vtable 静态关联”不能当作选择事件；把它们当通知会每帧触发。

证据等级：静态分析给出了候选，**动态调用证据**否定了“选择通知”的假设。

### 动态结论二：选中英雄是 RaidDisplay 的索引字段（已验证 A/B/C）

对 `RaidDisplay` 做 0x8000 字节快照差分（切换英雄前后），唯一语义稳定的变化
是 `RaidDisplay+0x3a40` 处的两个 int32：

```
+0x3a40  0x0000000300000000  → {selected=0, partySize=3}
         0x0000000300000001  → {1,3}
         0x0000000300000002  → {2,3}
         0x0000000300000000  → 回到 {0,3}（越界回绕）
```

按 `R`（右肩键）逐次切换，并在同一时刻抓屏，得到一一对应：

| 索引 | 面板显示 | 职业 |
|---|---|---|
| 0 | 哥伦布尔斯 | 修女 |
| 1 | 麦克道尔 | 小丑 |
| 2 | 戈顿 | 破盾者 |

即“选 A 读到 A、选 B 读到 B、选 C 读到 C”，且回绕到 0 时仍是同一个指针值。
`partySize` 与画面上的三人队伍一致。证据等级：**动态调用证据 + 真实游戏行为验证**。

同时确认：`Panel_Hero` 实例自身在切换前后前 0x800 字节**完全不变**，
`+0xa0` 是它的布局/资源句柄（值为 `0x17e3`，可解析到 `panel_*` 资源名），
不是英雄指针。也就是说英雄身份是每帧从 `RaidDisplay` 解析出来的，面板不缓存。

### 动态结论三：离开地牢后选择状态被销毁

从暂停菜单“保存并退出”回到标题后：

- `Panel_Hero` 实例（`0x70081dc1c0`）前 0x40 字节被清零；
- 原 `RaidDisplay` 地址（`0x700923c000`）已被别的对象复用（vtable 变为
  `0x7003198770`），说明 raid 对象已析构、内存回收；
- 对 `main+0xcfdf70` / `main+0xd1d890` 重新下断点，12 秒内**零命中**
  （在地牢内约每帧各命中一次）。

证据等级：**动态调用证据 + 真实游戏行为验证**。这给出了“何时该清空快照”的
可靠信号：这两个逐帧函数停止被调用 + `RaidDisplay` 指针失效。

### 未完成：Buff Tooltip 文本（B）与免悬浮取数（C）

本轮**没有**截获任何 Buff/Debuff Tooltip 文本，也没有验证免悬浮枚举。
原因是队伍在起始房间无法移动，因而没有进入战斗、没有获得任何 Buff/Debuff：

- 左摇杆可以把队伍在房间内挪动，但走不出房间；地图上的房间/走廊格点击、
  右摇杆选点、D-pad + A 均未使队伍移动（多次截图确认画面未变）。
- 该房间地图显示正南方是“走廊 → 红色 X（封锁门） → 走廊 → 蓝色房间 → 红色战斗房间”，
  队伍停在最北端的房间里。
- 无食物（启程时确认过“未购买食物”），无法扎营；角色页的“扎营技能”因此不可用。
- 已有 Buff 图标行为可确认：血条下方是 8 个空状态格，无 Buff 时为空。

已就绪但未命中的断点（`trace.py`，只读）：`main+0xcd3d10`
(`Overlay_Basic::ShowBuffIconTooltip`)、`main+0xe04430`
(`StatAddAdditionalTooltipBuffLines`)、`main+0xcd9700`（分组谓词）、
`main+0xd05be0`。对技能图标、属性行、角色页反复点击均零命中——符合
“没有 Buff 就不会走这条路径”的预期，但也**不能**据此宣称 Tooltip 契约已恢复。

继续验证所需的最小人工动作（挂好上述断点后）：

1. 把队伍走到有敌人的格，触发一场战斗；
2. 战斗中让某个英雄获得任意 Buff/Debuff（例如修女治疗、破盾者格挡、
   或被打上流血/腐蚀）；
3. 用鼠标左键（宿主映射为触点）点住该英雄血条上方的状态图标不放；
4. 记录 `0xcd3d10` 命中时的 `x0`（Actor*）、`x1`（TrayIconType）、
   `x8` 附近是否为 `RaidDisplay`，以及随后文本构建函数的参数；
5. 用 `DM_CTL memdump` 对 Tooltip 对象做前后快照，确认文字缓冲的生命周期。

### 本轮验收对照

| 项目 | 状态 | 证据等级 |
|---|---|---|
| Mac 真实进入可操作地牢 | 是（走廊可操作：切人、开角色页、暂停菜单、退出） | 真实游戏行为验证 |
| 英雄 A/B/C 切换识别 | 是（索引 0/1/2 ↔ 修女/小丑/破盾者，回绕一致） | 动态调用证据 |
| 离开地牢清理 | 是（面板清零、RaidDisplay 复用、逐帧调用归零） | 动态调用证据 |
| `Panel_Banner::ShowSelectedHero` 是选择入口 | **否**，是逐帧刷新 | 动态调用证据 |
| `Panel_Hero::ShowSelectedHero` 职责 | 逐帧把 `RaidDisplay` 当前选择画到面板 | 动态调用证据 |
| Buff Tooltip 原版文本 | **未截获**（无 Buff 可用） | — |
| 数值/百分比/持续回合 | 未取得 | — |
| 免悬浮取数 | 未验证 | — |
| 生产代码改动 | 无（仅新增 out/ 下的只读脚本与本文档） | — |

本次没有 commit、push，没有替换翻译器，没有改变 Build ID 检查，
没有修改触控/指针/启动器逻辑，也没有动过用户存档。

---

## 第二轮：真实战斗中的 Buff Tooltip 动态调查

本轮目标只有一个：进入战斗、拿到一个真实 Buff、截获原版 Tooltip 文本。
环境沿用 `out/hero-audit2/`（`run.sh` 的 `DM_ROOT/DM_SAVE/DM_TEMP`
仍指向该隔离目录；用户存档 `/Volumes/MacData/game1/dungeon1/save` 未读写）。
游戏进程直接是 `/Volumes/MacData/game1/dungeon1/Dungeon1.app/Contents/MacOS/dmhost
Contents/Resources/program`，没有重新构建 App。

### 1. 进入战斗的实际方法（真实游戏行为验证）

上一轮「队伍困在起始房间」的原因不是地图点击失效，而是**移动方式不对**：
先用 `DM_CTL` 的 `LRight~3.0`（左摇杆右推约 3 秒）让队伍朝出口移动，
画面出现「移至此房间 · 战斗」的目标提示后，再按 `A` 确认，队伍进入走廊并
触发战斗。之后按两次 `A` 跳过关卡开场，得到回合 1 的战斗界面
（3 名英雄 vs 3–4 名邪教/死灵法师系敌人，任务「杀死死灵法师学徒」）。

战斗内可稳定执行的操作（均已用 `grab.sh` 的桌面抓帧逐张确认）：

- 红色 `X` 按钮（归一化约 `0.473 x 0.72`）= **跳过回合**。屏幕原版提示
  「跳过回合，英雄会承受压力」；每点一次切换一名英雄，点满一轮后回合数
  2 → 3，敌人行动，英雄压力 57 → 62、HP 19 → 17。
- 点击技能图标会选中技能并显示技能 Tooltip；例如小丑第 4 技能
  「鼓舞乐章 1 / 压力-8 / 增益目标：-10%所受压力伤害 / 增益自身：…」。
- 选中技能后点击英雄身体可释放：目标英雄出现白色光圈、施法者技能栏变暗。
- 长按血条会出现英雄状态 Tooltip「生命：20/24 / 压力：35/200」。

**结论：本轮确实进入了可操作的战斗，并真实释放了一个带增益的技能。**
截图证据：`shots/vmv3.png`（战斗开始）、`shots/vbuff2.png`（技能释放）、
`shots/vhover1.png`（状态 Tooltip）、`shots/jest4c.png`（技能 Tooltip）。

### 2. `0xcd3d10` 的真实职责与参数身份（动态调用证据）

`Overlay_Basic::ShowBuffIconTooltip`（`main+0xcd3d10`）在战斗中**每帧被调用**，
调用者固定是 `main+0xcd1c04`，上游为
`main+0xd650ec → main+0x8f85a8 → main+0x8b7448 → main+0x8b9d28`，
线程 T=4（游戏主线程），全部断点都在同一线程。

| 参数 | 实测值 | 身份 |
|---|---|---|
| `x0` | `0x7008fbb480` | tray icon 句柄数组（前 0x100 字节是 16 位资源句柄 `0x17a4…`），不是文本对象 |
| `x1` | `0x7008b00010` / `0x7008b07010` | **Actor\***（函数开头 `cd3d58 mov x25,x1`） |
| `x2` | `0x7 / 0xd / 0xe / 0x16` | TrayIconType，函数内 `br x10` 跳转表的索引 |
| `x3` | `0x62666b9a / …a0 / …a1 / …a9 / …bc` | tray icon 的运行时资源 id |
| `x4` | `0x0`（全程） | 本次调查中恒为 0，未出现 hover/选中上下文 |

`main+0xcd8fc0`（GetBuffTrayBuffInstanceList 谓词）与 `main+0xcd9650`
（Buff::GroupEntry 谓词）在 UI 重建时成批命中，例如一次切换中出现 60 次
`0xcd8fc0`，调用栈 `main+0xcd30e4 → main+0xccffa8 → main+0xd650ec`。
`main+0xe04430`（`StatAddAdditionalTooltipBuffLines`）**本轮零命中**。
`main+0xcd9700`、`main+0xd05be0` 同样零命中。

**结论：`0xcd3d10` 是每帧的 tray icon / tooltip 调度器，不是「悬停时通知」。**
不能把它的命中当成「已经生成了 Buff Tooltip 文本」。

### 3. 原版文本的生成链（静态分析 + 动态调用证据）

对 `main+0xcd3d10` 函数体（0x1800 字节）定向反汇编，得到完整的文本生成链：

- `main+0x98fdb0`：**本地化键查表**。入口按 `hash = hash*53 + ch` 计算键哈希，
  再 `bl 0x992270` 查表，返回 `x0=data ptr, x1=size/flags`（SSO 字符串）。
  函数内逐一 `adrp/add` 装载键名，实测键包括：
  `tray_icon_tooltip_controlled_burn_title`、
  `tray_icon_tooltip_controlled_burn_turn_start`、
  `tray_icon_tooltip_controlled_burn_on_move`、
  `tray_icon_tooltip_controlled_burn_rounds`、
  `tray_icon_tooltip_death_blow_resistance_permanent_debuff`、
  `tray_icon_tooltip_deathsdoor_title`、`tray_icon_tooltip_daze_format`、
  `tray_icon_tooltip_guard_title`、
  `tray_icon_tooltip_health_damage_blocks_duration_format`、
  `resistance_trap_disarm_format`、`buff_bsrc_last_hero`、
  `tray_icon_tooltip_immobilized`、`tray_icon_tooltip_deathsdoor`、
  `tray_icon_tooltip_daze`、`tray_icon_tooltip_guard`、
  `tray_icon_tooltip_guard_no_duration`。
- `main+0x993000`：**变参格式化**（`cd4400` 处 `x0=本地化串对象, x1=sp+0xe0,
  w2=0x100, w3=数值`；数值来自 `fcvtzs w21, s3` 的游戏内运行时浮点计算），
  内部 `bl 0xe69aa0` 完成 printf 风格替换。
- `main+0xe69af0`：**把格式化好的行追加到 Tooltip 行 vector**
  （`cd440c` 取 `[sp+0x990]` begin / `[sp+0x998]` end，`x1=sp+0xe0`，
  `w2=0x100`，步长 `add x20, x21, #0x100`）。共找到 22 处提交点
  （`0xcd40f4` … `0xcd54b4`）和 7 处格式化点。

即：**Buff 实例 → 原版本地化模板 → 运行时数值格式化 → 每行 0x100 字节的
Tooltip 行 vector → UI**。文本是 UTF-8（本地化文件 `schinese.loc2` 中可见
中文与 `<c>…</c>`、`%d` 等标记），多行由 vector 逐行提交，并非单个字符串。

`shots/../dis_cd3d10.txt` 保存了完整反汇编；键名与调用点清单见
`out/hero-audit2/tiptext.py` 的 `COMMIT` / `FORMAT` 常量。

### 4. 真实 Buff 与免悬停的数据源（动态调用证据）

`cd3d58 mov x25,x1` 之后，`cd400c/cd401c` 直接读
`[x25+0x460] / [x25+0x468]` 作为 vector 的 begin/end，遍历步长
`add x24,x24,#0x1d8`（`cd4058`）。`main+0xb3cfe0` 是配套的筛选函数：
以 `Actor+0x460` 为输入、用谓词 `[vtable+0x30]` 过滤、把命中的
`element+8` 收集成指针 vector，并返回聚合浮点值（`fmov s12,s0`）。

运行时用 `DM_CTL memdump` 实际读取（`out/hero-audit2/dumps/actor*_all.bin`）：

- Actor `0x7008b00010`：`begin=0x70574fa000 end=0x70574faec0`，**8 个条目**；
- Actor `0x7008b07010`：`begin=0x70574cd000 end=0x70574ce098`，**9 个条目**。

条目结构（每个 0x1d8 字节，均为**运行时内存，非静态表**）：
`+0x08` SSO 字符串短名、`+0x50` float 效果数值、`+0x58` 两个 int32
（本例中常驻条目为 `(9,5)`，临时 Buff 为 `(9,1)`）、`+0x68` 起为内部 id。
实测 id 例：`BLEEDRESIST15`(0.15)、`RESOLVECHECK5`(0.05)、
`QUIRK_in_dungeon_crypts_STRESSDMG_D`(0.20)、
`QUIRK_hottotrot_acc`(0.20)、`QUIRK_hottotrot_dmg`(0.25)、
`QUIRK_scientific_1_`(-0.20)。

**关键对应**：Actor 2 的最后一个条目 id 为 `…TTuneStressResis`、
值 **-0.1000**、ints `(9,1)` —— 正是刚释放的「鼓舞乐章」给目标施加的
「-10% 所受压力伤害」增益。这同时证明：

1. 真实 Buff 已产生（真实游戏行为验证）；
2. Buff 的完整集合在 `Actor+0x460` 运行时可读，**不需要鼠标悬停**；
3. 数值与技能 Tooltip 显示的 `-10%` 一致，无需自行计算。

证据等级：**动态调用证据 + 真实游戏行为验证**。尚未达到
「生产代码可安全复用」——条目生命期、跨场景失效、跨线程读取约束未验证。

### 5. 文本截获结果与未解决的原因

本轮**没有**截获到 Buff Tooltip 的原版文本。

已在 `out/hero-audit2/tiptext.py` 挂好 31 个只读断点（22 个文本提交点 +
7 个格式化点 + `0xcd3d10` 入口 + `0xe04430`），脚本启动打印
`all 31 breakpoints resolved; unresolved: none`，入口每帧命中，
但 `TEXT` / `LINES` 记录为 0。也就是说：游戏走了 `0xcd3d10` 的
「无文本」分支，本地化/格式化/提交链一次都没有执行。

可以确定的原因与排除项：

- 不是基址错误（`0xcd3d10` 入口、两个 witness 断点都命中）；
- 不是断点失效（31 个全部 resolved，locations=1）；
- 不是没有 Buff（`…TTuneStressResis -0.1` 已在运行时容器里）；
- 最可能是**缺少 hover 上下文**：`x4` 全程为 0，而宿主当前运行配置未开启
  `DM_MOUSE_HID`，`front_mac.m` 的 `mouseMoved` 不发布任何事件，
  `DM_CTL` 只能产生「按下/抬起」的触点。长按血条只能得到英雄状态
  Tooltip（生命/压力），长按 buff tray 格子落回同一 hitbox。

### 6. 需要人工接管的具体动作（下一步）

游戏窗口与 LLDB 附加**保持原样**（pid 见运行时 `pgrep -f Resources/program`），
`out/hero-audit2/text.log` 持续接收断点记录。请按顺序操作：

1. 在游戏窗口用**真实鼠标**移动（不是点击）到中间英雄血条正下方那排
   小方格中的**彩色**状态图标上（约归一化 `0.30 x 0.665`），停留 1–2 秒，
   等屏幕上出现 Buff 描述框。若当前增益图标不明显，可先让敌人再行动一回合
   得到流血/眩晕等更醒目的 Debuff。
2. 保持悬停不动，告诉我「已悬停」，我会立刻抓取 `text.log`、
   对 Tooltip 行 vector 做 `memdump` 前后快照，并用 `grab.sh` 保存屏幕文本
   做逐字对照。
3. 换另一个 Buff/Debuff、推进一回合让持续时间变化，重复一次。

若真实鼠标移动仍不触发（宿主未开启 Mouse HID），备选方案是重启该隔离进程时
在 `out/hero-audit2/extra.env` 加 `DM_MOUSE_HID=1`、`DM_DD_FAKE_IOS=1`，
再按上文的「左摇杆右推 → A 确认」重新进入战斗；这一步会丢弃当前战斗进度，
但不动用户存档。

### 7. 本轮验收对照

| 项目 | 状态 | 证据等级 |
|---|---|---|
| 真实进入战斗 | **是**（左摇杆右推 + A 确认；回合 2→3 已推进） | 真实游戏行为验证 |
| 获得真实 Buff | **是**（鼓舞乐章 → `…TTuneStressResis -0.1`） | 动态调用证据 + 真实游戏行为验证 |
| 命中 `main+0xcd3d10` | **是**，每帧、固定调用栈、线程 T=4 | 动态调用证据 |
| 命中 `main+0xe04430` | 否（零命中） | 动态调用证据 |
| 命中 `main+0xcd8fc0` / `0xcd9650` | 是（UI 重建时成批） | 动态调用证据 |
| 找到文本生成/提交链 | **是**（本地化键 → `0x98fdb0` → `0x993000` → `0xe69af0` → 行 vector） | 静态分析（链本身）+ 动态调用证据（函数被 `0xcd3d10` 调用） |
| 截获与屏幕一致的原版 Buff Tooltip | **否** | — |
| 数值/百分比来源 | 游戏内 `float`（`+0x50`）经 `fcvtzs`/格式化；持续回合字段为候选 `+0x58` 的 int32，**未确认** | 静态分析 + 动态内存 |
| 不悬停枚举 Buff | **可读取** `Actor+0x460` vector（8/9 条目，含 id/值），但生命周期与线程安全未验证 | 动态调用证据 |
| 复用原版格式化函数 | 未验证（文本分支未执行） | — |
| 共享只读数据快照条件 | **未达标**（缺已验证的原版文本契约） | — |

新增可复用诊断工具（全部位于 gitignore 的 `out/hero-audit2/`）：
`tiptrace.py`（多断点寄存器/栈追踪）、`tiptext.py`（31 个只读文本站点 +
Actor/行 vector 观测）、`dis_cd3d10.txt`、`dumps/actor*_all.bin`、
`text.log` / `tip3.log` / `tip2.log`、以及 `shots/` 下本轮全部截图。
**产品代码零改动**；只有本文档是 tracked 改动。没有 commit、push，
没有修改存档、资源、触控逻辑或启动器配置。

## 第三轮：恢复调查环境、证伪 hover 路径、修正文本断点假设

本轮目的不是实现界面，而是把前两轮「Tooltip 未截获」的原因查实，并确认
阶段 A 还缺什么。全程没有结束游戏进程、没有重启、没有覆盖任何调查数据。

### 1. 环境恢复核验（2026-11-04 16:05–16:15）

| 检查项 | 实际结果 |
|---|---|
| Git | 分支 `main`；未提交改动 `CHANGELOG.md`、`docs/darkest-dungeon-hero-status-audit.md`、`docs/input-controls.en.md`、`docs/input-controls.md`、`docs/user-guide.md`，未跟踪 `dm/tools/dd_hero_ui_audit.py`；无 commit/push |
| dmhost | pid 30958 仍在，已运行约 45 分钟，进程状态正常 |
| LLDB | pid 34726 仍附着（debugserver 34728），运行的是 `tiptext.main()`，`DM_SECS=2400`，15:57:22 启动。注意：`tiptext.py` 的循环在 `proc.Continue()` 上阻塞，ENTRY 断点 40 次命中后自禁用、其余站点零命中，因此它**不会**到点自动 detach，而是空转挂起；`text.log` 自 15:57 起没有新增内容 |
| 调查数据 | `out/hero-audit2/` 脚本、`runtime.log`、`text.log`、`tip2/3.log`、31 个 dumps、290 张截图全部保留；新增截图 `shots/state_now.png` |
| 游戏状态 | 截图确认仍在回合 3 战斗，选中「戈顿／破盾者」HP 17/20、压力 24/200，血条下方 Buff 图标可见 |
| 隔离存档 | `DM_ROOT/DM_SAVE/DM_TEMP` 仍指向 `out/hero-audit2/`，`extra.env` 为空，正式存档未动 |

Build ID 用宿主真正读取的元数据核对，而不是对已打补丁的 `.patched.bin`
猜偏移：`loader.c:194` 从 `<module>.fixups.tsv` / `.cuts.tsv` 的
`# BUILD_ID` 行填入 `module_t.build_id`。

| 模块 | 运行中文件记录 | 注册表 `game.tsv` v393216 | 结论 |
|---|---|---|---|
| main | `ff2bf22565188d11ea0981ee0e2b53ce` | 同 | 匹配 |
| sdk | `b33804825108340e4cad9d080a636a3f` | 同 | 匹配 |
| subsdk0 | `bd9af3397f38608dba3f01510fd206e8` | 同 | 匹配 |

`runtime.log` 首行也记录 `main: base 0x7002000000`，与全部断点基址一致。

### 2. 真实鼠标移动在当前进程里无法变成游戏内 hover（代码级结论）

`ps eww -p 30958` 显示进程环境里**没有** `DM_MOUSE_HID`、
`DM_DD_MOUSE_POINTER`、`DM_DD_FAKE_IOS`。链路逐段确认：

1. `dm/host/hle_hid.c:426–430`：`mouse_config()` 只在 `pthread_once` 首次调用时
   读 `DM_MOUSE_HID`；`dm_mouse_enabled()` 此后恒为 0。
   `hle_hid.c:455` 的 `dm_mouse_set()` 因此直接返回，不产生任何 Mouse HID 采样。
2. `dm/host/front_mac.m:218–230`：只有 `dm_mouse_enabled()` 为真时才安装
   带 `NSTrackingMouseMoved` 的 tracking area；否则 `mouseMoved:` 根本不会被投递。
   即便投递，`front_mac.m:204–209` 的 `publishMouse:` 也在第一行返回。
3. `dm/host/hle_dd_pointer_mac.c:11–30`：DD 指针桥要求
   `DM_DD_MOUSE_POINTER=1` **且** `dm_mouse_enabled()`，并校验两个 Build ID、
   gate 与两条原版指令；满足后才把指针坐标写入 `main+0x27e0890`。当前是关闭的。
4. `dm/apple/LauncherSettings.swift:136` 进一步说明：需要先有一次左键点击把
   hover 焦点交给鼠标，且游戏内必须打开它自己的 Switch Mouse HID 选项
   （`hle_dd_pointer_mac.c:34–35` 读 `main+0x27dee2c` 的模式字段）。

`DM_CTL` 支持运行时 `env KEY=VALUE`（`hle_hid.c:149`），但救不了这条链：
`pthread_once` 与 `dd_pointer_impl` 的 `static int enabled` 都已在启动时定值。
**结论：现在让用户用真实鼠标悬停不会有任何效果，此前「请悬停后回复」的步骤
是无效的，需要撤回。** 要启用 hover 必须重启该隔离进程。

### 3. 对上一轮「文本分支没执行」结论的两处修正

前一轮把 `TEXT` 行数为 0 解释成「本地化/格式化/提交链一次都没执行」，
这个推论不成立：

- `tiptext.py:182–192` 只在**找到可打印字符串**时才写日志
  （`if not fresh: continue`），并且没有断点命中计数器。因此「0 条 TEXT」只能
  说明「没读到字符串」，不能证明「断点没命中」。
- `0xe69af0` 不是专门的「文本行提交」。反汇编中 `0xcd40f4` 的调用紧邻
  `0xe69a80`（分配）与 `0xe69a20`（释放），参数是 `(x0=目标, x1=源, x2=字节数)`，
  是通用的 vector 追加/扩容助手；23 个调用点里既有拷贝指针数组、也有拷贝
  0x100 字节文本行，不能全部当成文本提交点。

另外解出了 `main+0xf1cb52` 的 28 项 u16 跳转表
（目标 `= 0xcd400c + entry*4`），它按 `w20 = x2`（TrayIconType）分派：

| 观测到的 x2 | 跳转目标 | 说明 |
|---|---|---|
| `0x07` | `main+0xcd472c` | — |
| `0x0d` / `0x0e` | `main+0xcd400c` | **读取 `Actor+0x460/+0x468` Buff vector，按 `0x1d8` 步长用虚谓词筛选** |
| `0x16` | `main+0xcd4cbc` | — |

也就是说，观测到的图标类型里至少 `0x0d/0x0e` **确实进入了 Buff 文本分支的入口**，
并不像上一轮推测的那样「因缺 hover 直接走无文本分支」。真正的门槛更可能是
该类别的筛选谓词没有命中当前 Buff 实例（`0xcd407c` 的 `tbz w0,#0` 跳过），
以及 `w23 = x4` 作为图标槽位索引（`0xcd4780`、`0xcd4794` 的 `0x18` 步长）。
这需要在运行时用带命中计数的断点确认，而不是继续用 tap/press/长按去试。

### 4. 原版本地化与效果数据的正式来源（静态证据）

这些是游戏自带的只读资源，可作为「复用原版文本」的入口，不需要自建翻译表：

- `romfs/shared/buffs/base.buffs.json`：`JESTTuneStressResistance1` 的完整定义是
  `stat_type: stress_dmg_received_percent`、`amount: -0.1`；与运行时容器里的
  `…TTuneStressResis -0.1000`、屏幕上的 `-10%所受压力伤害` 对得上。
  该文件还给出 `duration_type` 词表：`combat_end` / `quest_end` /
  `activity_end` / `idle_start_town_visit` / `quest_complete`，是判断
  「永久 / 临时 / 回合」的候选依据（**运行时语义仍未验证**）。
- `romfs/effects/base.effects.darkest:1063–1067`：小丑「鼓舞乐章」1–5 级效果
  分别引用上述 5 个 buff id，可解释「同一效果多来源 / 多等级」。
- `main.patched.bin` rodata 里存在 8 处 `tray_icon_tooltip_*` 原版键，
  例如 `tray_icon_tooltip_buff_until_camp_format`、
  `tray_icon_tooltip_burn_format`、`tray_icon_tooltip_guard_no_duration`、
  `tray_icon_tooltip_stealth_description`；这些就是传给 `0x98fdb0` 的键。
- `romfs/localization/*.loc2` 与 `localization/nx/*.loc2`（含 `schinese.loc2`）
  是 NUL 分隔的 UTF-8 原版文本池，前面带二进制偏移/哈希表。
  `schinese.loc2` 中可确认「鼓舞乐章」等原文；其容器格式尚未完整解析，
  也尚未与运行时 `0x98fdb0` 的返回值逐字对照。

### 5. 已准备但未运行的诊断工具

`out/hero-audit2/tiptext2.py`（新文件，`py_compile` 通过，**尚未挂载**）：
从 `dis_cd3d10.txt` 提取 16 个 `bl 0x98fdb0`、7 个 `bl 0x993000`、
7 个 `bl 0xe6a0e0`、23 个 `bl 0xe69af0` 调用点，加上 28 个跳转表 case
与 `0xcd3d10` / `0xe04430` 两个 witness；**对每个断点记录命中次数**，
在结束时打印每个类别的 reached/total 与图标类型直方图，从而把
「断点没命中」变成可证实的观测。全程只读 guest 内存，写入新日志文件。

### 6. 阶段状态与待确认决策

- 阶段 A **未完成**：原版 Buff Tooltip 文本、最终文本对象、数值格式化契约、
  `+0x58` 持续回合语义、英雄姓名/职业/HP/压力来源均未获得运行时证据。
- 阶段 B/C/D **一律未开始**：按本轮要求，不跳过 A/B 直接写共享快照或双端 UI。
- 本轮新增文件只有 `out/hero-audit2/tiptext2.py`、`shots/state_now.png`
  和本文档追加内容；产品代码、启动器设置、输入逻辑零改动；没有 commit/push。

需要用户确认的两条路径：

1. **重挂 LLDB（推荐先做）**：当前 LLDB 会话已空转挂起、不再产出任何记录。
   结束该 LLDB 会话后用 `tiptext2.py` 重新 attach 同一个 dmhost pid 30958
   （**不结束游戏进程、不重启、不动存档、不覆盖已有日志**），先验证文本分支
   到底有没有被命中。若命中，可能完全不需要 hover，也就不需要重启。
   残留风险：debugserver 断连瞬间游戏可能短暂停住，需要重新确认窗口响应。
2. **重启路径**：只有在证实文本分支必须靠 hover 时才需要。重启会**丢弃当前
   回合 3 的战斗进度**，需在 `extra.env` 加 `DM_MOUSE_HID=1` 与
   `DM_DD_MOUSE_POINTER=1`，重启后还要在游戏内打开 Switch Mouse HID 选项、
   先左键点击一次再把真实鼠标悬停到彩色 Buff 图标上。仍只用
   `out/hero-audit2/save` 隔离存档，不碰正式存档。**未获确认前不执行。**
3. **保持现状**：不改动游戏与 LLDB，先由用户人工核对上面的结论。

阶段 B/C/D 在阶段 A 完成前一律不启动；本轮没有写任何 UI、共享快照或
启动器设置代码。

---

## 第四轮：命中计数证据链（2026-11-04 16:34–16:40，用户选择方案 1）

### 1. 操作与环境（动态 · 已执行）

- 结束空转的旧 LLDB pid 34726（`kill -TERM`），debugserver pid 34728 自行退出；
  `dmhost` pid 30958 **未结束、未重启**，PPID 由 34728 回到 1、状态 `SNX → SN`。
  随后帧号 57600 → 59400 持续增长、`runtime.log` 4 秒增加 782 字节，
  `shots/post_detach.png` 仍是回合 3 战斗、Buff 图标可见、无崩溃、无 Tooltip。
  说明旧断点已由 debugserver 恢复，无残留 `brk`。
- 用 `tiptext2.py` 重新 attach 同一 pid 30958：
  `DM_BASE=0x7002000000 DM_SECS=120 DM_MAXVAR=12 DM_MAXHIT=1000000`，
  `DM_OUT=out/hero-audit2/tiptext2_r1.log`，LLDB stdout
  `tiptext2_r1_run.out`（均为**全新文件**，未覆盖 `text.log` 等）。
  `MAXHIT` 设大是为避免活跃断点自禁用后 `proc.Continue()` 空转挂起
  （第三轮失败的直接原因）。
- **81 个只读断点全部解析成功**（`unresolved: none`）。
- 运行 16:35:49–16:37:54（125 s），脚本自行 `proc.Detach()` 并完整打印统计。
  LLDB 退出码 1 仅因末尾多余的 `-o detach` 报
  `error: Process must be launched.`；`main()` 返回 0、`detached` 已写入，证据完整。

### 2. 完整命中计数（动态 · 可证实的正观测）

| 类别 | 命中站点 | 总命中 | 明细 |
|---|---|---|---|
| ENTRY `0xcd3d10` | 1/1 | 2765 | 图标直方图 `0x7=553, 0xd=1659, 0xe=553` |
| CASE（26 个去重目标） | 2/26 | 2765 | `main+0xcd400c:2212`（type 0xd/0xe）、`main+0xcd472c:553`（type 7） |
| KEY/本地化 `bl 0x98fdb0` | **0/16** | **0** | none |
| FORMAT `bl 0x993000` | **0/7** | **0** | none |
| STRING `bl 0xe6a0e0` | **0/7** | **0** | none |
| APPEND `bl 0xe69af0` | 1/23 | 3871 | 仅 `main+0xcd40f4:3871` |
| LINES witness `0xe04430` | 0/1 | 0 | none |

- 图标分布精确吻合 1:3:1：每帧 5 个图标（1×type7 + 3×type0xd + 1×type0xe），
  553 帧 / 120 s ≈ 23 fps。断点开销使 display link 出现帧合并丢弃
  （`old frames dropped by merging 19729`），但 3 个检查点
  （16:36:41 / 16:37:21 / 16:38:00）均抓帧成功、`runtime.log`
  101199 → 102762 字节持续增长，游戏全程响应。
- ENTRY 前 6 次 `x4` 恒 0；`Actor+0x460/+0x468` 读出 `buffs=8 / 9 / 6`
  （三个不同 Actor），Buff vector 有效。

### 3. 结论：不依赖 hover 时不会生成任何原版 Tooltip 文本（动态）

`0xcd3d10` 每帧被调用 2765 次、跳转表 case 也确实进入，但**本地化查表、
格式化、字符串助手、文本行 witness 全部 0 命中**。这是 81 个断点各自带
命中计数器的正观测，不是「脚本没写日志」的推论。第三轮「零文本 =
断点没写日志」的怀疑已被排除：**当前无 hover 状态下，该路径不生成
任何 Buff/Debuff Tooltip 文本**。

### 4. 具体阻塞分支（静态反汇编 + 动态命中对照）

- `main+0xf1cb52` 的 28 项 u16 跳转表（target = `0xcd400c + entry*4`）
  索引即 TrayIconType。把 16 个 KEY / 7 个 FORMAT 调用点按地址区间归到各 case：
  - **含文本生成的类型**：0xf、0x10、0x11、0x13、**0x16**、0x18、0x1a、0x1b。
    index 27（`0xcd4250`）最密集：4 KEY + 3 FORMAT + 1 STRING；
    index 22 = 0x16（`0xcd4cbc`）含 1 KEY + 1 FORMAT。
  - **每帧实际出现的类型**：0x7（`0xcd472c`）、0xd/0xe（`0xcd400c`）——
    这三个 case 区域内 KEY=0、FMT=0、STR=0，**本来就不生成文本**。
- `0xcd400c`（type 0xd/0xe）反汇编证明它只是 **Buff 实例筛选器**：
  ```
  ldr x24,[x25,#0x460] ; ldr x19,[x25,#0x468]      ; vector begin/end
  ldr x8,[x0] ; ldr x8,[x8,#0x30] ; blr x8         ; 谓词是虚调用
  tbz w0,#0,next ; add x20,x24,#8 ; str x20,[x23],#8 ; 命中 -> 存 ptr+8
  add x24,x24,#0x1d8                                ; 步长 0x1d8
  bl #0xe69af0                                      ; vector 追加助手
  ```
  谓词是 **vtable+0x30 的虚调用 `blr x8`**（不是固定地址 `bl`），本轮 81 个
  地址断点没有直接覆盖。遍历结束 `b.eq #0xcd4234 → b #0xcd4f64`
  **直接跳到函数尾声，不 fall through 到任何文本生成代码**。
- **纠正第三轮一处假设**：`0xe69af0` 是 vector 扩容/追加助手
  （相邻 `0xe69a80` 分配、`0xe69a20` 释放），**不是「文本行提交」**。
  `APPEND main+0xcd40f4:3871` 是「筛选命中的 Buff 指针被追加到数组」3871 次，
  不是 3871 行文本；23 个调用点里只有这 1 个在每帧路径上。
- **Buff 筛选谓词是否命中**：虚调用本身未被地址断点直接观测，但
  `0xcd40f4` 命中 3871 次 + `buffs=8/9/6` 证明循环执行且至少 3871 次
  谓词返回真（每次命中都走一次追加）。虚函数具体目标尚未定位。
- `0xcd3d10` 体内 **零个 `bl 0xe04430` 调用点**（静态核对）+ 动态 LINES=0，
  故它不是这条每帧链的文本提交入口；不排除其他调用路径。

### 5. 原版 Tooltip 文本链（静态 · 已完整定位，运行时待验证）

16 个 `bl 0x98fdb0` 调用点的本地化键全部由 `adrp/add` 静态解出，
均为游戏原版键：

`tray_icon_tooltip_controlled_burn_title / turn_start / on_move / rounds`、
`death_blow_resistance_permanent_debuff`、`deathsdoor_title / deathsdoor`、
`daze_format / daze`、`guard_title / guard / guard_no_duration`、
`health_damage_blocks_duration_format`、`immobilized`、
`resistance_trap_disarm_format`、`buff_bsrc_last_hero`；
rodata 另有 `buff_duration_`、`buff_until_camp_format`、
`buff_until_end_of_raid_format`、`buff_no_duration`、
`burn/bleed/poison/stress_dot/hp_heal_dot_format` 等持续时间与数值模板。

典型链（`0xcd4cbc`，type 0x16）：
```
adrp/add -> "tray_icon_tooltip_health_damage_blocks_duration_format"
bl 0x98fdb0                       ; 本地化查表（hash）
str x0,[sp,#0x870]                ; 模板放入格式化上下文
add x1,sp,#0xe0 ; mov w2,#0x100   ; 0x100 字节行缓冲区
mov w3,w21 ; mov w4,w20           ; 运行时数值（含回合数候选）
bl 0x993000                       ; printf 风格格式化
b 0xcd614c                        ; 提交
```
index 27 分支还调用 `0xe6a0e0`（字符串助手）与 `0x703ef0`（行提交）。

**这些是原版模板，不需要自建翻译表**；但模板实际渲染出的中文文本、
`w3/w4` 与持续回合的对应关系、最终文本行对象仍缺运行时证据，
本轮**不宣称已截获 Tooltip 文本**。

### 6. 关于 Mouse HID 的判断（等待确认，不执行）

1. 文本生成代码确实存在于 `0xcd3d10` 内，使用原版本地化键（静态，已定位）；
2. 它只能由 TrayIconType 0xf/0x10/0x11/0x13/0x16/0x18/0x1a/0x1b 进入，
   本轮 2765 次每帧调用中这些类型**零出现**（动态正观测）；
3. 当前进程环境无 `DM_MOUSE_HID` / `DM_DD_MOUSE_POINTER`；
   `hle_hid.c:426–430` 的 `pthread_once` 缓存、`front_mac.m:218–230`
   不注册 `NSTrackingMouseMoved`、`publishMouse:` 首行返回，
   `hle_dd_pointer_mac.c` 的 DD 指针桥还要求 Build ID + 游戏内开关 +
   先左键；运行时 `DM_CTL env` 无法改变这些启动时缓存。

「hover 链被静态禁用」是确定结论；「Tooltip 图标类型只能由 hover 产生」
是**语义 + 排除法的强推断，尚缺一次动态观测**（本轮未把 tap/press/长按
模拟成 hover，也未做新的游戏内交互实验）。因此本轮**不提交正式重启请求**：

- **A（零风险，优先）**：不重启、再 attach 同一 pid，只监控 ENTRY 的 x2
  分布与 8 个文本 case，期间用现有 `DM_CTL` 做真实游戏内交互
  （切换选中英雄、打开角色面板等，**不模拟 hover**），看是否出现上述
  8 种 Tooltip 类型。若出现且 KEY/FORMAT 命中，则无需 Mouse HID 即可
  拿到原版文本并继续验证数值与持续回合。
- **B（需确认）**：若 A 仍不出现 Tooltip 类型，重启隔离进程启用
  `DM_MOUSE_HID=1` + `DM_DD_MOUSE_POINTER=1`，游戏内打开 Switch Mouse HID、
  先左键一次，再真实悬停彩色 Buff 图标。**影响：丢弃回合 3 战斗进度**；
  仍只用 `out/hero-audit2/save` 隔离存档，不碰正式存档。**未获确认前不执行。**

### 7. 阶段状态与新增文件

- 阶段 A **仍未完成**：原版 Tooltip 最终文本、格式化参数与持续回合语义、
  `+0x58` 字段、姓名/职业/HP/压力来源，均缺运行时证据。
- 阶段 B/C/D **一律未开始**：没有写共享快照、启动器开关或双端 UI 代码。
- 本轮新增 `out/hero-audit2/tiptext2_r1.log`、`tiptext2_r1_run.out`、
  `shots/post_detach.png`、`shots/r1_cp{1,2,3}.png`（及 `desk_*.png`）
  与本文档追加节。产品代码、输入逻辑、资源、数值、存档零改动；
  无 commit/push。

---

## 第五轮：方案 A —— 真实游戏内交互能否触发 8 个文本分支（2026-11-04 17:00–17:09）

### 1. 执行（动态 · 已执行，未重启 / 未碰存档）

- 继续使用 `dmhost` pid 30958；无 LLDB 附着时为确认交互命令做了三次
  无断点探测（截图 `probe_open.png` / `probe_close.png` / `probe_close2.png`），
  逐张验证后确定：
  - 切换英雄：`R~0.3`（第一轮已动态验证 0/1/2 回绕）
  - 打开角色面板：`T0.158x0.757~0.3`（左下角选中英雄肖像）
  - 关闭角色面板：`T0.867x0.236~0.3`（面板右上角红色 X；
    红色像素聚类定位，第一次 `0.858x0.264` 偏下未命中）
- 观测窗口 `tiptext3.py`：17:07:11–17:08:31（80 s，脚本 `DM_SECS=75`），
  `DM_BASE=0x7002000000`、`DM_MAXHIT=1000000`、全新日志
  `tiptext3_r1.log` / `tiptext3_r1_run.out`。**51 个只读断点全部解析**
  （`unresolved: none`），比第四轮 81 个精简 37%；只保留 ENTRY、
  8 个文本 case、16 KEY、7 STRING/TEMPLATE、7 FORMAT + 7 返回点、
  5 个文本行提交点，去掉了每帧命中的 23 个 APPEND 与 18 个非文本 case。
  每帧只停 ENTRY 一次，帧率影响明显小于上一轮。
- 脚本自行 `proc.Detach()`，`LLDB EXIT=0`（去掉了第四轮末尾多余的
  `-o detach`，不再产生 `Process must be launched.` 报错）。
- `interact_A.sh` 在窗口内执行 5 次英雄切换 + 2 次开/关角色面板
  （`interact_A.log` 有逐条时间戳）。**没有模拟 hover，没有推进战斗回合，
  没有释放技能，没有保存退出**；`T` 是 0.3 s 的 tap，
  低于 `hle_dd_touch.c` 的 0.5 s 长按阈值。

### 2. 完整命中计数（动态 · 可证实的正观测）

| 类别 | 命中站点 | 总命中 |
|---|---|---|
| ENTRY `0xcd3d10` | 1/1 | **5478** |
| 8 个文本 case | **0/8** | **0** |
| KEY `bl 0x98fdb0` | **0/16** | **0** |
| TEMPLATE `bl 0xe6a0e0` | **0/7** | **0** |
| FORMAT `bl 0x993000` | **0/7** | **0** |
| FORMAT 返回点 | **0/7** | **0** |
| 文本行提交 `0x703ef0/0x6f1c40` | **0/5** | **0** |

- 图标类型直方图：`0x7=1096, 0xd=3286, 0xe=1096`（仍是 1:3:1，
  每帧 5 个图标）；**`x4` 恒 0**（`x4 histogram: 0x0=5478`）；
  调用线程恒 **T4**；调用栈恒
  `main+0xcd3d10 → main+0xd650ec → main+0x8f85a8 → main+0x8b7448 → main+0x8b9d28`。
- 交互确实生效（不是假阴性）：`shots/A_panel1.png` / `A_panel2.png`
  显示角色面板打开（特质、基础属性、抗性、战斗技能）；
  `A_closed1.png` / `A_final.png` 显示面板已关闭、仍是**回合 3**、
  戈顿／破盾者 HP 17/20、压力 24/200，与交互前一致。
  `runtime.log` 在窗口内有 `DM_CTL: press 0x80 (hold 0.30 s)` 记录。
- 窗口看护 4 个检查点（17:08:12 / 17:08:30 / 17:08:48 / 17:09:06）
  全部 `runtime.log` 增长、帧号 129300 → 130500 持续推进；
  `SNX → SN` 对应 detach。detach 后帧率恢复到
  `game enqueue p50 81.9 ms`，无崩溃。

### 3. 结论：属于「仍只有 0x7/0xd/0xe」这一分支（动态）

**普通游戏内交互（切换英雄、打开／关闭角色面板）无法触发
TrayIconType 0xf/0x10/0x11/0x13/0x16/0x18/0x1a/0x1b 这 8 个文本分支，
也无法触发本地化查表、格式化或文本行提交。** 51 个断点各自带命中计数器，
因此 0 命中是正观测。角色面板打开时展示的英雄详情走的是另一条渲染链，
不经过 `0xcd3d10` 的 Tooltip 文本 case。

补充观察：`A_final.png` 里出现了一个**技能 Tooltip**（毒蛇之舞 1，
含「可使用次数: 1 / 前进 1 / 2 次护体格挡 / 增益自身」），
它是最后一次输入后游戏自身显示的 UI 反馈，不是我们注入的 hover；
即使屏幕上存在 Tooltip，KEY/FORMAT/LINE 仍是 0 命中。
这不构成异常，也没有违反「不模拟 hover」——但说明
`0xcd3d10` 不是所有 Tooltip 的公共文本入口。

### 4. 关键新证据：这 8 个分支是「状态类型驱动」，不是「hover 驱动」（静态）

把 16 个本地化键按 `adrp/add` 解出并归到 case 区域：

| type | case | 原版本地化键 |
|---|---|---|
| 0xf | `0xcd4a54` | `deathsdoor_title` |
| 0x10 | `0xcd43a0` | `death_blow_resistance_permanent_debuff` |
| 0x11 | `0xcd4b74` | `guard_title` |
| 0x13 | `0xcd4d0c` | `resistance_trap_disarm_format` |
| 0x16 | `0xcd4cbc` | `health_damage_blocks_duration_format` |
| 0x18 | `0xcd4a98` | `daze_format` |
| 0x1a | `0xcd4eac` | `buff_bsrc_last_hero`（其余 `immobilized`/`deathsdoor`/`daze`/`guard`/`guard_no_duration` 在 0xcd4f54 之后的**函数尾部公共区**，不是 0x1a 专属，此处修正第四轮按地址区间的粗归属） |
| 0x1b | `0xcd4250` | `controlled_burn_title` / `turn_start` / `on_move` / `rounds` |

这些全是**特定战斗状态图标**（死门、死亡抗性、守护、格挡、迷惑、定身、
灼烧、陷阱解除）的 Tooltip，而不是任意 Buff 的通用 Tooltip。
当前队伍没有这些状态，只有小丑「鼓舞乐章」产生的
`stress_dmg_received_percent = -0.1` 这类普通 Buff。
`0xcd4f54` 是筛选器空 vector 的汇合点，其后 `0xcd4fc8` 等 KEY 点
属于尾部公共文本区；`w23 = w4` 只在 `0xcd4780`（type 0 case）被使用，
`x4` 恒 0 也说明本轮没有额外的槽位/状态参数传入。

**因此「8 个分支零命中」更符合的解释是：需要英雄身上出现对应的特殊
战斗状态，而不是缺少 hover。** 证据等级：静态键名归属 + 动态排除的
强推断，仍缺一次「制造对应状态后观察」的动态验证。

### 5. 对 Mouse HID 判断的影响（等待确认，本轮不执行 B）

第四轮把「文本分支只能由 hover 产生」列为强推断。本轮的证据
**削弱了这一推断，也不支持「必须启用 Mouse HID」**：
即使开启 hover，若队伍里没有死门／守护／格挡／迷惑／定身／灼烧等状态，
这些 case 仍不会进入。第三、四轮看到的「零文本」更可能是
**状态条件不满足**，而不是 hover 输入缺失。
因此本轮**不提交重启方案 B，不请求批准重启**。

零风险下一步（供用户选择，本轮不自行执行）：

- **A2（推荐，仍不重启、不碰存档）**：在不推进回合、不释放技能的前提下，
  用只读方式确认 8 个分支的入口条件——把每个 case 读取的
  `Actor` 字段／状态位与 `romfs/shared/buffs/base.buffs.json` 的
  `stat_type` / `duration_type` 对应起来，找出哪些状态会产生这些
  TrayIconType。这能判断「需要制造状态」还是「需要 hover」。
- **A3（需要用户授权，会改变战斗状态）**：在隔离存档里受控地让英雄
  获得其中一种状态（例如守护／格挡／灼烧），再挂同一组精简断点，
  观察对应 case 是否命中并截获中文文本与数值。这一步会推进战斗，
  本轮按用户要求未执行。
- **静态补充**：普通 Buff 的 `buff_duration_` / `buff_no_duration` /
  `buff_until_camp_format` 等键**不在**这 16 个 KEY 调用点里，
  说明还有另一处生成普通 Buff Tooltip 文本；需要先定位那个函数，
  才能回答「-10% 所受压力伤害」这类效果的原文从哪来。

### 6. 阶段状态与新增文件

- 阶段 A **仍未完成**：原版 Buff Tooltip 的最终中文文本、数值格式化契约、
  持续回合语义、`+0x58`、姓名/职业/HP/压力来源仍缺运行时证据。
- 阶段 B/C/D **一律未开始**：没有写共享快照、启动器开关或双端 UI。
- 本轮新增 `out/hero-audit2/tiptext3.py`、`interact_A.sh`、
  `interact_A.log`、`tiptext3_r1.log`、`tiptext3_r1_run.out`、
  `shots/probe_open.png`、`probe_close.png`、`probe_close2.png`、
  `pre_A.png`、`A_panel1.png`、`A_closed1.png`、`A_panel2.png`、
  `A_final.png`（及对应 `desk_*.png`），以及本文档追加节。
  已有 `tiptext2.py` / `tiptext2_r1.log` / `text.log` 等时间戳未变。
- 产品代码、输入逻辑、资源、数值、存档零改动；无 commit/push。

---

## 第六轮（A2：纯静态分析，2026-11-04 17:17–）

### 0. 授权边界与实际执行范围

| 项目 | 状态 |
|---|---|
| 静态反汇编、ROMFS / 本地化资源、只读已有 dump / 日志 | **已执行** |
| 附加 LLDB、动态修改游戏状态、推进回合、制造 Buff/Debuff | **未执行**（不授权） |
| 重启、启用 Mouse HID | **未执行**（不授权） |
| 修改产品代码 / UI / 存档、commit / push、A3 | **未执行** |

环境只做观察：`dmhost` pid 30958 存活，无 `lldb` / `debugserver` 附着；
`main` Build ID `ff2bf225…`、`sdk` `b3380482…`、`subsdk0` `bd9af339…`
三项与 `game.tsv` 一致；`main.patched.bin` 文件偏移 == 运行 VA，基址
`0x7002000000` 不变。

新增诊断文件（均位于 `out/hero-audit2/`，gitignore，非产品代码）：
`xref.py`（全模块 BL / ADRP-ADD 交叉引用索引）、`xref_cache.json`、
`a2_cases.py`（8 分支指令级汇总）、`a2_cd3d10_full.txt`、
`a2_cd8540.txt`、`a2_deba10_dec500.txt`、`a2_e04430.txt`、
`a2_cd1c00_caller.txt`。**没有覆盖任何既有日志、dump 或截图。**

证据标签：**[指令级]** = 已从 ARM64 指令读出；**[配置]** = ROMFS 文本；
**[动态-已有]** = 前几轮真实运行观测；**[待验证]** = 还没有运行时证据。

### 1. 函数边界与对前几轮结论的修正

| 项 | 此前记录 | 本轮指令级修正 |
|---|---|---|
| `0xcd3d10` 范围 | 反汇编只到 `0xcd550c` | prologue `0xcd3d3c sub sp,sp,#0xf20`，**ret `0xcd7e6c`**，真实范围 `0xcd3d10–0xcd7e6c` |
| 普通 Buff 文本链 | 认为在 `0xcd3d10` 内或未知 | **`0xcd8540–0xcd8790` 是独立函数**，被 `0xcd3d10` 体内 **11 处** `bl` 调用；`0xdebdc0` / `0xdec330` / `0xdeba10` 在 `0xdexxxx`，全部落在旧断点范围之外 |
| 断点为何零文本命中 | 推测「缺 hover」或「状态不满足」 | **[指令级]** 旧断点只覆盖 `0xcd3d10..0xcd550c`；`0xcd85f0`(本地化)、`0xcd8628`/`0xcd864c`(格式化)、`0xcd8668`(文本行提交) **从未被挂过断点** —— 这是范围遗漏，不是纯逻辑阻塞 |
| `0xcd400c` 遍历之后 | 「直跳尾声，不 fall through 到任何文本代码」 | `0xcd424c b 0xcd4f64` 进入**公共尾部**，`0xcd4fa0 bl 0xcd8540` 就在其中；但 `x2=0xd/0xe` 时 `0xcd4f54` 清零 `x28/x23/x22`，`0xcd4fa0` 传入**空列表**，且 `0xcd4fa4 cmp w8,#0xd; b.eq 0xcd4fe8` → `0xcd4fe8 cbz x28,0xcd775c` 直接结束。**所以这两类图标确实不生成文本**，与第五轮零命中一致 |
| `0xe04430` | 候选「Tooltip 文本行提交」 | 实际是 `HeroDisplay::App::ShowBaseStats` 的属性加成行（符号串 `ZN11HeroDisplay3App13ShowBaseStats…` 在 `0xe04818`）；34 种 stat 循环、虚函数谓词筛选、累加 `+0x48`，用 `buff_%s` 生成说明行 |
| Buff 实例字段 | `+0x50` float、`+0x58` 两个 int32 | **[指令级]** `0xdebdc0` 读 `[x20,#0x48]` float；`0xdec330` 读 `[x1,#0x4c]`/`[x1,#0x50]`；`0xcd85c4` 读 `[x19,#0x54]`；`0xcd85b0` 读 `[x19,#0x188]`；`0xcd8674` 读 `[x19]`。即 **+0x48 数值 / +0x4c 持续 / +0x50 duration_type / +0x54 索引 / +0x00 id**。旧记录不成立 |
| `0xe69af0` | 文本行提交（第三轮） | 通用 vector 追加助手（第四轮已修正，本轮确认 5231 个调用点） |

**已有 dump 校准 [动态-已有 + 指令级]**：`dumps/actor2_all.bin` 中
`-0.1000` 位于文件 `0xf10`。按 `0xdebdc0` 的 `[+0x48]` 反推实例基址
`0xec8`，则该实例 `+0x4c=3`、`+0x50=9`、`+0x54=1`、`+0x60` 起为
`JESTTuneStressResistance1\0`、`+0x151=1`、`+0x188=0` —— 与
`0xdebdc0` / `0xdec330` / `0xcd8540` 读取的字段逐一吻合。
**但该 dump 的起始地址未记录，绝对偏移需重新对齐**，此处只证明相对
字段关系，不作为生产偏移量使用。

### 2. 交付一：特殊状态 Tooltip 路径图（8 个分支）

**共同分派链 [指令级]**

```
0xcd1c00  bl 0xcd3d10
   x0 = 输出 GuiTooltipParameters* (x24)      x1 = Actor* (x21)
   x2 = TrayIconType  <- [sp+0x50]（上层 0xccf0a0 起的大函数，
                          0xccf0b8 stp x24,x23,[sp,#0x50] 保存的 x24）
   x3 = 图标资源 id (x20)                     w4 = 槽位索引 (w28)
   s0..s3 = 位置/尺寸
0xcd3fbc  cmp w20,#0x1b ; b.hi 0xcd47dc      ← 越界即默认分支
0xcd4000  ldrh w11,[0xf1cb52 + x2*2] ; 0xcd4008 br x10（基 0xcd400c）
          ⇒ 唯一分派条件就是 w2 = TrayIconType
```

`w23`(=x4) 全函数只在 `0xcd4780`（case 0x00）用作数组元素数比较
`cmp x8,x11`，**不是 hover 标志**；函数内没有读鼠标坐标或悬停状态的指令。

**逐分支 [指令级]**：共享尾部（`0xcd5xxx–0xcd7xxx`）是多个 case 公用的，
下表把「case 入口专属指令」与「共享尾部」分开列出，避免误归属。

| x2 | case 入口 | case 内部条件 | 读取的 Actor 字段 | 虚函数谓词 | 本地化键（原版） |
|---|---|---|---|---|---|
| `0xf` | `0xcd4a54` | 入口无条件，直接生成标题行 | 入口无；共享尾部 `+0x1268`(`0xcd5aa4`)、`+0x460/+0x468`(`0xcd7334`) | 共享尾部 `vtable+0x30` 筛选 buff（`0xcd7390`），`0xcd748c → 0xcd8540` | `tray_icon_tooltip_deathsdoor_title`、`…deathsdoor`、`…death_blow_resistance_permanent_debuff` |
| `0x10` | `0xcd43a0` | `ldr s0,[x25,#0x1268]` × 全局倍率 × 100 → `cmp w21,#1 ; b.lt 0xcd7080`（≥1 才出文本） | `+0x1268`；共享尾部 `+0x460/+0x468` | 共享尾部 `vtable+0x30`（`0xcd70dc`），`0xcd71d8 → 0xcd8540` | `…death_blow_resistance_permanent_debuff`（`0x993000`, `w3`=百分比） |
| `0x11` | `0xcd4b74` | 入口无条件；`0xcd4bd0` 起遍历 buff 集合 | 入口 `bl 0x9cb740(Actor*, out)` 取 guard 信息；`+0x460/+0x468` | **8 处 BLR**：`vtable+0x150/+0x10/+0x30/+0x38` 等；`0xcd5d94/0xcd5dec/0xcd5e58 → 0xcd8540` | `…guard_title`、`…guard`、`…guard_no_duration` |
| `0x13` | `0xcd4d0c` | `vtable+0x20 → x20 ; cbz x0,0xcd5e00`（必须取到 combat/raid 对象） | 入口仅 vtable；后续 `[x20,#0xf8c]`、`[x0,#0xb34]`、`[x20,#0x127e]` | **4 处 BLR**：`+0x20 / +0x38 / +0x1a8(w1=7) / +0x138`；`0xcd60b8 → 0xcd8540` | `resistance_trap_disarm_format` |
| `0x16` | `0xcd4cbc` | `ldr w20,[x25,#0x128c]`；`ldr w21,[x25,#0x11a4]`；`cmp w20,#1 ; b.lt 0xcd611c` | `+0x128c`、`+0x11a4` | **无 BLR** | `…health_damage_blocks_duration_format`（`w3`=+0x11a4、`w4`=+0x128c）、`…health_damage_blocks_format` |
| `0x18` | `0xcd4a98` | 入口无条件；`ldr s0,[x25,#0x1284]` → `fcvtzs w3` | `+0x1284` | **无 BLR** | `…daze_format`、`…daze` |
| `0x1a` | `0xcd4eac` | 入口无条件生成 `buff_bsrc_last_hero` 行 | 共享尾部 `+0x460/+0x468`(`0xcd532c`) | 共享尾部 `vtable+0x30`（`0xcd538c`），`0xcd6ccc/0xcd6d94/0xcd6dec → 0xcd8540` | `buff_bsrc_last_hero` |
| `0x1b` | `0xcd4250` | 全局 `0xb1a27000+0x190 → [x20,#0x4858..#0x4860]` 列表（元素 `0x18`），逐项 `cmp w8,w0` 匹配 `vtable+0x30` 返回值、`cmp w8,#1 ; b.lt` | 入口 vtable；全局表 +0x4858 数组 | 1 处 BLR（`vtable+0x30`） | `…controlled_burn_title / turn_start / on_move / rounds` |

**与 `base.buffs.json` 的关系 [配置]**：文件里静态存在
`deathsdoor*`(5)、`*Guard*`(10)、`TRAPRESIST*`(33)、`ignore_stealth` 等 id，
且 `stat_type` 词表含 `resistance / combat_stat_add / combat_stat_multiply /
stress_dmg_received_percent`（137 次）等，`duration_type` 词表为
`combat_end / quest_end / activity_end / idle_start_town_visit / quest_complete`。
**但 8 个 case 的指令里没有按 JSON id 查表**：它们读 Actor 的固定字段
（`+0x1268 / +0x1284 / +0x128c / +0x11a4`）和编译期全局表
`0xb185e5e4 + 0x58*id`、`0xb186068c + 0x4c*idx`。因此
「哪个 case 对应哪条 JSON 定义」**没有指令级映射**，不能按名称判定。

**是否依赖 hover**：**[指令级]** 8 个分支本身**不检查 hover**，进入只由
`x2` 决定，参数中也没有鼠标/悬停状态；`x4` 是槽位索引。
**[待验证]** `x2` 由上层函数 `0xccf0a0` 提供（`[sp+0x50]` 保存的 x24），
上层是否在 hover 时才产生这 8 个值，本轮没有追踪到写入点，不能下结论。
**[动态-已有]** 第五轮普通交互（切换英雄、开关角色面板）时 `x2` 只有
`0x7/0xd/0xe`、`x4` 恒 0，8 个 case 全部 0 命中。综合结论应表述为：
「分支内部与 hover 无关；上层触发条件未静态确定」，而不是「已证明与
hover 完全无关」。

### 3. 交付二：普通 Buff Tooltip 路径图（从 Buff 实例到原版中文文本）

```
[动态-已有]  Actor +0x460 / +0x468 = vector<Buff::Instance>，元素步长 0x1d8
             第二轮实测：-0.1000（鼓舞乐章），第四轮 APPEND 3871 次证明遍历命中
                  │
[指令级]  0xcd400c (x2=0xd/0xe)：遍历 +0x460..+0x468，
          `ldr x8,[pred]; ldr x8,[x8,#0x30]; blr x8` 谓词筛选，
          命中者把 `ptr+8` 收进 Buff::Instance* 数组
                  │
[指令级]  0xcd4f54/0xcd4f64 公共尾部 → 11 处 `bl 0xcd8540`
          （0xcd4f40 / 4fa0 / 5d94 / 5dec / 5e58 / 60b8 /
            6ccc / 6d94 / 6dec / 71d8 / 748c）
                  │
[指令级]  0xcd8540(x0=GuiTooltipParameters*, x1/x2=Buff::Instance* begin/end,
                   x3=Actor*, w4=分组标题, w5=谓词结果, w6=持续文本开关)
          ├─ 0xdeba10  GetBuffTrayBuffInstanceList 聚合 [指令级]
          │    输出 vector 元素 0x1d0；去重合并条件：
          │    [+0x00] id、[+0x44]、[+0x5c]、[+0x50]、[+0xf4] 相同
          │    且 |[+0xb0]| 差值 < 常量 → [+0x48] 数值相加、[+0x4c] 取 max
          │    ⇒ 多个同源 Buff 的合并规则是指令级可见的，未做过运行时验证
          ├─ 逐实例准入 [指令级]：[+0x188] 非空 → 文本；
          │    为空则 `ldr w8,[x19]; sub w9,w8,#0x26; cmp w9,#0x35` 位掩码
          │    `0x0022000800000069`，再按 [+0x151] / 全局表 +0x48 判定
          ├─ w4=1：0x8aa930(`buff_%s` @0xea3d35, 索引 [+0x54]
          │          → 0xb186068c+0x4c*i) → 0x98fdb0 → 0xe6a100 拼分组标题
          ├─ w6=1 → 0xdec330（持续回合文本）
          ├─ w6=0 → 0xdebdc0（名称 + 数值文本）
          └─ 0x703ef0(GuiTooltipParameters*, char[0x100]) 追加一行文本
             （同型 0x6f1c40；`ldp x20,x8,[x0,#8]`，元素 0x100 字节）
```

**两个格式化函数 [指令级]**

- `0xdebdc0`：
  - 名称 —— `[x1,#0x188]` 非空则直接 `0x98fdb0`；否则 `0xdebbd0`：
    `[x19]` id → `0xb185e5e4 + 0x58*id` 表（读 `+0x44/+0x48/+0x51`）
    → 选模板 → `0x8aa4b0` → `0x98fdb0`。
  - 数值 —— `ldr s0,[x20,#0x48]`；按该表 `+0x48` 的 0/1/2/3 分支处理
    （`fmul s0,s0,100.0` 即 0x42c80000、`fneg` 取负、`fcvtzs w3`），
    最后 `0x993000` 格式化到 0x100 字节缓冲。
- `0xdec330`：`ldp w9,w8,[x1,#0x4c]` → `w9=[+0x4c]`、`w8=[+0x50]`；
  `cmn w9,#1`（`-1` = 无持续）分支选择
  `buff_duration_%s_format` / `buff_no_duration` /
  `buff_until_end_of_raid_format` / `buff_until_camp_format`
  （引用点 `0xdec374 / 0xdec3d0 / 0xdec3f4 / 0xdec420`，**不在 0xcd3d10 内**）；
  `0x98fdb0` → `0xdebdc0` → `0x993000(w4 = [x20,#0x4c] 回合数)`。
- `0x98fdb0` [指令级]：`h = h*0x35 + byte(key)` 哈希 → `0x992270` 查表 →
  返回 `(文本指针, 长度打包)`；`localization/schinese.loc2` 是
  **NUL 分隔 UTF-8 文本池（90442 条，无明文 key）**，故按 key 搜不到。
- `0x993000` [指令级]：vsnprintf 风格，输出上限 `w2=0x100`，
  整数参数 `x3/x4…`、浮点参数 `q0..q7`。

**原版中文文本 [配置]**：`schinese.loc2` 中存在模板
`%+d%%所受<c>]qlHkB压力</c>伤害`、`%s(效果持续到任务结束)`、
`%+d%%队伍所受<c>]qlHkB压力</c>伤害`、`<c>]qlHkB压力</c>%+d/每回合，持续%d回合`
等。屏幕上的 `-10%所受压力伤害` 与 `base.buffs.json` 的
`JESTTuneStressResistance1 = stress_dmg_received_percent / -0.1`
在数值链上闭合：`-0.1 → ×100 → -10 → %+d%%所受…伤害`。
**但 key → loc2 偏移的哈希映射、`buff_%s` 的 %s 具体取值尚未静态解出
[待验证]**，因此不宣称已逐字复现原版 Tooltip。

**并行候选路径 [指令级，归属待验证]**：`0xdec330` 另有 2 个调用点
`0xe009c8`（其后 `0xe009d8 bl 0xe69af0` 直接追加文本行）与 `0xd46374`；
`0xe04430`（`ShowBaseStats`）也用 `buff_%s` + `str_stat_*` 生成属性加成行。
它们可能是角色面板 / 技能 Tooltip 的独立文本链，与 tray icon 链并行。

### 4. 证据等级汇总与仍然缺失的运行时证据

| 结论 | 等级 |
|---|---|
| 8 个分支由 `x2` 分派、分支内不读 hover、各分支的 Actor 字段与本地化键 | **[指令级]** |
| 普通 Buff 名称 / 数值 / 持续回合 / 文本行提交的完整调用链 | **[指令级]** |
| `Actor+0x460` 存在真实 Buff、已有 `-0.1000`、字段相对关系吻合 | **[动态-已有]** + **[指令级]** |
| 原版中文模板存在于 `schinese.loc2`、Buff 定义 `stat_type/duration_type` | **[配置]** |
| 上述函数**在真实运行时是否被调用**、由哪些 `x2` 触发 | **[待验证]**（本轮禁止 attach） |
| key 哈希 → loc2 文本偏移、`buff_%s` 的 %s 取值、最终中文逐字对照 | **[待验证]** |
| `+0x4c` 剩余回合 / `+0x50` duration_type 的语义与回合推进后的变化 | **[待验证]** |
| 上层 `x2` 构造逻辑与 hover 的关系、免悬浮通用枚举是否每帧可用 | **[待验证]** |
| 姓名 / 职业 / HP / 压力字段来源、`RaidDisplay → 当前 Actor` 映射 | **[待验证]** |

### 5. 下一步建议（本轮不自行执行）

1. **A2-followup（推荐，零风险、不制造状态、不重启）**：在现有
   `dmhost` 30958 上挂极少量只读断点：`0xcd8540`、`0xdeba10`、
   `0xdebdc0`、`0xdec330`、`0x703ef0`，以及 `0x98fdb0` / `0x993000`
   的返回点；同时记录 ENTRY 的 `x2` 分布。若命中，即可直接读到
   `char[0x100]` 里的原版中文行、数值与回合数，验证 key→文本映射。
   若全部零命中，则说明普通 Buff 文本由 `0xe009c8` / `0xd46374`
   那条并行链生成，应转去追踪它。**不需要 Mouse HID、不需要 A3。**
2. **A3 仍不授权**：制造战斗状态对回答「普通 Buff 通用数据路径」没有必要。
3. 阶段 A **仍未完成**；阶段 B/C/D **一律未开始**，没有写共享快照、
   启动器开关或双端 UI。产品代码、输入逻辑、资源、数值、存档零改动；
   无 commit/push。

---

## 2026-11-04：英雄状态面板产品实现（第七轮）

本轮按要求停止逆向，直接交付功能。本节只记录**实现**与**验证结果**。

### 数据源（全部运行时证据，零猜测）

| 数据 | 来源 | 证据 |
|---|---|---|
| 全局游戏单例 | `[main+0xb1a27190]` | 指令 `0xd6b428` `ldr x10,[0xb1a27000,#0x190]`；实测 `0x70b3a27190 → 0x700926d000` |
| 当前选中/行动英雄 Actor* | `[G+0x3e8]` | 指令 `0xd6b430` `ldr x8,[x10,#0x3e8]`；实测 `0x7008b00010`（与 Buff vector 完全吻合） |
| Buff 集合 | `Actor+0x460/+0x468`，步长 `0x1d8` | 动态验证（第三/五轮），本轮再次实测 8/9/6 条 |
| 效果数值 | `Instance+0x50` float | 实测 `0.15`、`0.1`、`-0.1` |
| 内部效果 id | `Instance+0x68` | 实测 `\x00STRESSDMG10`、`\x00BLEEDRESIST15`：**首字节是 0x00 分隔符，id 从 +0x69 开始** |

**读取方式**：`vm_read_overwrite` 在 `OBS_DD_TOUCH_FRAME` 的 gate 回调（游戏线程）
里失败（返回错误），与现有 HLE 全部使用裸 `memcpy` 的事实一致。改为
`mincore()` 逐页确认后 `memcpy`，未映射页使样本无效而不是崩宿主。

### 新增/修改文件

新增：`dm/host/dd_hero.h`（快照结构）、`dm/host/hle_dd_hero.c`（游戏线程采集、
mutex 快照、generation、开关关闭即停止）、`dm/host/dd_hero_names.h`（由
`scripts/gen_dd_hero_names.py` 从 RomFS 的 `base.buffs.json` + `schinese.loc2`
派生，809/2020 条有中文短语）、`scripts/tests/test_hero_panel_settings.py`。

修改：`hle_dd_touch.c`（在 `dd_frame_tick` 开头调用 weak `dd_hero_frame_tick()`，
在其 `dd_ready()` 之前，因此与触控策略完全独立；不改任何输入分支）、
`front_ios.m` / `front_mac.m`（双端面板：iOS `userInteractionEnabled=NO`，
macOS `hitTest` 返回 nil）、`settings.tsv`（`DM_DD_HERO_PANEL toggle 默认 0`）、
`Localization.swift`（中英文）、`LauncherSettings.swift`（归入高级区）、
`Makefile`（头文件依赖）。

**未改动** `patches.py`／OBS 表：采集复用已有 `OBS_DD_TOUCH_FRAME`，所以
现有 prepared 输入在重新 rewriter 后仍然兼容（见下）。

### 验证结果

- **macOS 成品 App** `out/macOS/Dungeon1.app`（3.3 G，内置 RomFS + AOC，
  ad-hoc 签名）：用隔离存档副本启动、进入地牢/战斗，左侧出现半透明面板，
  逐行显示 `所受压力伤害 +10% / -100% / -20%`、`减益抗性 +15%`、
  `英雄决心等级 +5%` 等，数值来自 `Instance+0x50`。
- **iOS** `out/iOS/Dungeon1.ipa`（1.6 G，内置资源）：`compile_check.py`
  137 源文件 + 6 Swift，0 失败；`dm/launcher.json` 含新开关。**未真机运行**。
- 测试：`scripts/tests` 64 项通过（含新增 7 项）、`dm/tools/tests` 81 项通过
  （跳过 4）、host C 测试通过、`check_public.py` issues 为空。
- **prepared 输入需要重建**：`patches.py` 在上次提交时新增了 `OBS 32`，
  旧 prepared 缺该 gate，构建前用原始 NSO 重新 rewriter 了 main/sdk/subsdk0
  到 `out/work-hero-prep`（`VALIDATE OK`）。

### 未实现与已知限制（不伪造）

1. **姓名 / 职业 / HP / 压力**：Actor 内有 `max_hp` 等属性表与疑似 17/24 的数值，
   但没有变化验证，按“不猜偏移”原则**留空**，面板不显示。
2. **敌方（右侧）**：`RaidDisplay+0x3a40` 选中字段与 `+0x1420` 镜像 Actor 已验证，
   但当前进程的 RaidDisplay 单例链未定位；快照已预留 `enemy_*` 字段与右侧面板，
   `enemy_valid=0` 时隐藏。**当前不显示敌方**。
3. **剩余回合**：`Instance+0x58` 两个 int32 语义未验证，不显示。
4. **城镇/叙事不过滤**：`G+0x3e8` 在城镇仍是有效 Actor，面板会显示
   `HERO —` 或怪癖效果；缺“是否在地牢”的可靠信号。
5. 中文名来自 RomFS 模板派生（809/2020），未匹配的显示内部 id（如
   `WARDING_STANCE_DMG_D1`），不是编造译文。

**产品代码改动仅限上述文件；未 commit/push；未改存档、输入策略、升级过滤。**

## 第八轮：Buff 行数据质量修复（显示层与解析层）

前一轮的面板能出数据，但截图暴露出四类问题：内部 ID 直接显示（`build_to_finale_dmgL`、
`AWLER_STRESSDMG_D1`）、单字符残片（`p`、`z`）、多个 `+100%`、同一效果重复多行。
本轮只修这些，不扩展功能。

### 字段偏移的最终结论（推翻上一轮报告里的自相矛盾）

用当前进程的 9 个实例逐条对照 `base.buffs.json` 的定义数值，6 条完全吻合：

| 偏移 | 含义 | 证据 |
|---|---|---|
| `+0x50` | float 数值 | JEST −0.1、BLEEDRESIST15 0.15、RESOLVECHECK5 0.05、QUIRK_crypts 0.2、STRESSDMG10 0.1、BRAWLER_D1 0.1 |
| `+0x54` | 回合数（−1 = 无） | JEST 3、怪癖 −1（仍不显示） |
| `+0x68` | char[] Buff ID，文本从 +1..+3 字节处开始 | 同一 vector 里 `BRAWLER_STRESSDMG_D1` 与 `"\0\0AWLER_STRESSDMG_D1"` 并存 |
| `+0x58/+0x5c` | 两个枚举字，语义未验证 | 不读取 |

审计文档 A2 那组「+0x48 数值 / +0x4c 回合 / +0x50 duration_type」描述的是
`main+0xdeba10` 产出的**聚合**结构（步长 0x1d0），不是这里的 `Buff::Instance`
（步长 0x1d8）：在实例上读 `+0x48` 恒为 0。上一轮实现里的 `+0x50` 才是对的。

### 三个真因

1. **ID 截断**：游戏会把 id 缓冲区开头 1–3 字节清零，`+0x68` 直读得到
   `AWLER_STRESSDMG_D1`。现在先取标识符形状的 token（最多跳过 3 个不可打印字节、
   遇到非 `[A-Za-z0-9_]` 立即停止、长度 ≥3），再用 RomFS 的 2020 条 id 做
   **唯一后缀匹配**恢复规范 id；不唯一就当作无法识别。
2. **单字符残片**：旧代码跳过全部不可打印字节，会一直扫到相邻字段，于是把 `p`、`z`
   当成名字。同一个有界扫描同时修掉了这个问题。
3. **+100% / 类型混淆**：游戏把大多数属性存成百分之一（命中 0.05 = +5），速度存整数
   （2 = +2），百分比属性另外加 `%`。生成器现在为每个 id 输出 `amount / pct / mul`
   三列，`mul=100` 表示百分之一，`pct=1` 才加百分号。

### 未匹配与重复

- 生成器为 1995/2020 条 id 生成了中文名（模板仍取自 `schinese.loc2`，带
  「。的了时」等虚词的句子被排除）；**23 条食物/折扣类效果没有名字，面板直接不显示**，
  绝不回退到内部 id。运行时怪癖（`QUIRK_*_STRESSDMG_*`）若不在表内同样跳过。
- 同一标签 = 同一属性 = 同一语义：合并成一行并**按数值相加**（与 `0xdeba10` 的聚合一致），
  右侧显示 `×N`；不同持续时间的同名效果也合并，因为面板不展示回合数。
- 数值保护：百分比实例 |v| > 1.0 丢弃；恰好 ±1.0 而定义数值 < 1.0 的实例丢弃
  （活体 vector 里出现过同一 id 的 1.0 与 0.1 并存，且正是 id 头被清零的那条）。

### 改动与验证

- `scripts/gen_dd_hero_names.py`：重写匹配（子类型优先、虚词过滤、`%%` 判定百分比、
  后缀消歧、`amount/pct/mul` 三列）。
- `dm/host/hle_dd_hero.c`：`hero_token()` 有界提取、规范 id 解析、类型感知格式化、
  同标签合并；`dm/host/dd_hero.h` 的快照行改为 `label/value/positive/count`。
- `front_mac.m` / `front_ios.m`：数值列右对齐（macOS 逐行绘制，iOS 用右对齐制表位），
  显示 `×N`，不再回退显示 id。
- 实测（成品 App，`out/macOS/Dungeon1.app`，回合 4 战斗）：
  `伤害 ×2 +60%`、`所受压力伤害 ×3 −110%`；三者定义数值 0.1 / 0.2 / −1.0 相加即 −1.1。
- `scripts/tests/test_hero_buff_names.py` 新增 5 项断言（含 JEST 样本、无 id 泄漏、
  整数属性不带 %）。70 项脚本测试、Host C 测试、iOS compile_check（137 文件 + 6 Swift）全通过。

## 2026-11-05：改用游戏原版 Buff 格式化链（第九轮）

按验收要求放弃全部自定义解析（loc2 模糊匹配、amount/pct/mul 推断、后缀恢复、
按标签合并、±1.0 丢弃），面板的每一行改为**游戏自己的函数**生成。

### 复用的原版函数（全部 main 镜像内偏移，Build-ID 把关）

| 偏移 | 职责（本轮以反汇编确认的签名） |
|---|---|
| `0xcd8540` | 行生成总入口：`f(GuiTooltipParameters*, Instance** begin, Instance** end, Actor*, w4 组标题, w5 有战斗对象, w6 持续开关)` |
| `0xdeba10` | 聚合去重（输出 0x1d0 元素；自己的身份字段与合并规则），由 0xcd8540 内部调用 |
| `0xdebdc0` | 名称+数值格式化（读 `+0x188/+0x00/+0x48/+0x151`），走 `0x98fdb0` 查表、`0x993000` 格式化 |
| `0xdec330` | 持续时间格式化（本轮未启用，w6=0 走名称+数值） |
| `0x703ef0` | `std::vector<char[0x100]>::push_back` —— GuiTooltipParameters 头部就是 begin/end/cap |

关键结构事实（反汇编 + 活体 dump 双证）：`GuiTooltipParameters` 头部只是
`vector<char[0x100]>`（`0x703ef0` 只读 +0/+8/+0x10），因此宿主可以自己持有
这个向量；`Buff::Instance*` = 原始 vector 元素 +8（`0xcd4080/0xcd7398` 原样
收集 `element+8`），因此实例的 `+0x48/+0x4c/+0x50` 落在原始元素
`+0x50/+0x54/+0x58` —— 与活体 dump 完全吻合，此前的基址混淆就此统一。

tray 仿函数（vtable `0x1184c40`，谓词 `0xcd8fc0` 无状态）**有意不使用**：它按
正负把效果分给 0xd/0xe 两个图标，并整体丢弃若干 stat 类别（压力类就在其中，
JEST 将永远不显示）。改为把全部实例交给 `0xcd8540`，由它**自己的准入规则**
（`+0x188` 键、id 位掩码 `0x0022000800000069`、`+0x151` 标志）和聚合决定显示 ——
这些规则全部是原版代码，本项目不再有任何一条自己的过滤/合并/换算规则。

`w5` 按游戏原样传「Actor 有战斗对象」（Actor vtable+0x20 非空，`0xcd7458`）；
w4=0（无组标题）、w6=0（名称+数值格式）。

行内的游戏颜色协议 `<c>` + 6 字节色码 + `</c>` 在拷贝进快照时剥离
（游戏渲染器自己解释它，宿主 UI 画纯文本），文字与数值一字不动。

### 移除的自定义代码

`scripts/gen_dd_hero_names.py`、`dm/host/dd_hero_names.h`（生成表）及其测试
整组删除；`hle_dd_hero.c` 不再包含任何 loc2 扫描、id 翻译、数值换算或合并逻辑。

### 实际运行验证（成品 App `out/macOS/Dungeon1.app`，回合 4 战斗）

```
HERO
终曲：+30%伤害            （蓝色）
+10%所受压力伤害           （蓝色）
后退时-100%所受压力伤害     （橙色）
-20%所受压力伤害在遗迹      （橙色）
```

与游戏自己的技能提示「終曲: +30%伤害」同源一致（同一格式化链）。五个实例 →
四行：`build_to_finale_dmgL/H`（同 kind）由原版聚合合并为一行 +30%，三条压力类
各自成行，无错误合并。压力类文本与 JEST 同属一个 stat 类别（同一 kind 表模板
`%+d%%所受压力伤害`），JEST 本身不在当前英雄身上，机制已由同类验证。
切换英雄后面板跟随 `[G+0x3e8]` 自动更新（战斗内手动切换本就不可用）。

回归：65 项脚本测试、Host C 测试、iOS compile_check（137 文件 + 6 Swift）全过。
修复构建前置：AOC 目录混入 Finder 的 `.DS_Store` 导致清单校验失败，删除后通过。

## 2026-11-05（二）：按截图反馈收敛面板内容（第十轮）

用户反馈四点：只显示血条上方的战斗效果（不要特质）、显示持续时间（X回合）、
显示角色姓名与职业、显示生命/压力数值。

### 本轮新增的原版数据

| 字段 | 来源 | 验证 |
|---|---|---|
| 效果持续回合 | 同一条链的 w6=1 调用 → `0xdec330` 直接渲染**整行**：名称+数值+(N回合) | 实测「终曲：+30%伤害(7回合)」 |
| 英雄姓名 | `Actor+0x08`，游戏存好的已本地化中文名 C 串 | 两位英雄（麦克道尔/戈顿）与底栏一致 |
| 当前生命 | `Actor+0x80` float | 麦克道尔 17、戈顿 10，与屏幕一致 |
| 当前压力 | `Actor+0x1274` float | 76、20，与屏幕一致 |
| 压力上限 | `Actor+0xab8` float | 200（两位一致） |
| 职业 id | Actor 属性包 `heroClass` 键 → 长度前缀串（jester/shieldbreaker 实测） | 位置随实例漂移，按姓名缓存 |

**生命上限不在 Actor 里**（0x6000 全量扫过，int/float/double 均无 19/20）——
游戏按职业基础值+修正实时计算，本轮不做推导，面板生命显示当前值。

### 只保留战斗效果

`Instance+0x54`（原始元素 +0x5c）是游戏自己的分组索引：战斗效果=1、
特质(quirk)效果=5（两次会话 8 个实例全部吻合，另有无敌类=9 的旁证）。
面板只传 group==1 的实例给 `0xcd8540`，特质行随之消失。

### 一次崩溃与修复

给 `0x98fdb0` 传一个**不存在的 key** 会崩（缺失 key 的回退链在游戏线程外
不可入）——「hero_class_name_<id>」推想的职业名键实测 miss 并崩掉宿主两次。
已移除该查表调用；职业中文名列为未完成（职业 id 已取到，英文）。

### 界面

面板头部增加：姓名、`生命 N`（仅战斗中显示，战场外该字段为 0）、
`压力 N/200`；效果行如「终曲：+30%伤害(7回合)」。

回归：65 项脚本测试、Host C 测试、iOS compile_check 全过。

## 2026-11-05（三）：漏行、职业名与持续时间（第十一轮）

用户反馈三点：戈顿 3 个 Buff 只显示 2 个（缺「2伤害 下次行动」）、没有职业名、
没有血量上限。

### 1. 漏掉的 Buff —— 原因是原版链的准入过滤，改为绕过它

`0xcd8540` 的准入（0xcd8674 起）按聚合行首的 stat 索引查掩码
`0x0022_0008_0000_0069` 与两张全局表；stat 5（「下次行动伤害」）被它丢弃——
游戏自己的托盘也只为该 stat 显示图标，文字来自别的路径。而实例向量实测
e2+e4（stat 5，1.0+1.0，回合 1/2）正是用户看到的「2伤害 下次行动 (2回合)」。

修复：不再调用 `0xcd8540`，直接复刻它的内核——`0xdeba10` 聚合 → 逐行
`0xdec330`（整行=名称+数值+持续回合）→ `0xe69a20` 释放（嵌套向量
row+0x158/0x170 与行数组，与 0xcd8540 尾部逐字节一致，零泄漏）。每行仍是
游戏自己的文本，只是不再有准入丢弃。Dedup：两个不同 stat（伤害 low/high）
可能渲染出逐字相同的行，按原样去重（与托盘一致只显示一条）。

### 2. 职业名 —— 键形状已捕获，查表成功

挂 `0x98fdb0` 被动捕获（30 秒读档期），抓到游戏自己查询
`hero_class_name_<id>`（全部 16 个职业，含 shieldbreaker）——第十轮的崩溃
其实是当时从错误缓冲提取到垃圾 id 导致的 miss。现在用干净的
class_id（属性包 `heroClass` 键）查表即可：jester→小丑、shieldbreaker→破盾者。

提取的正确性：属性包节点由分配器放在 Actor 之后，但间距不固定（0x3000–
0x30000），固定窗口要么漏要么**跨到下一英雄抢类名**（修女被标成小丑）。
改为以「下一个同 vtable Actor 对象」为界（每英雄一次向前扫描并缓存），
绝不跨英雄；越界找不到就如实不显示职业。

### 3. 血量上限 —— 确认不在 Actor 中

三英雄（19/20/24）差分 + 全编码（float/u32/u16/u8）扫描 0x6000 均无；
属性包 `max_hp` 节点值与上限无关。上限是游戏按职业配置+修正实时计算的
（tray case 0x7 用 `0xb3cfe0` 聚合修正值即为一例）。不自行推导，面板继续
显示当前生命。

### 4. DoT 行的嵌套标记

流血/中毒行由 `0xdec330` 产出时带嵌套键
（`[<buff_stat_tooltip_hp_dot_bleed>](2回合)`），由游戏的文本渲染器在绘制
时解析。从外部调 `0x98fdb0` 解析它有 miss 即崩的风险，面板选择丢弃这类行
（托盘本来就以图标显示 DoT），绝不显示原始标记。

### 验证与产物

实测（隔离存档、回合 4-5 战斗）：`麦克道尔 小丑 / 生命 13 压力 100/200 /
+30%伤害 (5回合) / +10%所受压力伤害 (3回合)`——职业名正确、终曲两实例
合并为一行、持续回合随游戏回合递减（6→5）、受伤后生命实时变化。
66 项脚本测试、Host C 测试、iOS compile_check（137+6）全过。
产物重建：`out/macOS/Dungeon1.app`（3.3G）、`out/iOS/Dungeon1.ipa`。

## 2026-11-05（四）：终曲重复行、破盾者职业（第十二轮）

用户反馈：小丑 4 个 Buff 只显示 2 个且终曲出现两行（其中之一其实是暴虐标
志的 Buff）；破盾者的职业没显示。

### 终曲双行 → 恢复同文去重

伤害 low / high 是两个真实 Buff（聚合后各自成行），但渲染文本逐字相同，
游戏托盘也只给一个终曲图标——按用户确认恢复「逐字相同行只保留一条」。
（第七轮曾按此去重，第九轮重构时误删。）

### 暴虐（状态图标）与破盾者的 +20% 伤害

托盘谓词 main+0xcd8fc0 完整解码：成员资格 = stat 表 entry+0x56 / 元素
+0x1d2 / stat 44 / entry+0x45 之一置位，或**组表**
0xb186068c[group*0x4c+0x48] bit0。按它实现（两个极性图标取并集）。
实测：暴虐所授予的组 3 Buff（DMGL20/DMGH20 等）组表标志为 0 —— 游戏自己
也不把它们显示为图标；暴虐的图标是**状态**（affliction_type_id，属性包内
实测 +1），不是 Buff 行。面板本轮未显示状态行（下一轮可从属性包的
affliction_type_id 读取）。

### DoT 行的最终形态

stat 5 = hp_dot_bleed（stat 表 entry5 的名字段实测）。其名字键
buff_stat_tooltip_hp_dot_bleed 在游戏表中**不存在**（41 个候选逐一调用
游戏查表验证，16 个缺失，全部 DoT 类）——游戏托盘对这些只有图标。用户看
到的「2伤害 下次行动 (2回合)」来自施加弹字，用托盘格式键
tray_icon_tooltip_bleed_format = "%d伤害下次行动(%d回合)"（oracle 取到）。
面板对 DoT 行改用同一游戏模板 + 行自身聚合数值与回合
（hero_fmt_two），实测输出「1伤害 下次行动 (1回合)」与游戏弹字一致。

### 破盾者职业

两处修正：(1) 类扫描边界改为「下一个**活的** Actor」（同 vtable 且名字
非空），跳过未映射页而不是停止——此前误把野 vtable 命本当边界导致截断；
(2) 属性包节点填充有变体（麦克道尔是 u32 长度前缀，哥伦布斯多一个杂散字
节），固定 +10 读长度会得到垃圾而拒绝——改为键后寻找首个 ≥3 字符的标识
符串并用 romfs heroes/ 的 19 个职业 id 白名单验证。

### 回归

66 项脚本测试、Host C 测试、iOS compile_check（137+6）、check_public 全过。
验证实例（隔离存档）实测：`麦克道尔 小丑 / 生命 13 压力 95/200 /
終曲：+30%伤害(6回合)`（单行）与 `戈顿 … / 1伤害 下次行动 (1回合)`（与
游戏弹字同文）。双端产物**未重建**（按用户指示，待验收后统一构建）。

## 2026-11-06：点击查看、Affliction 与护体格挡（第十三轮）

本轮把面板从「自动跟随行动英雄」改为「玩家点击查看、目标锁定」，并补齐两类特殊状态。

### 数据源（全部原版路径，零新增补丁点）

| 数据 | 来源 | 说明 |
|---|---|---|
| 查看目标捕获 | 角色面板 `CharacterDisplay+0x120` 的 hero | 点肖像→原版面板打开即游戏自己的查看入口；OBS 24（技能格渲染，wrapper→action+8→panel）与 OBS 26/27（面板关闭，r[0]=panel）两处现成门控只读捕获，不注入任何输入 |
| 查看目标锁定 | `g_inspect_actor` + `g_inspect_vt` | 锁定时记录 vtable，此后每帧要求 vtable 不变才继续（防页复用野调用）；失效条件：vtable/名字校验失败、失去 raid 对象（离开地牢/战斗） |
| Affliction | 属性包 `affliction_type_id`（字符串） | RomFS trait_library 白名单（7 固着 + 5 美德）；游戏查表 `str_affliction_name_%s` / `str_virtue_name_%s`（键形状为 main 镜像内原文）；属性包节点地址按英雄缓存、每帧廉价复验，状态变化实时可见 |
| 护体格挡 | `Actor+0x128c`（剩余次数）≥1 时逐字复刻 tray case 0x16（main+0xcd4cbc） | 查表 `tray_icon_tooltip_health_damage_blocks_duration_format` + 游戏格式化器 `0x993000`（w3=`+0x11a4`、w4=次数），中文模板「剩余%d次护体隔挡」在 schinese 文本池；`rules.json: health_damage_blocks_max=2` 佐证该字段为 Actor 内部状态而非 Buff |

`dd_loc_fn` 返回类型改为 16 字节结构（x0 文本指针 + x1 打包长度字，AAPCS 对应），供格式化描述符使用；颜色协议剥离提取为公共 `hero_strip()`。

### 运行时验证（成品 App `out/macOS/Dungeon1-r4.app`，隔离存档，DM_CTL 注入）

- **点击查看**：点肖像→原版角色面板→关闭，日志 `inspection target pinned (actor 0x7008d4d010)`；截图 `out/hero-verify/w_t1.png`（麦克道尔 小丑，含粉色「暴虐」行与「終曲：+30%伤害(5回合)」）。
- **不跟随**：回合推进后行动英雄切到修女（gate actor 翻转为 0x7008d37010），面板仍显示麦克道尔且终曲实时更新为 +60%(7回合)（`w_t2.png`）。
- **再选择**：R 切换 + 肖像→关闭，日志 `pinned (actor 0x7008d40010, player re-selected)`，面板切到哥伦布尔斯 修女（`w_t3.png`）；随后切到戈顿 破盾者（`w_b6.png`）。
- **实时性**：下一场战斗中锁定戈顿，生命 9→12、速度 Buff 回合数等逐帧更新（`w_wa.png`）。
- **护体格挡**：扎透（增益自身 2 次护体格挡）击杀最后敌人后战斗结束；战斗外面板不再显示格挡行——与游戏在战斗结束时清除该状态一致。**战斗中获得后、战斗结束前的面板显示尚未实测**（显示链路与已验证的查表+格式化路径相同）。
- **敌人查看（下一轮输入）**：确认游戏原生存在**敌人信息面板**（目标选择时点击敌人打开，显示名称/生命/抗性/技能，实测截图 `w_s7.png`骸骨誓僧）——功能二可直接复用该面板持有的 Actor，需一轮新增 OBS 门控（patches.py + 重写 prepared）。

### 回归

host C 测试 0 失败；脚本测试 7 个文件全过；iOS compile_check 137+6 全过；`check_public` issues 空。
双端成品重建：`out/macOS/Dungeon1-r4.app`（1m04s）、`out/iOS/Dungeon1-r4.ipa`（1.6G）。
未 commit/push（按要求等待确认）。

## 2026-11-06（二）：验收问题修复（第十四轮）

人工验收反馈三项：点击角色不切换、部分角色无职业、护体格挡不显示。逐项根因与修复：

### 1. 点击角色不切换 → 点击门控的选中跟随
点不同英雄的肖像时，游戏只切换"展开卡片"（选中英雄槽 G+0x3e8），并不一定打开
CharacterDisplay，旧捕获（面板开/关两处门控）不触发。修复：新增**点击门控的选中跟随**
（hle_dd_hero.c `hero_tap_track`）——触摸抬起后 0.8 s 窗口内，游戏选中槽发生变化即锁定
为新查看目标；回合自动切换没有伴随点击，不会误跟随。追踪每帧执行（快速点击可能起止于
两次采样之间），基线取抬起前最后一次读到的选中值；模块基址在首次采样扫描后缓存。

### 2. 部分角色无职业 → 扫描边界加固
职业扫描边界（"下一个同 vtable Actor"）被野 vtable 指针提前截断，且回退窗口 0x6000
小于属性包实际漂移（实测至 ~+0x7600）。修复：边界候选须同时通过 Buff 向量形状校验
（begin/end 对齐、步长、上限），回退窗口扩至 0x9000；hero_identity 与固着扫描共用。
实测：存活英雄职业均显示（麦克道尔 小丑、哥伦布尔斯 修女、戈顿 破盾者）；**濒死
（生命 0）英雄的职业/固着不显示——游戏已释放其属性包，如实留空**。

### 3. 护体格挡不显示 → 分支语义修正（运行时实测证据）
字段证物（r5 会话，字段变化逐条日志）：扎透（增益自身 2 次护体格挡）命中后
**Actor+0x11a4: 0→2，Actor+0x128c 保持 0** ——剩余次数在 +0x11a4，旧实现错误地以
+0x128c ≥ 1 为显示前提，把常态路径整个挡掉了。修正为逐字复刻 tray case 0x16 的两个分支：
- +0x128c ≥ 1：查表 `…health_damage_blocks_duration_format`，格式化 (w3=+0x11a4, w4=次数)
  →「剩余%d次护体隔挡」；
- 否则若 +0x11a4 ≥ 1：查表 `…health_damage_blocks_format`，格式化 (w3=+0x11a4)
  →「%d次护体隔挡」。
两键均为游戏自用键（main 镜像原文），格式化器为游戏自己的 0x993000。
另加字段变化日志（cnt/arg 逐次变化一行，含 actor 地址）作为长期证物。

### 4. 交付物路径（重要）
此前验收所用 `out/macOS/Dungeon1.app` 是修复前的旧版。本轮已将最终版（r7）复制到
标准路径 `out/macOS/Dungeon1.app` 并重签名；iOS 产物 `out/iOS/Dungeon1-r7.ipa` 同步
重建。**请用标准路径的 App 重新验收。**

### 5. 回归
host C 测试 0 失败；脚本测试全过；iOS compile_check 137+6 全过（r7 重建时再次执行）。

## 2026-11-06（三）：二次验收问题修复（第十五轮）

用户复测反馈：点人物模型只能双击开详情页才跟随；新加的角色不显示职业；面板遮挡
最左边的人物（四人编队）。

### 1. 点模型：单击=游戏无反应，双击=原版详情页（原版交互，面板已跟随）
单击模型游戏本身不改变选中槽（无从跟随、也不注入输入）；双击打开的原版详情页会
触发捕获，面板随之切换。这是游戏原版交互，非缺陷。肖像点击/R 切换+点肖像的路径
不变。

### 2. 新角色无职业 → 属性包扫描重做（关键根因）
用 DM_CTL memdump 对运行中的英雄 Actor 做了 0x40000/0xC000 多点采样，发现：
- 属性包节点与 Actor 的距离是**会话相关**的：一次会话内 +0x391d..+0x14829，另一次
  会话在同场景下完全不在 ±0x40000 内（英雄 Actor 与包分属相距约 1.3GB 的两个
  vm 区域）——固定窗口的旧扫描因此时灵时不灵（「有的角色没职业」的直接根因）；
- 各英雄的包**彼此交错**在同一分配区（小丑的 heroClass 出现在修女 Actor 前方
  0x94da 处）——无锚定的宽域扫描会错标他人职业；
- 包内存在英雄自己的名字字符串（值），与 heroClass 节点相距 0x1a1..0x1346。

修复（hle_dd_hero.c hero_bag_anchored + hero_bag_wide_scan）：有界扫描失败后进入
宽域扫描，窗口逐次增长（0x20000→0x80000→0x200000，每 2 秒至多一趟）；**只有当
本英雄的名字字符串（作为包值，Actor+0x8 本体字段除外）出现在节点前 0x2000 字节内，
节点才被接受**——名字把节点绑定到英雄，杜绝错标；职业 id 仍过白名单。固着节点的
发现同样改走该锚定扫描。实测：新会话装载后职业立即显示（戈顿 破盾者、麦克道尔
小丑、哥伦布尔斯 修女）。

### 3. 面板遮挡最左侧英雄 → 移至左上角窄列
四人编队时最左英雄位于画面 x≈0.14 起。面板改为：宽 0.128×画面宽（clamp 132–176px）、
贴画面顶边（Mac 修 y 坐标系后实测落位），占左侧窄列，不与任何英雄重叠；任务横幅
与面板有少量重叠（静态信息，可接受）。Mac/iOS 同步。

### 4. 回归与产物
host C 测试 0 失败；脚本测试全过；iOS compile_check 137+6 全过。
标准路径 `out/macOS/Dungeon1.app` 与 `out/iOS/Dungeon1.ipa` 均已更新为本版。
注意：此前 r9 验证会话误用 r7 旧版 App（run 脚本 App 路径未随版本更新），已修正
脚本并以标准路径 App 复测通过。

## 2026-11-06（四）：卡顿修复与站位点击撤销（第十六轮）

用户反馈：双击人物游戏会卡住；希望单击/长按模型直接在面板展示（不开详情页）；
并指出队伍可能只有 3 人（上限 4），不建议用固定站位点击。

### 1. 双击卡住 → 扫描改分帧预算（根因）
上一轮的宽域锚定扫描在「打开详情页的那一帧」同步跑完整趟（最多 0x200000 字节、
上千个窗口的逐窗读取 + 锚定校验），游戏线程整帧被占——表现为双击即卡。修复：
hero_bag_scan_tick 每个采样至多扫 24 个窗口（≈55KB，亚毫秒级），一趟分摊到几十帧；
窗口仍逐趟增长（0x20000→0x80000→0x200000），两趟之间按 15 秒重扫（游戏可能延迟
构建属性包，例如打开该英雄详情页时）。实测：连续三击无任何新增停顿记录
（display link stalled 计数不变），职业/固照常找到（+0x2835 / +0x2954）。

### 2. 单击/长按直接查看 → 按用户意见不做固定站位点击
游戏对模型的单击/长按没有任何原生态反应，"点哪查哪"需要把点击位置映射到英雄
（站位→英雄）。用户明确指出队伍可能只有 3 人且不建议固定站位方案，该映射已撤销
（连带撤销 raid 对象队伍数组探测）。保留的查看路径：双击模型/点卡片肖像/R 切换后
点肖像——面板均跟随（原版交互，零注入）。

### 3. 回归与产物
host C 测试 0 失败；脚本测试全过；iOS compile_check 137+6 全过。
标准路径 `out/macOS/Dungeon1.app` 与 `out/iOS/Dungeon1.ipa` 均为本版。

## 2026-11-06（五）：性能修正与面板精简（第十七轮）

用户反馈：一进游戏就持续卡顿；要求去掉职业与名字显示、不要影响性能、面板放在
角色上方。

### 1. 持续卡顿的真根因（上轮引入的锚定循环写法错误）
宽域扫描的窗口内循环对**每个字节偏移**都调用锚定校验 hero_bag_anchored——每窗口
约 2266 次 × 每次 2 个 mincore 系统调用 + 8KB 内存比较 ≈ 每窗口 10-20ms；扫描存活
期间每个采样帧都要跑 24 个窗口，即每帧 0.3-0.5 秒的开销——游戏全程卡顿。修复：
先做窗口内的键字节匹配（memcmp，微秒级），只对真正命中 affliction_type_id 的候选
才做锚定校验——每趟开销从数百毫秒降到微秒级。

### 2. 面板精简（按用户要求）
- 去掉名字行与职业行（连同 heroClass 扫描和每帧的 hero_class_name 查表调用）；
- 内容仅剩：生命/压力行、固着/美德行（游戏查表中文名）、护体格挡行（游戏自己的
  Tooltip 文案）、Buff 行（上限 4 行）；
- 属性包扫描只服务固着节点，且**只在压力 ≥ 60 时运行**（低于该值不可能有固着/
  美德状态）——低压力队伍零扫描开销；窗口趟数上限改为 0x80000。

### 3. 面板位置：悬在英雄队列正上方
面板改为顶部横条（x 0.05-0.45、高 0.145×画面高），底边正好在英雄模型头顶
（y≈0.13）之上——四位英雄全部完整可见。Mac/iOS 同步。

### 4. 回归与产物
host C 测试 0 失败；脚本测试全过；iOS compile_check 137+6 全过。
`out/macOS/Dungeon1.app` 与 `out/iOS/Dungeon1.ipa` 均为本版。
实测：战斗中面板悬于队列上方，固着/终曲行正常，display link 零新增停顿。

## 2026-11-06（六）：点击角色 → 头顶悬浮面板（第十八轮）

本轮把面板从「固定贴在画面左侧的窄条」改为「点谁就悬在谁头顶」，并建立独立的
「查看目标」。数据源全部来自游戏自身，未新增任何输入注入。

### 1. 点击事件的实际来源（结论：原版没有「点击英雄模型」这件事）

- 实测（第十五轮已确认、本轮复核）：单击模型游戏无任何反应；双击打开原版
  CharacterDisplay 详情页；点技能后点模型是「释放技能」。也就是说**不存在可复用的
  「英雄被点击」事件**，只有「双击打开详情页」这一条游戏自己的查看路径。
- 因此点击对象由本适配层判定：触点来自宿主的触点流（与游戏自己收到的是同一根手指，
  `dm_touch_contact_snapshot`，坐标已是游戏面板空间 1280×720 的整数），命中判定用
  **游戏自己每帧给出的单位位置**（下面第 2 条）——不是固定屏幕坐标，也不是当前
  行动英雄、当前技能目标或鼠标悬停对象。
- 只有「短按（<0.5 s）+ 位移 ≤10 px」算作点选；被宿主取消的触点（拖动、第二根手指、
  被手柄接管）永远到不了 RELEASED，因此拖动不会误选。点空处不改变已选目标。
- 双击模型打开详情页时，仍由既有 OBS 24/26/27 捕获该面板持有的 hero 并锁定——那是
  游戏自己的查看入口，与点选结论不会冲突。

### 2. 英雄屏幕位置（本轮核心技术点）

新增只读观测点 **OBS 36 @ main+0xccf0a0**（单位精灵的动画绘制入口，每单位每帧一次）：
`x0 = Actor+0x94`，`s0/s1` = 该单位在场景空间的位置，`w3 = 7`。同一次调用还会用同一组
坐标摆放该单位的血条与 Buff 图标，所以这就是游戏自己认定的「单位在哪」。

排查记录（避免后续重复调查）：

| 试过的来源 | 结果 |
|---|---|
| Actor 内部字段（0x40-0x1400 全量 dump） | 只有世界坐标（+0x60/+0x64），没有屏幕坐标 |
| 单位 HUD 布局对象（OBS 37 试做，tray+0x10 → +0x100..0x140） | 是**常量样式表**（20/24/50/-10/58/100…），全部单位共用，不含位置；且 tray 基址是按队列序号固定的 HUD 列（417.6/573.0/728.4 三次会话不变），**不是**单位屏幕位置。该观测点已撤销 |
| 场景对象（OBS 38 试做，0xd5f790 的 x0） | +0x1400 区几乎全 0，相机变换不在此结构里（渲染器用矩阵完成），已撤销 |
| 世界坐标 → 屏幕的换算 | 单位世界坐标处于 2048 宽的**场景空间**：`画面比例_x = world_x / 2048`。三个英雄实测 446.7/614.2/776.5 → 画面 0.218/0.300/0.379，与截图量出的 0.222/0.305/0.385 一致（误差 <1%），故取此换算 |

由此：`anchor_x = world_x / 2048`，`feet_y = 0.600 - world_y / 2048`（行高），
`head_y = feet_y - 0.245`（一个精灵的高度）。三个分数是**视图几何**（脚线与精灵高度），
可用 `DM_DD_HERO_FLOOR_Y / _SPRITE_H / _BODY_HALF / _PANEL_GAP` 在运行时用 DM_CTL
`env` 调，无需重新编译。位置本身（x、y）每帧来自游戏，因此走路、攻击前冲、镜头移动
都会跟随，不存在「点一次定死」的问题。

### 3. 悬浮面板

- Mac：`DmHeroPanelView` 单实例，30 Hz 定时器读快照 → 逐行 CoreText 量宽 → 自适应
  尺寸 → 按 anchor 定位（居中于单位、底边在头顶上方 4 px；顶部放不下时自动移到下方；
  始终 clamp 在画面内）。命中测试返回 nil，点击照常落到游戏视图。半透明深色底、
  7 px 圆角、0.5 px 描边，样式沿用原面板。
- iOS：`DmHeroPanel` + UILabel，同一套 anchor/尺寸/边界逻辑。
- 内容不变（未触碰 Buff 解析/数值/职业名）：生命/压力行、固着/美德行（游戏查表名）、
  护体格挡行（游戏自己的 tooltip 文案）、Buff 行（上限 6 行，超出显示 +N）。
- 修掉一个既有缺陷：生命/压力行此前只在「有 Buff 实例」时才出现（`has_battle` 是在
  Buff 聚合函数里顺带写的）。现在 `has_battle` 由 Actor 的 vtable +0x20（游戏自己的
  「这个单位在战斗中吗」）在每个采样里直接问，无 Buff 的单位也有血量/压力行。

### 4. 查看目标保持

`g_inspect_actor` + `g_inspect_vt`：只由玩家点选（或原版详情页）改变，回合自动切换
不参与；失效条件为 vtable 变化（对象被释放/复用）、raid 对象消失（离开地牢/战斗结束）、
或连续 20 次采样（≈1 秒）该单位不再被绘制（模型离开场景）。指针一律走 `hero_rd`
（mincore 校验）后才解引用，失效 Actor 不会被野读。

### 5. 敌人接口（第二阶段预留）

`DdInspectTargetType { NONE, HERO, ENEMY }` 已加入 `dd_hero.h`，快照新增
`target_type / target_actor / anchor_valid / anchor_x,anchor_y / body_x0..y1`，
位置与面板渲染都是类型无关的。敌人只需在点选时把类型设为 ENEMY 并接上敌人 Actor 的
来源（本轮未做：敌人点击目前被 vtable 过滤排除）。

### 6. 实测（成品 `out/macOS/Dungeon1-r33.app`，隔离存档，DM_CTL 注入触摸）

- 点最左英雄 → 面板出现在其头顶：`生命 18 压力 73/200` + `+5%侦察概率在荒野(效果持续到任务结束)`
  （`out/hero-verify/float_h1.png`）。
- 点中间英雄 → 面板随点击切换（日志 `player re-selected`，`float_h2.png`）。
- 点最右英雄 → 面板切到该英雄：`生命 12 压力 145/200`、`暴虐`、`终曲：+210%伤害(7回合)`、
  `1伤害下次行动(2回合)`、`+10%所受压力伤害(2回合)`，行全部完整显示（`float_h3.png`）。
- 回合推进（自动切换行动英雄）时面板不移动：锚点只随目标单位的绘制位置变化。
- 日志证据：`inspection target pinned (actor 0x…, player re-selected)` 每次点击一行；
  三次点击得到三个不同 Actor。
- **注意**：截图必须用系统截屏（`screencapture`）。游戏的 `shot`/DM_CTL 截图取的是
  Metal drawable，**不包含 AppKit 覆盖层**，面板不会出现在那种截图里（本轮曾因此误判
  「面板没画出来」）。

### 7. 回归与产物

host C 测试 0 失败；8 个脚本测试全过；iOS compile_check 137+6 全过。
`out/macOS/Dungeon1-r33.app`、`out/iOS/Dungeon1-r33.ipa` 为本轮产物（IPhone 端仅静态
检查 + 构建，未做真机运行）。本轮按要求**未 commit、未 push**。

### 8. 已知限制（下一轮输入）

- 面板水平居中用的是单位在场景里的列位置（精灵原点），视觉上比角色躯干中心略偏左
  约 2-3% 画面宽；若要求严格居中可用 `DM_DD_HERO_BODY_HALF/DX` 微调。
- 精灵高度取统一的 0.245（DD 战斗中各职业精灵高度接近，未按职业分别测量）。
- 敌人点选与敌人面板未实现（架构已预留）。
