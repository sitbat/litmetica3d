"""Reject invalid emission values before creating an OBJ, MTL or manifest."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from litmetica3d.block_models import _cuboid
from litmetica3d.conversion import ConversionOptions, convert
from litmetica3d.emission import load_overrides, resolve_override
from litmetica3d.litematic import BlockState, Region, Schematic
from litmetica3d.visual_mesh import CompactVisualMesh, export_compact_obj


def source():
    return Schematic(6, 3955, regions={
        "R": Region("R", (0, 0, 0), (1, 1, 1), [BlockState("minecraft:glowstone")],
                    {(0, 0, 0): 0})
    })


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -1, True])
@pytest.mark.parametrize("field", ["global_multiplier", "rule.multiplier"])
def test_config_multipliers_must_be_finite_nonnegative(tmp_path, value, field):
    config = {"global_multiplier": value} if field == "global_multiplier" else {"rules": [{"multiplier": value}]}
    path = tmp_path / "emission.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="multiplier"):
        load_overrides(path)
    with pytest.raises(ValueError, match="multiplier"):
        resolve_override(config, "minecraft:glowstone", {}, "R", (0, 0, 0))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_config_colors_must_be_finite(tmp_path, value):
    path = tmp_path / "emission.json"
    path.write_text(json.dumps({"rules": [{"color": [value, 1, 0]}]}))
    with pytest.raises(ValueError, match="color"):
        load_overrides(path)


@pytest.mark.parametrize("strength", [1e38, 1e308])
@pytest.mark.parametrize("mode", ["exact", "clustered", "material"])
def test_finite_strength_cannot_overflow_final_emission(tmp_path, strength, mode):
    options = ConversionOptions(Path("fixture"), tmp_path / "output/model.obj",
                                geometry="visual", output_format="obj",
                                emission_strength=strength, blender_lights=mode)
    with patch("litmetica3d.conversion.load_schematic", return_value=source()):
        with pytest.raises(ValueError, match="emission_strength"):
            convert(options)
    assert not options.output_path.parent.exists()


def test_final_scaled_light_power_must_fit_blender_float(tmp_path):
    options = ConversionOptions(Path("fixture"), tmp_path / "output/model.obj",
                                geometry="visual", output_format="obj", scale=1e20)
    with patch("litmetica3d.conversion.load_schematic", return_value=source()):
        with pytest.raises(ValueError, match="power"):
            convert(options)
    assert not options.output_path.parent.exists()


@pytest.mark.parametrize("invalid", [
    {"power": float("inf")}, {"radius": -1}, {"position": [float("nan"), 0, 0]},
    {"color": [0, float("inf"), 0]}, {"extra": float("nan")},
])
def test_direct_export_checks_lights_before_writing_any_files(tmp_path, invalid):
    mesh = CompactVisualMesh()
    mesh.add_faces(_cuboid(0, 0, 0, 1, 1, 1, "test"))
    with pytest.raises(ValueError, match="发光"):
        export_compact_obj(mesh, tmp_path / "model.obj", light_sources=[invalid])
    assert not list(tmp_path.iterdir())


def test_zero_multiplier_remains_valid_and_manifest_is_strict_json(tmp_path):
    path = tmp_path / "emission.json"
    path.write_text(json.dumps({"global_multiplier": 0, "rules": []}))
    options = ConversionOptions(Path("fixture"), tmp_path / "output/model.obj",
                                geometry="visual", output_format="obj", emission_config=path)
    with patch("litmetica3d.conversion.load_schematic", return_value=source()):
        report = convert(options)
    def reject_constant(value):
        raise AssertionError(f"nonfinite JSON value: {value}")
    manifest = json.loads((options.output_path.parent / "model.blender_emission.json").read_text(),
                          parse_constant=reject_constant)
    assert report.emissive_blocks == report.blender_lights == 0
    assert manifest["lights"] == []
