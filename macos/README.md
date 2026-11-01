# 本机 macOS 修复分支

此分支基于 [morningmeal/morningmeal_ComPet](https://github.com/morningmeal/morningmeal_ComPet)，维护本机 Compet-V3 的 macOS 兼容修复。上游源码和 Git 历史保留在仓库中；本机补丁从正在使用的应用包直接提取。

## 代码和已安装应用的对应关系

- `morningmeal_Compet_V3/core/macos_compat.py`：与当前 `/Applications/Compet-V3.app/Contents/Resources/compet_macos_compat.py` **逐字节一致**的兼容层。暂时保留累积补丁结构，方便核对已验证行为。
- `morningmeal_Compet_V3/main.py`：在 Cocoa GUI 启动路径中、绑定输入引擎及窗口类之前加载兼容层；Windows 和已有的 offscreen/minimal 启动路径不加载它。
- `.github/workflows/release.yml`：macOS ZIP 使用 `zip -ry`，保留 framework 和 PyInstaller 包中的符号链接，并执行完整签名验证。
- `macos/installed-baseline.json`：源码基线、已安装 hook 和原 main 字节码的 SHA-256。它是核对记录，不含配置、皮肤、计时数据、权限数据库或凭据。
- `macos/check_installed.py`：只读核对当前安装的补丁和签名。
- `macos/REPAIR-NOTES.md`：历史应用包修复、权限和回归验证说明。

当前应用是此前原位修复的发布包，**不是从本分支重新构建的产物**。上游 main 已包含较新的功能；此分支源码入口和打包设置尚未做完整依赖安装与重建验收。不要把当前应用的手工验证结果当作新构建的验收结果。

## 已保存的修复

1. 在主线程读取键盘布局，避免 macOS 15 在后台输入线程中触发 Carbon 断言。
2. 主线程预加载输入监听相关的 Quartz / HIServices 接口。
3. 用 macOS 原生 **listen-only** 事件通道驱动桌宠互动，必须由用户授予“输入监控”；不屏蔽、修改或记录按键和鼠标内容。
4. 桌宠和计时器采用非激活浮动面板，辅助应用模式、跨 Space 属性以及空间切换通知配合使用，支持跟随其他应用的全屏空间。
5. 每帧清空桌宠透明画布，禁用 Cocoa 缓存阴影，避免残影。

辅助应用模式下 Dock 图标隐藏，设置仍通过菜单栏进入。

## 本地维护

在仓库根目录运行：

```sh
python3 macos/check_installed.py
```

修改兼容层时先提交到本分支，在输出副本中完成构建/验收，再替换正式应用。不要仅为了同步源码而反复修改或签名当前应用。

按上游依赖和流程构建源码时使用 Python 3.11；本机包的已知运行环境为 Apple Silicon、macOS 15.5、Python 3.11.9、Qt 6.11.2。当前依赖范围没有锁定，依赖升级需要重新验收。

任何应用包内容变化都需要重新签名；本机使用临时签名，macOS 授权绑定代码哈希。更新后即使权限列表的开关显示开启，旧记录也可能失效。请在“隐私与安全性 → 输入监控”中移除旧 Compet-V3，重新添加 `/Applications/Compet-V3.app` 并授权；辅助功能授权如失效也按同样方式刷新。不得直接编辑 TCC 数据库或改用具有更大能力的输入模式绕过授权。

## Git

- `upstream` 指向原项目。
- 修复分支：`codex/macos-local-fixes`。
- 如完成 GitHub fork，`origin` 指向个人 fork；本地提交不会自动推送。
- 不提交 `.app`、ZIP、用户配置、皮肤、计时数据、日志、虚拟环境或密钥。
