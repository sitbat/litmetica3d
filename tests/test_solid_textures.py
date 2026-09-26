import pathlib
import unittest
from unittest.mock import patch

from litmetica3d.model_loader import ModelLoader
from litmetica3d.cli import _parser

ASSETS = pathlib.Path(__file__).parents[1] / 'litmetica3d/mc_assets/26.2'


class SolidTextureTests(unittest.TestCase):
    def test_opacity_map_has_actual_alpha_not_just_grayscale(self):
        import io
        from PIL import Image
        loader = ModelLoader(ASSETS, visual_textures=True, solid_textures=True)
        try:
            source = Image.new('RGBA', (3, 1))
            source.putdata([(10, 20, 30, a) for a in (0, 128, 255)])
            out = io.BytesIO()
            source.save(out, format='PNG')
            loader._generated_textures['generated:test/mask'] = out.getvalue()
            raw = loader.texture_alpha_bytes('generated:test/mask')
            with Image.open(io.BytesIO(raw)) as mask:
                self.assertEqual(mask.mode, 'RGBA')
                for x, expected in enumerate((0, 128, 255)):
                    self.assertEqual(mask.getpixel((x, 0)), (expected,) * 4)
        finally:
            loader.close()

    def test_solid_models_skip_pixel_geometry_and_keep_textures(self):
        loader = ModelLoader(ASSETS, visual_textures=True, solid_textures=True)
        try:
            with patch.object(loader, '_alpha_shell_faces', side_effect=AssertionError), \
                 patch.object(loader, '_pixel_extrusion_faces', side_effect=AssertionError):
                for name, props, count in (
                    ('oak_leaves', {}, 6),
                    ('short_grass', {}, 12),
                    ('tube_coral_fan', {}, 24),
                    ('tube_coral_wall_fan', {'facing': 'north'}, 12),
                ):
                    with self.subTest(name=name):
                        result = loader.resolve('minecraft:' + name, props)
                        self.assertEqual(result.status, 'ok')
                        self.assertEqual(len(result.faces), count)
                        self.assertTrue(all(f.texture and len(f.uvs) == 4 for f in result.faces))
                self.assertEqual(loader.transparent_pixels_removed, 0)
        finally:
            loader.close()

    def test_default_keeps_holes_and_print_is_unchanged(self):
        for visual in (False, True):
            normal = ModelLoader(ASSETS, visual_textures=visual)
            solid = ModelLoader(ASSETS, visual_textures=visual, solid_textures=True)
            try:
                a = normal.resolve('minecraft:oak_leaves', {}, closed=not visual)
                b = solid.resolve('minecraft:oak_leaves', {}, closed=not visual)
                if visual:
                    self.assertGreater(len(a.faces), len(b.faces))
                    self.assertEqual(normal.texture_bytes(a.faces[0].texture), solid.texture_bytes(b.faces[0].texture))
                else:
                    self.assertEqual(a.faces, b.faces)
            finally:
                normal.close()
                solid.close()

    def test_cli_default_and_flag(self):
        self.assertFalse(_parser().parse_args([]).solid_textures)
        self.assertTrue(_parser().parse_args(['--solid-textures']).solid_textures)


def test_gui_solid_textures_available_for_all_presets():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from litmetica3d.gui_app import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        for preset in ('print', 'visual', 'render'):
            window._apply_preset(preset)
            check = window.solid_textures_check
            assert check.isEnabled()
            assert not check.isChecked()
            assert check.text().startswith('**') and check.text().endswith('**')
            check.setChecked(True)
            assert window.current_preset == 'custom'
            assert window._snapshot()['solid_textures']
            assert '填平镂空' in window.preset_summary.toPlainText()
    finally:
        window.close()
