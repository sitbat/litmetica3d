# 代码审查修复记录

基线为 `866dec1f635dc4fd9fb8819b9c9c188a35144388`，对应上游 [Issue #2](https://github.com/zzhaccount1121/litmetica3d/issues/2)。本轮修复与验证日期：2026-10-03。

## 已修复问题

| 问题 | 修复结果 | 主要回归测试 |
|---|---|---|
| 1. 小调色板解码缺块 | BlockStates 最低使用 2 bit；截断数据和越界索引明确报错并标注区域 | `test_parser_regressions.py` |
| 2. Python 构建后端无效 | 改为 `setuptools.build_meta`，验证 wheel / sdist 及 editable 安装 | `test_packaging_regressions.py`、实际包安装 |
| 3. 填腔保留内部实体产生重复壳 | 填腔后重新求并集，同步更新导出网格、体积和实体数 | `test_geometry_regressions.py`、`test_cavity_reports.py` |
| 4. 打印双箱接缝与朝向错误 | 打印和视觉共用箱体、锁扣与朝向；覆盖四个方向的双箱 | `test_geometry_regressions.py`、`test_chest_uv.py` |
| 5. 忽略 `rotation.rescale` | 普通模型和透明像素几何都应用旋转补偿，并保持正确法线 | `test_geometry_regressions.py` |
| 6. 忽略 `uvlock` | 在透明像素裁剪之前修正 UV，覆盖 XY 旋转、偏移 UV 与面纹理旋转 | `test_geometry_regressions.py` |
| 7. 非法数值仍被导出 | 统一 CLI/API/bridge 参数校验；变换后检查实际网格；稳定计算 STL 法线，OBJ 保留 float32 精度；拒绝非有限发光数据 | `test_conversion_regressions.py`、`test_numeric_exports.py`、`test_emission_numeric.py` |
| 8. 优化选项不产生差异 | 视觉 OBJ 的 `raw` 写原始网格，`safe` 复用顶点并恢复矩形四边面；旧 `experimental` 明确按 `safe` 处理，更新界面与文档 | `test_conversion_regressions.py`、`test_visual_index.py` |
| 9. 发光规则坐标随归零变化 | 匹配区域 Position + 局部坐标；导出居中、缩放和区域筛选不影响匹配 | `test_conversion_regressions.py` |
| 10. 批量输出名称冲突 | 批内预留名称，发布时独占创建目录，若已被占用则重新编号 | `test_frontend_regressions.py`、`test_output_layout.py`、EngineSmoke |
| 11. Windows wheel 无法启动 GUI | 存在已构建 WinUI 时优先使用，否则启动 Qt | `test_packaging_regressions.py`、实际 wheel 安装 |
| 12. Qt 打开目录依赖 Windows | 使用 `QDesktopServices.openUrl` 打开本地目录 | `test_frontend_regressions.py` |

补充修复：NBT 有符号 byte、数组截断与负长度；组件过滤后再计算填腔体积，避免把删除组件的体积抵消填腔量。

## 结构与性能改进

- 拆出共享参数、灯光处理、场景遍历和 Qt worker；保留 `conversion.ConversionOptions` 等旧导入入口。
- 聚类光源只排序一次，再遍历邻居，避免孤立光源场景反复扫描剩余集合。
- 场景准备保留区域引用，取消两份完整的方块中间列表。
- CLI 与两套 Qt 区域列表读取轻量信息，流式跳过 BlockStates 和实体载荷。
- Python、Qt、WinUI 和打包脚本统一从 `__version__` 读取版本；共享便携 spec，保留旧 spec 入口。
- 增加开发/构建依赖组和 Windows/Linux、Python 3.10/3.13 CI。

下列是 Windows / Python 3.13.0 上的合成微基准，时间取三次运行中位数；不是完整转换或真实大型投影的耗时承诺。

| 场景 | 基线 | 修复后 |
|---|---:|---:|
| 2,000 个互不相邻的同类灯光聚类 | 0.0276 秒 | 0.00345 秒 |
| 10,000 个互不相邻的同类灯光聚类 | 0.924 秒 | 0.0265 秒 |
| 100,000 方块场景准备 + 两次遍历 | 0.119 秒 | 0.0853 秒 |
| 同一场景准备与遍历的额外 Python 分配峰值 | 35.08 MiB | 0.124 MiB |

聚类比较运行基线提交中的原函数，并确认输出列表相同；场景比较原来的归零列表与新遍历器，确认逐项输出相同。内存由 `tracemalloc` 测量，不含预先创建的输入字典，不代表进程 RSS 或整个转换的内存占用。

## 验证范围

- 本地全量 Python 回归：`python -m pytest -q -p no:cacheprovider`，269 项测试、73 项子测试通过，无警告；Qt 使用 `QT_QPA_PLATFORM=offscreen`。
- wheel 和 sdist 可构建；独立安装目录能导入包、读取内置 stone 资源并执行 `--version`；editable 安装通过。
- C# EngineSmoke 实际转换、目录编号和取消三项通过。
- WinUI Release 编译成功，0 警告、0 错误。此次工作目录很长，构建时指定较短的中间输出目录以避开 XAML 编译器路径问题。
- Qt 使用 offscreen 回归；跨平台目录打开验证调用路径，未在 Linux/macOS 真正启动文件管理器。没有进行交互式桌面操作或真实大型投影的性能验证。
- CI 已加入仓库，本地验证不替代远程矩阵运行结果。便携包脚本与 spec 入口完成静态/执行检查，本轮没有发布新的便携版二进制。
