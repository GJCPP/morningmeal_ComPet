# Windows 本地构建

桌面固定入口是 `ComPet.lnk`，始终指向本仓库的：

`morningmeal_Compet_V3\dist\Compet-V3\Compet-V3.exe`

后续修改源码后，在仓库根目录运行同一个命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\build.ps1
```

脚本先构建到固定的临时目录，再用隔离用户配置进行 8 秒离屏启动检查。检查成功才更新固定程序目录及快捷方式；不会自动启动正式应用。默认不生成 ZIP 或带版本后缀的发布目录。`ExecutionPolicy Bypass` 只作用于本次 PowerShell 进程。

如果固定目录内的应用正在运行，脚本会停止并提示先从托盘菜单退出，避免打断计时或覆盖正在使用的 DLL。其他旧版本不会被自动关闭。更新后仍从桌面同一个快捷方式启动。

用户配置及计时数据仍由应用保存到 `%USERPROFILE%\.morningmeal_ComPet`，构建与启动检查不迁移或覆盖这些数据。不要移动仓库目录；如需迁移，在新位置重新运行脚本更新快捷方式。

## 首次安装依赖

需要 Git 和 uv。已有 `.venv` 及依赖时无需重复安装。

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
```

## 验证和恢复

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s macos/tests -p 'test_*.py' -v
```

脚本只保留一份上一构建，位于 `morningmeal_Compet_V3\build\windows-previous`。如果需要恢复，退出应用后，在资源管理器中将当前 `dist\Compet-V3` 文件夹移至其他位置，再将 `build\windows-previous` 整个文件夹移到 `dist` 并命名为 `Compet-V3`；桌面快捷方式无需更改。源码、用户设置和计时数据不受此恢复操作影响。

离屏检查确认启动和资源初始化，完整桌面交互仍需实际操作验证。
