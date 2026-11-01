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

当前应用是原位更新兼容层和交互补丁的发布包，**不是从本分支重新构建的产物**。上游 main 已包含较新的功能；此分支源码入口和打包设置尚未做完整依赖安装与重建验收。不要把当前应用的手工验证结果当作新构建的验收结果。

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
- QQ / 微信按应用身份及别名识别；应用名的匹配优先于聊天窗口标题中的关键词，避免 QQ 窗口标题出现 ChatGPT 时误归到工作。
- 同一时刻只选择并累计一个计时器。前台不匹配、识别失败、手动暂停、无输入监控授权或超过闲置阈值时均不累计，并在卡片显示原因。
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
