"""Regressions for output reservation, publication and desktop integration."""
import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from litmetica3d import __version__
from litmetica3d import gui_app, gui_qt
from litmetica3d.conversion import ConversionReport
from litmetica3d.gui_worker import ConversionWorker
from litmetica3d.output_layout import next_model_path, publish_model_directory
from litmetica3d.winui_bridge import run


def test_batch_reserves_suffixed_names_and_reports_each_result(tmp_path):
    root = tmp_path / "L3D_output"
    (root / "a").mkdir(parents=True)
    sources = [tmp_path / "a.litematic", tmp_path / "a (2).litematic"]
    for source in sources:
        source.touch()
    reports = []

    def convert(options, *_args):
        options.output_path.write_text(options.input_path.name, encoding="utf-8")
        return ConversionReport(str(options.input_path), str(options.output_path))

    with patch("litmetica3d.conversion.convert", convert):
        run({"files": [str(p) for p in sources], "output_dir": str(tmp_path)},
            lambda: False, lambda kind, **data: reports.append(data["report"]) if kind == "report" else None)
    models = [Path(report["output_path"]) for report in reports]
    assert models == [root / "a (2)" / "a.stl", root / "a (2) (2)" / "a (2).stl"]
    assert [model.read_text(encoding="utf-8") for model in models] == [p.name for p in sources]


def test_publish_retries_when_destination_is_claimed_during_conversion(tmp_path):
    source = tmp_path / "a.litematic"
    source.touch()
    root = tmp_path / "L3D_output"
    reports = []

    def convert(options, *_args):
        # Another process creates even an empty directory after planning.
        (root / "a").mkdir()
        options.output_path.write_text("model", encoding="utf-8")
        return ConversionReport(str(source), str(options.output_path))

    with patch("litmetica3d.conversion.convert", convert):
        run({"files": [str(source)], "output_dir": str(tmp_path)}, lambda: False,
            lambda kind, **data: reports.append(data["report"]) if kind == "report" else None)
    assert list((root / "a").iterdir()) == []
    assert Path(reports[0]["output_path"]) == root / "a (2)" / "a.stl"
    assert (root / "a (2)" / "a.stl").read_text(encoding="utf-8") == "model"
    assert not list(root.glob(".litmetica3d-*"))


def test_publication_rolls_back_only_its_own_files_on_failure(tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    stage = tmp_path / "stage"
    stage.mkdir()
    for name in ("a.obj", "a.mtl"):
        (stage / name).write_text(name, encoding="utf-8")
    model = next_model_path(root, Path("a.litematic"), "obj")
    original_rename = Path.rename
    calls = 0

    def fail_second(self, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("publication failed")
        return original_rename(self, target)

    with patch.object(Path, "rename", fail_second), pytest.raises(OSError, match="publication failed"):
        publish_model_directory(stage, root, Path("a.litematic"), "obj", model)
    assert not model.parent.exists()
    assert sorted(path.name for path in stage.iterdir()) == ["a.mtl", "a.obj"]


@pytest.mark.parametrize("module", [gui_app, gui_qt])
def test_qt_open_output_uses_local_url_and_current_version(tmp_path, module):
    app = QApplication.instance() or QApplication([])
    window = module.MainWindow()
    folder = tmp_path / "L3D_output"
    folder.mkdir()
    try:
        window.output_edit.setText(str(tmp_path))
        with patch.object(module.QDesktopServices, "openUrl", return_value=True) as open_url:
            window._open_output()
        assert open_url.call_args.args[0].toLocalFile() == str(folder.resolve()).replace("\\", "/")
        assert __version__ in window.windowTitle()
        assert module.VERSION == __version__
    finally:
        window.close()
        app.processEvents()


def test_worker_cancellation_discards_staged_model(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = gui_app.MainWindow()
    try:
        event = threading.Event()
        worker = ConversionWorker([tmp_path / "a.litematic"], tmp_path, window._snapshot(), None, event)
        cancellations = []
        reports = []
        worker.cancelled.connect(cancellations.append)
        worker.report_ready.connect(reports.append)

        def convert(data, *_args):
            model = data["output_path"]
            model.parent.mkdir(parents=True)
            model.write_text("partial", encoding="utf-8")
            event.set()
            return ConversionReport(str(data["input_path"]), str(model))

        worker._run_one = convert
        worker.run()
        assert cancellations == ["转换已取消"]
        assert reports == []
        assert list((tmp_path / "L3D_output").iterdir()) == []
    finally:
        window.close()
        app.processEvents()


def test_new_gui_does_not_import_the_legacy_window():
    result = subprocess.run([sys.executable, "-c", "import sys; import litmetica3d.gui_app; assert 'litmetica3d.gui_qt' not in sys.modules"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_legacy_optimization_setting_maps_to_supported_mode():
    app = QApplication.instance() or QApplication([])
    settings = QSettings("litmetica3d", "litmetica3d-v0.5")
    settings.setValue("optimize", "experimental")
    window = gui_qt.MainWindow()
    try:
        assert window._value(window.optimize_combo) == "safe"
        assert window.optimize_combo.count() == 2
        window._preset("print")
        assert not window.optimize_combo.isEnabled()
        window._preset("visual")
        assert window.optimize_combo.isEnabled()
    finally:
        window.close()
        settings.clear()
        app.processEvents()


def test_shared_worker_uses_spawned_conversion_process(tmp_path):
    from test_winui_bridge import write_fixture

    app = QApplication.instance() or QApplication([])
    window = gui_app.MainWindow()
    source = tmp_path / "spawn.litematic"
    write_fixture(source)
    context = mp.get_context("spawn")
    try:
        worker = ConversionWorker([source], tmp_path, window._snapshot(), context, context.Event())
        completed = []
        failures = []
        worker.completed.connect(completed.append)
        worker.failed.connect(failures.append)
        worker.run()
        assert not failures
        assert completed == ["全部转换完成"]
        assert (tmp_path / "L3D_output" / "spawn" / "spawn.stl").is_file()
        assert not list((tmp_path / "L3D_output").glob(".litmetica3d-*"))
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("value", [True, False, None, "nan", float("inf"), 0, -1])
def test_bridge_uses_shared_numeric_validation_before_creating_output(tmp_path, value):
    source = tmp_path / "a.litematic"
    source.touch()
    with pytest.raises(ValueError, match="scale"):
        run({"files": [str(source)], "output_dir": str(tmp_path), "options": {"scale": value}}, lambda: False)
    assert not (tmp_path / "L3D_output").exists()


@pytest.mark.parametrize("module", [gui_app, gui_qt])
def test_qt_region_listing_skips_block_decoding(tmp_path, module):
    from test_winui_bridge import write_fixture

    app = QApplication.instance() or QApplication([])
    window = module.MainWindow()
    source = tmp_path / "regions.litematic"
    write_fixture(source)
    try:
        with patch("litmetica3d.litematic._decode_block_states", side_effect=AssertionError("decoded blocks")):
            if module is gui_qt:
                window._add_files([str(source)])
            else:
                with patch.object(module.QFileDialog, "getOpenFileName", return_value=(str(source), "")):
                    window._choose_input()
        assert window.regions_edit.text() == "测试区域"
    finally:
        window.close()
        app.processEvents()
