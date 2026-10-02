"""Shared process-based conversion worker for the Qt interfaces."""

from __future__ import annotations

from dataclasses import asdict
import json
import pathlib
import queue
import tempfile
import time

from PySide6.QtCore import QObject, Signal, Slot

from .output_layout import next_model_path, normalize_output_root, publish_model_directory


class GUIConversionCancelled(Exception):
    pass


def _conversion_process(options_data, events, cancel_event):
    from .conversion import ConversionCancelled, ConversionOptions, convert
    try:
        report = convert(
            ConversionOptions(**options_data),
            lambda stage, value, text: events.put(
                ("progress", stage, value, text)
            ),
            cancel_event.is_set,
        )
        events.put(("result", report))
    except ConversionCancelled:
        events.put(("cancelled",))
    except Exception as exc:
        events.put(("error", str(exc)))


class ConversionWorker(QObject):
    progress = Signal(float, str, str)
    log = Signal(str)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal(str)
    report_ready = Signal(str)

    def __init__(self, files, output_dir, options, context, cancel_event):
        super().__init__()
        self.files = [pathlib.Path(p) for p in files]
        self.output_dir = normalize_output_root(output_dir)
        self.options = options
        self.context = context
        self.cancel_event = cancel_event

    @Slot()
    def run(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            regions = tuple(x.strip() for x in self.options["regions"].split(",")
                            if x.strip())
            for index, source in enumerate(self.files):
                if self.cancel_event.is_set():
                    raise GUIConversionCancelled()
                fmt = self.options["format"]
                data = {
                    "input_path": source,
                    "output_path": next_model_path(self.output_dir, source, fmt),
                    "output_format": fmt,
                    "water": self.options["water"],
                    "fallback": self.options["fallback"],
                    "optimize": self.options["optimize"],
                    "minimum_thickness": self.options["thickness"],
                    "scale": self.options["scale"],
                    "center": self.options["center"],
                    "color": self.options["color"],
                    "textures": self.options["textures"],
                    "seamless_glass": self.options.get("seamless_glass", False),
                    "solid_textures": self.options.get("solid_textures", False),
                    "emission": self.options["emission"],
                    "emission_strength": self.options["emission_strength"],
                    "blender_lights": self.options["blender_lights"],
                    "emission_config": (
                        pathlib.Path(self.options["emission_config"])
                        if self.options["emission_config"] else None
                    ),
                    "regions": regions if len(self.files) == 1 else (),
                    "geometry": self.options["geometry"],
                    "components": self.options["components"],
                    "cavities": self.options["cavities"],
                    "boolean_fallback": self.options["boolean_fallback"],
                    "min_component_volume": self.options["min_component_volume"],
                    "save_report": False,
                }
                self.log.emit(f"[{index + 1}/{len(self.files)}] 开始：{source.name}")
                with tempfile.TemporaryDirectory(prefix=".litmetica3d-", dir=self.output_dir) as scratch:
                    stage = pathlib.Path(scratch) / source.stem
                    staged_data = {**data, "output_path": stage / data["output_path"].name}
                    report = self._run_one(staged_data, index, len(self.files))
                    if self.cancel_event.is_set():
                        raise GUIConversionCancelled()
                    published = publish_model_directory(
                        stage, self.output_dir, source, fmt, data["output_path"],
                    )
                    report.output_path = str(published)
                self.report_ready.emit(json.dumps(
                    asdict(report), ensure_ascii=False, indent=2
                ))
                self.log.emit(
                    f"完成：{report.triangles} 个三角形，"
                    f"回落 {report.fallback_cubes}，忽略 {report.ignored}"
                )
                if report.geometry_mode == "visual":
                    self.log.emit(
                        f"视觉：删除透明像素 {report.transparent_pixels_removed}，"
                        f"染色贴图 {report.tinted_textures}，"
                        f"发光方块 {report.emissive_blocks}"
                    )
                if report.solid:
                    self.log.emit(
                        f"打印检查：{'通过' if report.solid.printable else '失败'}，"
                        f"壳体 {report.solid.component_count}，"
                        f"空腔 {report.solid.cavity_count}"
                    )
            self.completed.emit("全部转换完成")
        except GUIConversionCancelled:
            self.cancelled.emit("转换已取消")
        except Exception as exc:
            self.failed.emit(str(exc))

    def _run_one(self, data, file_index, file_count):
        events = self.context.Queue()
        process = self.context.Process(
            target=_conversion_process,
            args=(data, events, self.cancel_event), daemon=True,
        )
        process.start()
        result = error = None
        cancelled_at = None
        try:
            while True:
                if self.cancel_event.is_set() and cancelled_at is None:
                    cancelled_at = time.monotonic()
                if (cancelled_at is not None and process.is_alive()
                        and time.monotonic() - cancelled_at > 2):
                    process.terminate()
                    process.join(2)
                    raise GUIConversionCancelled()
                try:
                    kind, *payload = events.get(timeout=.1)
                except queue.Empty:
                    if not process.is_alive():
                        break
                    continue
                if kind == "progress":
                    stage, value, text = payload
                    overall = ((file_index + value) / file_count) * 100
                    self.progress.emit(overall, text, stage)
                elif kind == "result":
                    result = payload[0]
                    break
                elif kind == "cancelled":
                    raise GUIConversionCancelled()
                elif kind == "error":
                    error = payload[0]
                    break
        finally:
            if process.is_alive():
                process.join(1)
            if process.is_alive():
                process.terminate()
                process.join(2)
            events.close()
        if error:
            raise RuntimeError(error)
        if result is None:
            if self.cancel_event.is_set():
                raise GUIConversionCancelled()
            raise RuntimeError(f"转换进程异常退出（退出码 {process.exitcode}）")
        return result
