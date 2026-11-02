# 本机 macOS 修复分支

此分支基于 [morningmeal/morningmeal_ComPet](https://github.com/morningmeal/morningmeal_ComPet)，维护本机 Compet-V3 的 macOS 兼容修复。上游源码和 Git 历史保留在仓库中；本机补丁从正在使用的应用包直接提取。

## 代码和已安装应用的对应关系

- `morningmeal_Compet_V3/core/macos_compat.py`：与当前 `/Applications/Compet-V3.app/Contents/Resources/compet_macos_compat.py` **逐字节一致**的兼容层。暂时保留累积补丁结构，方便核对已验证行为。
- `morningmeal_Compet_V3/core/interaction_fixes.py` 和 `core/docking.py`：整卡拖动、双向吸附、邻近计时器边缘吸附和补充翻译；原位更新时分别放在应用 Resources 的 `compet_interaction_fixes.py` / `compet_docking.py`。
- `morningmeal_Compet_V3/main.py`：在 Cocoa GUI 启动路径中、绑定输入引擎及窗口类之前加载兼容层；Windows 和已有的 offscreen/minimal 启动路径不加载它。
- `.github/workflows/release.yml`：macOS ZIP 使用 `zip -ry`，保留 framework 和 PyInstaller 包中的符号链接，并执行完整签名验证。
- `macos/installed-baseline.json`：源码基线、已安装 hook 和原 main 字节码的 SHA-256。它是核对记录，不含配置、皮肤、计时数据、权限数据库或凭据。
- `macos/check_installed.py`：只读核对当前安装的补丁和签名。
- `macos/REPAIR-NOTES.md`：历史应用包修复、权限和回归验证说明。

当前 `/Applications/Compet-V3.app` 已改为完整源码构建，含远端 `72151a3` 的新增功能，沿用固定本地签名。`Contents/Resources/compet-build.json` 记录完整 Python 源文件哈希及构建基线；`check_installed.py` 同时支持此格式和历史原位补丁格式。上面的 sidecar 与原 main 字节码说明仅适用于历史修复包，新构建直接使用打包后的 core 模块。

## 已保存的修复

1. 在主线程读取键盘布局，避免 macOS 15 在后台输入线程中触发 Carbon 断言。
2. 主线程预加载输入监听相关的 Quartz / HIServices 接口。
3. 用 macOS 原生 **listen-only** 事件通道驱动桌宠互动，必须由用户授予“输入监控”；不屏蔽、修改或记录按键和鼠标内容。
4. 桌宠和计时器采用非激活浮动面板，辅助应用模式、跨 Space 属性以及空间切换通知配合使用，支持跟随其他应用的全屏空间。
5. 每帧清空桌宠透明画布，禁用 Cocoa 缓存阴影，避免残影。
6. 计时器标题、时间和背景均可拖动；拖动计时器到桌宠底部或把桌宠放到计时器上方都可吸附。绑定后拖动任一窗口可联动；右键桌宠解除绑定。关闭磁吸开关后不再自动绑定。检测使用桌宠底部锚点，支持大尺寸皮肤。
7. 修复初始设置子标签、确认/取消按钮、主题按钮及删除分组提示的漏译，并保留语言切换。
8. 不再自动创建默认计时器分组；分组列表按已保存内容完整读取。旧版空白且未被使用的默认分组会清理，已有自定义、已填写或仍被引用的分组保留。

辅助应用模式下 Dock 图标隐藏，设置仍通过菜单栏进入。

## 当前/最近计时器模式

- 每 200ms 独立检查前台应用；闲置只影响累计，不阻止识别和卡片切换。
- macOS 前台应用使用 NSWorkspace 识别。窗口标题可通过限时 Accessibility 查询补充；标题权限不足时仍能按应用名识别，不使用易失败的 AppleScript 窗口 id，也不申请屏幕录制。
- QQ / 微信按应用身份及别名识别，也支持窗口标题关键词；远端新增的重叠监听允许多个分组同时累计，显示顺序由计时器列表决定。
- 所有匹配的普通计时器各自按暂停和闲置规则累计；按设置列表顺序显示第一个匹配的计时器。前台不匹配、识别失败、手动暂停、无输入监控授权或超过闲置阈值时均不累计，并在卡片显示原因。
- 桌面仅显示当前匹配的卡片；没有匹配时保留最近一次。完整列表仍在设置中管理。最近卡片会保存，重启后继续使用。
- 单个已绑定桌宠升级为“跟随当前计时器（全部）”，保留全部计时器关联，切换时在同一个宠物底部锚点替换卡片。可在桌宠设置下拉框选择全部/单个，或右键桌宠选择多个；“解除全部关联”恢复自由模式。多桌宠配置保留原有各自的绑定。
- 计时不再另开 pynput 活动监听；使用系统空闲秒数判断闲置，以单调时钟累计实际有效间隔。睡眠/长时间阻塞的间隔不补算。
- 用户已有累计时间、计时器 ID、分组与闲置阈值均保留；历史误计没有足够事件历史可自动重新归类，因此不重算。

实现位于 `core/timer_policy.py`、`core/timer_fixes.py` 和 `core/macos_foreground.py`。已安装旧包分别通过对应 `compet_*.py` sidecar 加载；源码启动也安装同一控制器。原 `ActivityEngine.start` 由新 Qt 主线程轮询替代，因此不要仅通过旧 `_engine_loop` 推断当前运行逻辑。

## 本地维护

在仓库根目录运行：

```sh
python3 macos/check_installed.py
python3 -m unittest discover -s macos/tests -p 'test_*.py' -v
```

修改兼容层时先提交到本分支，在输出副本中完成构建/验收，再替换正式应用。不要仅为了同步源码而反复修改或签名当前应用。

按上游依赖和流程构建源码时使用 Python 3.11；本机包的已知运行环境为 Apple Silicon、macOS 15.5、Python 3.11.9、Qt 6.11.2。当前依赖范围没有锁定，依赖升级需要重新验收。

应用现在启动时主动调用 CGRequestListenEventAccess；每次启动最多请求一次，最终批准仍由用户完成。设置中会显示键鼠互动权限状态，并提供申请/打开系统设置按钮。授权被拒绝或系统保留旧记录时不会反复弹窗；用户仍可从该入口处理。

本机已从临时签名切换到专用 `ComPet Local Development` 证书，身份要求同时固定应用标识和证书指纹。私钥只保存在登录钥匙串，证书仅设置用户域 codeSign 信任，不添加网站/SSL 信任。公开指纹保存在 installed-baseline.json；本机身份凭据单保存在 `~/.config/compet-signing/identity.json`，不在 Git 中。

签名校验需要在可访问登录钥匙串的正常用户环境中运行；隔离沙箱可能无法读取该用户的代码签名信任，出现 CSSMERR_TP_NOT_TRUSTED 时应先区分运行环境，不应因此放宽签名要求。

后续准备好输出副本后，使用同一身份重签：

```sh
python3 macos/sign_app.py --app /path/to/prepared/Compet-V3.app
```

不要再用 `codesign --sign -` 覆盖本机正式安装。GitHub Actions 的公开产物仍为临时签名，安装到本机前也需使用上面的本地证书重签；不要把私钥上传到仓库或 CI。已在两个资源内容不同的副本中验证指定身份完全相同且签名通过。

首次从旧临时签名迁移到该证书可能仍需用户再授权一次；以后继续使用同一证书可避免每次内容变化都改变指定身份。系统仍可独立撤销权限，不能承诺永久保留授权。如旧记录失效，可从应用按钮打开系统设置，必要时移除旧条目重新添加。不得直接编辑 TCC 数据库或改用更大能力的输入模式绕过授权。

仅在另一台本机明确批准创建身份时运行 `python3 macos/create_signing_identity.py --approve-keychain-changes`。不得重建或覆盖现有身份；丢失私钥/换证书会再次改变身份。

## Git

- `upstream` 指向原项目。
- 修复分支：`codex/macos-local-fixes`。
- `origin` 已关联个人 fork：`git@github.com:GJCPP/morningmeal_ComPet.git`；本地提交不会自动推送。
- 不提交 `.app`、ZIP、用户配置、皮肤、计时数据、日志、虚拟环境或密钥。

## 完整源码构建与登录启动

本机环境为 Apple Silicon、Python 3.11.18、Qt 6.12.0；已验证依赖记录在 `macos/requirements-local.lock`。构建环境 `.venv` 不进入 Git。重新配置时可用 `uv venv --python 3.11 .venv`，再用 `uv pip sync --python .venv/bin/python macos/requirements-local.lock` 安装锁定版本。

日常更新先从 origin 拉取，完全退出运行中的应用保存计时，再运行：

```sh
.venv/bin/python macos/build.py
```

脚本完整打包源码、沿用现有证书签名、执行隔离 offscreen/Cocoa 启动测试，然后安装到唯一正式路径 `/Applications/Compet-V3.app`。已运行的应用会阻止安装，不能强杀用户进程；退出后可运行 `.venv/bin/python macos/install.py` 发布已经验证的输出。`--build-only` 只准备测试构建，不改变正式版本。构建输出固定在 `macos/artifacts/dist/Compet-V3.app`，安装不会创建版本后缀目录或 ZIP。新构建仍需实际检查全屏和交互；测试副本不会申请输入权限，也不会读取或写入真实计时数据。

登录启动通过 `.venv/bin/python macos/enable_startup.py` 配置当前用户的 `~/Library/LaunchAgents/com.gjcpp.compet.login.plist`。它在 Aqua 登录时执行 `/usr/bin/open -g /Applications/Compet-V3.app`，不使用 `-n`，避免重复实例。任务仅负责打开应用，无 KeepAlive；主动退出后不会被不断重新打开。以后每次成功构建并安装，固定路径内容更新，启动项便会打开更新后的版本，不需重新添加。开机时不会自动拉取 Git 或编译；只运行最新成功安装的构建。

停用：`launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.gjcpp.compet.login.plist`，再移除该 plist。权限由 macOS 管理；若系统撤销输入监控，可从应用设置中的权限入口重新授权，不修改 TCC 或重建签名身份。

2026-11-02 验证：31 项 macOS 回归与 22 项更新功能测试通过；完整打包的 offscreen/Cocoa 启动通过，Finder 全屏中桌宠和计时器均处于活动空间；固定签名和源码清单校验通过。LaunchAgent 已实际加载并以退出码 0 打开正式安装版本。尚未执行真实重启测试。

## macOS 浮窗焦点与退出保护

桌宠和计时卡在创建原生窗口之前设置 `WindowDoesNotAcceptFocus`、`WA_ShowWithoutActivating` 和 `NoFocus`，保留鼠标点击/拖动能力。计时卡不再强制请求成为键盘窗口。主动打开设置或快捷设置对话框时仍可正常编辑文本。

`core/macos_focus.py` 在 QApplication 创建后安装保护：Qt 标准 Quit 快捷键事件会被消费；AppKit 本应用的 local event monitor 消费精确的 ⌘Q；原生菜单保留退出动作但去掉对应快捷键。没有新增全局拦截器，也不记录按键。其他应用的 ⌘Q、⌘⇧Q、系统注销/关机请求和应用明确调用 quit 均不被这层保护拦截。用户仍可从菜单栏、桌宠右键或设置中的退出按钮退出。

验证包含原生本地事件分支、Qt 快捷键分支、菜单退出动作保留、明确退出成功及原生窗口 `canBecomeKeyWindow == false`。不能用拦截所有 Quit 事件或覆盖所有 applicationShouldTerminate 请求替代快捷键保护，否则可能阻止系统正常注销/关机。

退出保护在 aboutToQuit 阶段先移除 Qt 事件过滤器，再停止菜单检查和移除 AppKit 本地监视器，避免 SIP/Qt 收尾期间调用残留过滤器。2026-11-02：54 项回归通过，Cocoa 拖动/吸附回归通过；用户确认拖动、右键和设置内 ⌘Q 保护均正常。收尾修正连续三次原生打包启动/退出通过，正式应用已安装重启。

## 数字输入与默认皮肤

设置中的“大小”和“闲置”统一使用 `ui/numeric_editor.py` 的 `SettingsSpinBox`：保留步进按钮、消除嵌套编辑框内边距，并在完整输入后（Enter/失焦）提交数字，避免输入中途被范围校正或保存刷新打断。宠物卡片按 ID 复用，宠物设置变化不再重建当前卡片；外部刷新也保留正在编辑的数值。已检查所有数字控件（当前共两处）及设置变化信号链。

用户明确要求将当前“羿”作为默认皮肤，因此本次将该皮肤的三张贴图和配置纳入内置资源，移除旧 `assets/skins/default`。新实例默认选择“羿”；已有“羿”皮肤不覆盖。旧默认皮肤仅在三张原始图片哈希全部一致、没有额外文件或自定义键位映射时移至用户数据目录的 `retired-skins/default-*`（保留恢复副本，不在皮肤列表显示）。仍引用旧默认的实例迁移为“羿”，保留 ID、大小、位置、关联及计时记录。修改过的其他皮肤保留。

源码构建清单 format 2 额外记录并校验完整内置 assets 哈希，安装时也检查不存在多余的旧资源。59 项回归通过；数字控件在 Cocoa 和 offscreen、明暗主题、中文/英文、1/1.5/2 缩放下通过键盘输入、可见字形、保存重开及焦点检查。

## 应用与窗口切换

桌宠和桌面计时器作为非激活浮动面板，不参与窗口轮换；应用使用辅助模式，从 Dock 和 Command-Tab 隐藏。本地构建和发布包均设置 `LSUIElement`，设置继续从菜单栏或桌宠右键菜单打开。原生构建检查验证辅助模式和窗口轮换属性；Command-Tab、全屏 Space 与菜单交互仍需在 macOS 桌面实测。
