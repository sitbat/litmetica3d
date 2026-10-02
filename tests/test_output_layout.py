import os
import json
from pathlib import Path
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from litmetica3d.conversion import ConversionReport
from litmetica3d.gui_app import MainWindow
from litmetica3d.gui_worker import ConversionWorker
from litmetica3d.output_layout import next_model_path, normalize_output_root


def test_output_root_is_added_only_once(tmp_path):
    root = tmp_path / "L3D_output"
    assert normalize_output_root(tmp_path) == root
    assert normalize_output_root(root) == root
    assert normalize_output_root(tmp_path / "l3d_OUTPUT") == tmp_path / "l3d_OUTPUT"


def test_next_model_path_keeps_previous_results(tmp_path):
    root = tmp_path / "L3D_output"
    source = tmp_path / "城堡.litematic"
    first = next_model_path(root, source, "stl")
    assert first == root / "城堡" / "城堡.stl"
    first.parent.mkdir(parents=True)
    assert next_model_path(root, source, "obj") == root / "城堡 (2)" / "城堡.obj"


def test_worker_groups_multiple_files_and_obj_assets(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        options = window._snapshot()
        options["format"] = "obj"
        sources = [
            tmp_path / "first" / "仓库.litematic",
            tmp_path / "second" / "仓库.litematic",
            tmp_path / "third" / "农场.litematic",
        ]
        worker = ConversionWorker(sources, tmp_path, options, None, threading.Event())
        outputs = []
        completed = []
        failures = []
        worker.completed.connect(completed.append)
        worker.failed.connect(failures.append)
        worker.report_ready.connect(lambda value: outputs.append(Path(json.loads(value)["output_path"])))

        def fake_convert(data, _index, _count):
            output = data["output_path"]
            output.parent.mkdir(parents=True)
            output.write_text("obj", encoding="utf-8")
            output.with_suffix(".mtl").write_text("mtl", encoding="utf-8")
            (output.parent / f"{output.stem}_textures").mkdir()
            return ConversionReport(str(data["input_path"]), str(output))

        worker._run_one = fake_convert
        worker.run()
        assert not failures
        assert completed == ["全部转换完成"]
        root = tmp_path / "L3D_output"
        assert outputs == [
            root / "仓库" / "仓库.obj",
            root / "仓库 (2)" / "仓库.obj",
            root / "农场" / "农场.obj",
        ]
        for output in outputs:
            assert output.is_file()
            assert output.with_suffix(".mtl").is_file()
            assert (output.parent / f"{output.stem}_textures").is_dir()
            assert not output.with_suffix(".report.json").exists()
    finally:
        window.close()
        app.processEvents()
