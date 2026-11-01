# 发布包修复记录

## 包结构及启动入口

首次检查的应用包为 arm64，与本机架构匹配。崩溃发生在 Qt 初始化，`codesign --verify --deep --strict` 同时报 Python.framework 结构不明确。原包中的符号链接被展开成内容相同的文件或目录。

当时在副本中恢复了 84 个符号链接：

- 54 个来自 `Contents/_CodeSignature/CodeResources` 中 `files2` 的 `symlink` 记录。
- Python.framework 和 9 个 Qt framework 各恢复 `Versions/Current`、根目录二进制和 `Resources` 三个标准链接。

每个被替换的副本都先与目标逐字节核对。恢复后原签名完整验证通过，无需重签。这也是本分支将 macOS 打包命令改为 `zip -ry` 的原因。

为避免依赖本机 Python 版本或整包重建，已安装应用的 PyInstaller CArchive 中 `main` 项被替换为一个短 bootstrap。它使用应用自身的 Python 3.11 执行，先加载兼容层，再执行保存的原始 main：

```python
import os as _compet_os, sys as _compet_sys, marshal as _compet_marshal
_compet_resources = _compet_os.path.join(_compet_os.path.dirname(_compet_sys.executable), '..', 'Resources')
with open(_compet_os.path.join(_compet_resources, 'compet_macos_compat.py'), encoding='utf-8') as _compet_file:
    exec(compile(_compet_file.read(), 'compet_macos_compat.py', 'exec'), globals())
with open(_compet_os.path.join(_compet_resources, 'compet_original_main.marshal'), 'rb') as _compet_file:
    exec(_compet_marshal.load(_compet_file), globals())
```

旧 main 的 marshal 数据保留在应用 Resources，仓库仅记录其校验和。原位修复时用应用内的 Python 3.11 库编译 bootstrap；压缩后的 720 字节放入原 main 的 7545 字节压缩区，填充剩余区域并更新 TOC 中的未压缩长度，随后重新做本地临时签名。不要用宿主 Python 3.13 编译字节码放入 Python 3.11 的包。仓库中的 main.py 已直接加载兼容层，新构建无需这种二进制入口修改。

以上记录是原位修复说明，并非针对任意版本发布包的自动修复器；不要将这些偏移或尺寸硬编码用于其他版本。

## 权限与全屏

只读事件通道使用 `CGPreflightListenEventAccess` 检查输入监控授权，`CGEventTapCreate` 的 options 为 `1`（listen-only），始终返回原始事件。系统可能会在授权不匹配时短暂发送少量鼠标事件，然后禁用通道；这并不表示权限有效。

每次重新签名都会改变临时签名的 CDHash。实际系统日志曾明确报告旧、新代码要求不匹配，因此授权刷新必须计入安装验收。仓库整理不应自动重签已安装应用。

Qt 的普通 WindowStaysOnTopHint 不足以实现跨其他应用的全屏空间。当前组合使用 NSPanel、非激活样式、辅助应用策略、CanJoinAllSpaces / FullScreenAuxiliary / CanJoinAllApplications、关闭隐藏行为及 Space 变化通知。PetWidget 和 TimerWidget 都必须处理，不能仅修改桌宠类。

## 已完成的本机验收

- 原版结构修复后完整签名校验通过。
- 原生输入回调的字母键、按下/松开、鼠标按钮转换和原事件返回均做过本地验证。
- 用户在刷新输入监控授权后确认键鼠互动恢复。
- 连续 20 次桌宠动画后，静止画面与初始像素完全一致；原生阴影已关闭。
- 在访达全屏空间中检查桌宠及计时器：两者都 visible、active_space，且为 NSPanel；退出全屏后正常。
- 当前仓库副本对已安装应用的兼容层逐字节核对，完整签名验证。

限制：以上是当前安装包的验收，未对本分支从源码重建后的应用做 GUI、全屏、权限或计时逻辑的完整验收；其他 macOS 版本和 Intel 平台也未实测。

## 恢复与清理

用户已要求删除修复前的三个 ZIP 备份；此前临时编译器、测试应用、截图和采样日志也已清理。不要依赖这些已删除文件。当前可用的源码保存在本仓库；如需重装，应保留当前可运行应用作为明确授权的临时回滚副本，验证完成后再清理。


## 交互与汉化修复（2026-11-01）

- 原来只有把桌宠拖到计时器上方的绑定路径，而且检测整张皮肤的中心；544×432 这类大皮肤的中心远离计时器，导致视觉上贴近也无法绑定。改用底部锚点，并补上把计时器拖到桌宠脚下的对称路径。
- 计时器的标题/时间标签统一安装事件过滤器，整张卡片作为拖动区域；拖动超过系统阈值后才吸附，普通点击不触发绑定。原生计时器面板允许首击交互，保留原有全屏行为。
- 相邻计时器只在另一轴也接近时吸附，修复跨屏或距离很远仍被拉齐的问题；几何运算统一使用排他右/下边界，消除一像素间距误差。
- 以补充翻译表和已有 UI 构造入口修复漏译，不覆盖用户自定义名称或分组内容。
- `core/interaction_fixes.py` 安装过程幂等，可供源码启动及旧发布包复用；旧包通过 `macos_compat.py` 从 Resources 加载 sidecar 模块，新源码直接导入同一文件。
- 7 个纯几何测试通过；使用应用自带 Qt 的 `macos/tests/gui_probe.py` 验证了从两个标签拖动、大皮肤双向绑定、绑定后联动及坐标保存、关闭磁吸不绑定、中文子标签/对话框/主题切换。探针将配置和皮肤保存替换为内存函数，不写用户数据，也不向系统注入输入事件。

真实鼠标复测发现移动窗口会丢失后续事件，因此拖动期间显式 `grabMouse()`，松开或丢失抓取时清理状态。随后在预览副本中实际从标题、时间文字拖动，验证了放到桌宠下方绑定、拖动后成对移动及访达全屏显示。预览禁用配置写入，未将测试的位置和绑定写入用户数据。
