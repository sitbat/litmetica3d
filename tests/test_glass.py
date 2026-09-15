import io
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from litmetica3d.glass import COLORS, glass_faces
from litmetica3d.model_loader import ModelLoader
from litmetica3d.visual_mesh import CompactVisualMesh, export_compact_obj

ASSETS = Path(__file__).parents[1] / 'litmetica3d/mc_assets/26.2'


def test_all_glass_colors_uniform_and_transparent():
    loader = ModelLoader(ASSETS, visual_textures=True)
    try:
        colors = set()
        for name in ['glass'] + [c + '_stained_glass' for c in COLORS]:
            key = loader.seamless_glass_texture('minecraft:' + name)
            im = Image.open(io.BytesIO(loader.texture_bytes(key))).convert('RGBA')
            assert im.size == (1, 1)
            pixel = im.getpixel((0, 0))
            assert 0 < pixel[3] < 255
            colors.add(pixel[:3])
        assert len(colors) == 17
    finally:
        loader.close()


def test_same_color_contact_removed_and_different_color_kept():
    name = 'minecraft:red_stained_glass'
    neighbors = {(1, 0, 0): SimpleNamespace(name=name, properties={})}
    assert len(glass_faces(name, {}, (0, 0, 0), neighbors, 'test')) == 5
    neighbors[(1, 0, 0)].name = 'minecraft:blue_stained_glass'
    assert len(glass_faces(name, {}, (0, 0, 0), neighbors, 'test')) == 6


def test_pane_connected_arm_has_no_internal_end():
    name = 'minecraft:red_stained_glass_pane'
    props = {'east': 'true', 'west': 'true'}
    neighbors = {(1, 0, 0): SimpleNamespace(name=name, properties=props)}
    faces = glass_faces(name, props, (0, 0, 0), neighbors, 'test')
    assert not any(all(v.x == 1 for v in f.vertices) for f in faces)
    assert any(all(v.x == 0 for v in f.vertices) for f in faces)
    assert all(7/16 <= v.z <= 9/16 for f in faces for v in f.vertices)


def test_obj_writes_scalar_opacity_and_blender_setup(tmp_path):
    loader = ModelLoader(ASSETS, visual_textures=True)
    try:
        name = 'minecraft:red_stained_glass'
        mesh = CompactVisualMesh()
        key = loader.seamless_glass_texture(name)
        for face in glass_faces(name, {}, (0, 0, 0), {}, key):
            mesh.add_face(face)
        mesh.flush()
        output = tmp_path / 'glass.obj'
        export_compact_obj(mesh, output, texture_provider=loader.texture_bytes,
                           alpha_provider=loader.texture_alpha_bytes)
        mtl = output.with_suffix('.mtl').read_text()
        assert 'd 0.400000' in mtl
        assert 'map_d' not in mtl  # no double multiplication of opacity
        manifest = json.loads((tmp_path / 'glass.blender_emission.json').read_text())
        assert manifest['materials'][0]['glass_opacity'] == 0.4
        script = (tmp_path / 'glass_blender_setup.py').read_text(encoding='utf-8')
        assert 'alpha_socket.default_value = float(opacity)' in script
        compile(script, '<generated>', 'exec')
    finally:
        loader.close()


def test_gui_glass_is_visual_only():
    from PySide6.QtWidgets import QApplication
    from litmetica3d.gui_app import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window._apply_preset('print')
        assert not window.seamless_glass_check.isEnabled()
        assert not window._snapshot()['seamless_glass']
        window._apply_preset('visual')
        assert window.seamless_glass_check.isEnabled()
        assert window.seamless_glass_check.text() == '半透明无缝玻璃'
        assert not window._snapshot()['seamless_glass']
        window._apply_preset('render')
        assert window._snapshot()['seamless_glass']
        assert window.current_preset == 'render'
        window._apply_preset('visual')
        assert not window._snapshot()['seamless_glass']
        window.seamless_glass_check.setChecked(True)
        assert window._snapshot()['seamless_glass']
        window._apply_preset('print')
        assert not window._snapshot()['seamless_glass']
    finally:
        window.close()


def test_conversion_switch_and_print_isolation(tmp_path):
    from unittest.mock import patch
    from litmetica3d.conversion import ConversionOptions, convert
    from litmetica3d.litematic import Schematic, Region, BlockState
    schematic = Schematic(6, 0, regions={
        'glass': Region('glass', (0, 0, 0), (2, 1, 1),
                        [BlockState('minecraft:red_stained_glass')],
                        {(0, 0, 0): 0, (1, 0, 0): 0})
    })
    with patch('litmetica3d.conversion.load_schematic', return_value=schematic):
        for enabled in (False, True):
            output = tmp_path / f'visual-{enabled}.obj'
            report = convert(ConversionOptions(
                input_path=tmp_path/'test.litematic', output_path=output,
                output_format='obj', geometry='visual', asset_path=ASSETS,
                seamless_glass=enabled, optimize='none', save_report=False,
            ))
            mtl = output.with_suffix('.mtl').read_text()
            assert ('generated_seamless_glass' in mtl) == enabled
            assert report.seamless_glass_blocks == (2 if enabled else 0)
        outputs = []
        for enabled in (False, True):
            output = tmp_path / f'print-{enabled}.stl'
            report = convert(ConversionOptions(
                input_path=tmp_path/'test.litematic', output_path=output,
                output_format='stl', geometry='print', asset_path=ASSETS,
                seamless_glass=enabled, save_report=False,
            ))
            assert report.seamless_glass is False
            outputs.append(output.read_bytes())
        assert outputs[0] == outputs[1]
