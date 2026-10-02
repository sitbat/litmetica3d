"""Verify numerical validity of the actual STL/OBJ bytes written to disk."""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from litmetica3d.conversion import ConversionOptions, convert
from litmetica3d.litematic import BlockState, Region, Schematic


def source():
    return Schematic(6, 3955, regions={
        "R": Region("R", (0, 0, 0), (1, 1, 1), [BlockState("minecraft:stone")],
                    {(0, 0, 0): 0})
    })


@pytest.mark.parametrize("geometry", ["print", "visual"])
@pytest.mark.parametrize("output_format", ["stl", "obj"])
@pytest.mark.parametrize("scale", [1e40, 1e-50])
def test_finite_scale_cannot_export_nonfinite_or_collapsed_mesh(tmp_path, geometry, output_format, scale):
    options = ConversionOptions(
        Path("fixture"), tmp_path / "output" / f"model.{output_format}",
        geometry=geometry, output_format=output_format, scale=scale,
    )
    with patch("litmetica3d.conversion.load_schematic", return_value=source()):
        with pytest.raises(ValueError, match="scale"):
            convert(options)
    assert not options.output_path.parent.exists()


@pytest.mark.parametrize("geometry", ["print", "visual"])
@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("scale", [1e20, 1e-20])
def test_representable_extreme_scale_retains_finite_unit_stl_normals(tmp_path, geometry, binary, scale):
    options = ConversionOptions(Path("fixture"), tmp_path / "scaled.stl", geometry=geometry,
                                stl_binary=binary, scale=scale)
    with patch("litmetica3d.conversion.load_schematic", return_value=source()):
        convert(options)
    if binary:
        records = np.frombuffer(options.output_path.read_bytes()[84:], dtype=np.dtype([
            ("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")
        ]))
        normals = records["normal"]
        vertices = records["vertices"].reshape(-1, 3)
    else:
        lines = [line.split() for line in options.output_path.read_text().splitlines()]
        normals = np.array([list(map(float, line[2:])) for line in lines if line[:2] == ["facet", "normal"]])
        vertices = np.array([list(map(float, line[1:])) for line in lines if line[:1] == ["vertex"]])
    assert np.isfinite(vertices).all()
    assert np.isfinite(normals).all()
    assert np.linalg.norm(normals, axis=1) == pytest.approx(np.ones(len(normals)))
    assert vertices.max() == pytest.approx(scale, rel=1e-6, abs=0)


@pytest.mark.parametrize("geometry", ["print", "visual"])
@pytest.mark.parametrize("scale", [1e-8, 2])
def test_obj_serialization_retains_small_and_normal_scaled_geometry(tmp_path, geometry, scale):
    options = ConversionOptions(Path("fixture"), tmp_path / "scaled.obj", geometry=geometry,
                                output_format="obj", scale=scale)
    with patch("litmetica3d.conversion.load_schematic", return_value=source()):
        convert(options)
    lines = [line.split() for line in options.output_path.read_text().splitlines()]
    vertices = np.array([list(map(float, line[1:])) for line in lines if line[:1] == ["v"]])
    assert np.isfinite(vertices).all()
    assert vertices.min(axis=0) == pytest.approx((0, 0, 0))
    assert vertices.max(axis=0) == pytest.approx((scale, scale, scale), rel=1e-6, abs=0)
    for line in lines:
        if line[:1] != ["f"]:
            continue
        ids = [int(corner.split("/")[0]) - 1 for corner in line[1:]]
        points = vertices[ids[:3]]
        assert np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0])) > 0


@pytest.mark.parametrize("optimize", ["raw", "safe"])
def test_visual_obj_roundtrips_adjacent_float32_coordinates(tmp_path, optimize):
    from litmetica3d.block_models import _cuboid
    from litmetica3d.visual_mesh import CompactVisualMesh, export_compact_obj
    mesh = CompactVisualMesh()
    mesh.add_faces(_cuboid(1_000_000, 0, 0, 1_000_000.125, 1, 1, "test"))
    mesh.flush()
    path = tmp_path / "thin.obj"
    export_compact_obj(mesh, path, optimize=optimize)
    lines = [line.split() for line in path.read_text().splitlines()]
    vertices = np.array([list(map(float, line[1:])) for line in lines if line[:1] == ["v"]])
    # Seven digits wrote both X coordinates as 1000000, collapsing the cuboid.
    assert len(np.unique(vertices[:, 0])) == 2
    actual = {tuple(row) for row in vertices.astype(np.float32)}
    expected = {tuple(row) for chunk in mesh.chunks for row in chunk.vertices.reshape(-1, 3)}
    assert actual == expected
    for line in lines:
        if line[:1] == ["f"]:
            ids = [int(corner.split("/")[0]) - 1 for corner in line[1:4]]
            points = vertices[ids]
            assert np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0])) > 0
