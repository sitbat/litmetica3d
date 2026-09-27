# Litematica 3D v0.6.0 preview

## 合并说明

本版合并 GitHub PR [#1：新增原生 WinUI 3 转换工作台](https://github.com/zzhaccount1121/litmetica3d/pull/1)，将 Windows 原生桌面界面纳入主分支。PR 的提交历史和贡献者信息通过 merge commit 保留。

## 主要功能

- 原生 WinUI 3 界面，复用现有 Python 转换引擎。
- 打印、视觉、渲染和自定义预设；高级选项会按格式和用途联动。
- 支持投影多选、拖放和批量转换，并避免覆盖已有同名结果。
- 提供实时进度、转换日志、JSON 报告、取消和主题设置。
- 提供独立 Windows x64 ZIP，包含 Python、转换依赖和 Minecraft 26.2 资源。

## 使用方法

下载 `Litematica3D-WinUI-v0.6.0-win-x64.zip`，完整解压后启动 `Litmetica3D.WinUI.exe`。添加 `.litematic` 文件、选择输出目录和预设，然后开始转换。详细界面说明见 [frontend/README.md](frontend/README.md)。

## 已知问题

- 繁忙转换期间，高频进度事件可能挤占界面线程，耗时显示会停滞；该问题在 v0.6.1 修复。
- 转换报告会同时保存为投影目录内的 `.report.json`；v0.6.1 改为默认只在界面显示，用户需要时再手动另存。
- 超大型投影仍可能让原生布尔运算长时间没有新进度；v0.6.1 会持续显示耗时和后台状态，并保留取消操作。
