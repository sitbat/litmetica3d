# Litematica 3D v0.6.2 预览版

## 修复

修复 WinUI 程序启动时立即退出的问题。0.6.1 的界面已移除“二进制 STL”选框，但启动时的参数同步代码仍访问 `stl_binary` 控件，导致 `KeyNotFoundException`；Windows 将异常记录为 `Microsoft.UI.Xaml.dll` 中的 `0xc000027b` 崩溃。0.6.2 删除了这处无效控件访问，STL 导出仍固定使用二进制格式。

## 使用方法

下载 `Litematica3D-WinUI-v0.6.2-win-x64.zip`，完整解压到一个新文件夹后，运行其中的 `Litmetica3D.WinUI.exe`。请保留整个文件夹；单独复制 EXE 无法运行。已有的 0.6.1 文件夹无需覆盖，可直接删除或留作对照。

## 验证

- 修复前捕获到 `MainWindow.Sync()` 访问缺失的 `stl_binary` 控件；修复后窗口可创建并持续运行。
- Release 配置构建通过，0 警告、0 错误。
- 打印、视觉、渲染预设仍沿用原有参数；转换引擎和 Minecraft 26.2 资源没有改动。

0.6.1 的 GitHub 发布包含有此启动错误，请使用 0.6.2。
