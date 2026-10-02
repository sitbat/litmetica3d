import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from litmetica3d.conversion import ConversionOptions, convert, _cluster_editable_lights
from litmetica3d.litematic import BlockState, Region, Schematic
from litmetica3d.prepared_scene import PreparedScene
from test_visual_index import read_obj


def source(block="minecraft:stone", position=(0, 0, 0), count=1):
    return Schematic(6, 3955, regions={
        "R": Region("R", position, (count, 1, 1), [BlockState(block)],
                    {(x, 0, 0): 0 for x in range(count)})
    })


@pytest.mark.parametrize("name,value", [
    ("scale", 0), ("scale", -1), ("scale", float("nan")),
    ("scale", float("inf")), ("scale", float("-inf")),
    ("minimum_thickness", 0), ("minimum_thickness", float("nan")),
    ("min_component_volume", -1), ("emission_strength", float("inf")),
])
def test_invalid_numbers_rejected_before_input_or_output(name, value, tmp_path):
    options = ConversionOptions(Path("not-read.litematic"), tmp_path / "invalid.stl")
    with patch("litmetica3d.conversion.load_schematic") as load:
        with pytest.raises(ValueError, match=name):
            convert(replace(options, **{name: value}))
    load.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_valid_scaled_stl_has_real_scaled_vertices(tmp_path):
    options = ConversionOptions(Path("fixture"), tmp_path / "scaled.stl", scale=2)
    with patch("litmetica3d.conversion.load_schematic", return_value=source()):
        report = convert(options)
    records = np.frombuffer(options.output_path.read_bytes()[84:], dtype=np.dtype([
        ("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")
    ]))
    vertices = records["vertices"].reshape(-1, 3)
    assert np.isfinite(vertices).all()
    assert np.array_equal(vertices.min(axis=0), [0, 0, 0])
    assert np.array_equal(vertices.max(axis=0), [2, 2, 2])
    assert report.solid.printable


@pytest.mark.parametrize("selected", [(), ("R",)])
@pytest.mark.parametrize("center,scale", [(False, 1), (True, 2)])
def test_emission_override_matches_original_coordinates(tmp_path, selected, center, scale):
    schematic = source("minecraft:glowstone", (10, -20, 30))
    schematic.regions["Other"] = Region(
        "Other", (-50, -40, -30), (1, 1, 1), [BlockState("minecraft:stone")], {(0, 0, 0): 0}
    )
    config = tmp_path / "lights.json"
    config.write_text(json.dumps({"rules": [
        {"region": "R", "position": [10, -20, 30], "multiplier": 0}
    ]}), encoding="utf-8")
    options = ConversionOptions(Path("fixture"), tmp_path / "model.obj", output_format="obj",
                                geometry="visual", regions=selected, center=center, scale=scale)
    with patch("litmetica3d.conversion.load_schematic", return_value=schematic):
        lit = convert(options)
        dark = convert(replace(options, emission_config=config))
    assert lit.emissive_blocks == lit.blender_lights == 1
    assert dark.emissive_blocks == dark.blender_lights == 0


def test_source_coordinates_do_not_depend_on_region_selection():
    schematic = source(position=(10, -20, 30))
    schematic.regions["Other"] = Region(
        "Other", (-50, -40, -30), (1, 1, 1), [BlockState("minecraft:stone")], {(0, 0, 0): 0}
    )
    for names in [(), ("R",)]:
        scene = PreparedScene(schematic, names)
        r = next(pos for name, pos, state in scene if name == "R")
        assert scene.source_position(r) == (10, -20, 30)
        assert list(scene) == list(scene)
    with pytest.raises(ValueError, match="missing"):
        PreparedScene(schematic, ("missing",))


def test_raw_and_safe_obj_differ_in_structure_but_preserve_surfaces(tmp_path):
    reports = {}
    parsed = {}
    for mode in ("raw", "safe", "experimental", "none"):
        output = tmp_path / mode / "model.obj"
        options = ConversionOptions(Path("fixture"), output, output_format="obj",
                                    geometry="visual", emission=False, optimize=mode)
        with patch("litmetica3d.conversion.load_schematic", return_value=source(count=2)):
            reports[mode] = convert(options)
        parsed[mode] = read_obj(output)
    assert reports["raw"].visual_optimization["enabled"] is False
    assert reports["safe"].visual_optimization["enabled"] is True
    assert len(parsed["raw"][0]) == 48
    assert len(parsed["raw"][3]) == 24
    assert len(parsed["safe"][0]) < 48
    assert len(parsed["safe"][3]) < len(parsed["raw"][3])
    assert parsed["raw"][2] == parsed["safe"][2] == parsed["experimental"][2]
    assert reports["experimental"].optimize_mode == "safe"
    assert reports["none"].optimize_mode == "raw"
    assert reports["none"].visual_optimization["enabled"] is False
    assert parsed["none"] == parsed["raw"]


def test_clustering_is_deterministic_and_preserves_power():
    def light(x, level=15):
        return dict(name=f"Light {x}", block="minecraft:glowstone", level=level,
                    color=[1, 1, 1], block_position=[x, 0, 0], position=[x + 0.5, 0.5, 0.5],
                    power=120, radius=0.14)
    sources = [light(8), light(2), light(1), light(20, level=7)]
    result = _cluster_editable_lights(sources)
    assert len(result) == 3
    group = result[0]
    assert group["block_count"] == 2
    assert group["position"] == [2, 0.5, 0.5]
    assert group["power"] == 240
    assert sum(item["power"] for item in result) == sum(item["power"] for item in sources)
    assert _cluster_editable_lights(sources) == result
