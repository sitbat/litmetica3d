"""Numerical regression cases for cavity fill and Minecraft model transforms."""

import json
import math

import manifold3d as m3d
import numpy as np
import pytest
from PIL import Image

from litmetica3d.model_loader import ModelLoader
from litmetica3d.solid import (
    SolidReport, manifold_from_closed_faces, process_components_and_cavities,
)


@pytest.mark.parametrize("components", ["keep", "remove-small", "main"])
def test_filling_nested_cavities_removes_internal_positive_shells(components):
    # Two nested hollow components and an inner island; a separate outside
    # cube verifies that bounding-box filtering cannot replace a true union.
    shell = m3d.Manifold.cube((10, 10, 10)) - m3d.Manifold.cube((8, 8, 8)).translate((1, 1, 1))
    inner = m3d.Manifold.cube((4, 4, 4)).translate((3, 3, 3)) - m3d.Manifold.cube((2, 2, 2)).translate((4, 4, 4))
    island = m3d.Manifold.cube().translate((4.5, 4.5, 4.5))
    outside = m3d.Manifold.cube().translate((12, 0, 0))
    source = shell + inner + island + outside
    report = SolidReport()
    result, vertices, triangles = process_components_and_cavities(
        source, cavities="fill", components=components,
        min_component_volume=0, report=report, return_mesh=True,
    )
    expected = 1000 if components == "main" else 1001
    assert result.volume() == pytest.approx(expected)
    assert report.volume_after_cavity_fill == pytest.approx(expected)
    assert report.retained_component_count == (1 if components == "main" else 2)
    assert len(result.decompose()) == report.retained_component_count
    # Check the exported arrays as well as the lazy boolean object.
    exported = m3d.Manifold(m3d.Mesh(vertices.copy(), triangles.copy()))
    assert exported.volume() == pytest.approx(expected)
    assert len(exported.decompose()) == report.retained_component_count


def test_fill_cavity_with_unit_island_reports_actual_added_volume():
    shell = m3d.Manifold.cube((10, 10, 10)) - m3d.Manifold.cube((8, 8, 8)).translate((1, 1, 1))
    source = shell + m3d.Manifold.cube().translate((4, 4, 4))
    report = SolidReport()
    result = process_components_and_cavities(
        source, cavities="fill", components="keep",
        min_component_volume=0, report=report,
    )
    assert report.volume_before_cavity_fill == pytest.approx(489)
    assert report.filled_cavity_volume == pytest.approx(511)
    assert result.surface_area() == pytest.approx(600)


def model(element):
    return {"textures": {"test": "minecraft:block/test"}, "elements": [element]}


def cube_element():
    return {
        "from": [0, 0, 0], "to": [16, 16, 16],
        "faces": {direction: {"texture": "#test", "uv": [0, 0, 16, 16]}
                  for direction in ("down", "up", "north", "south", "west", "east")},
    }


@pytest.mark.parametrize("axis", ["x", "y", "z"])
@pytest.mark.parametrize("angle", [-45, -22.5, 22.5, 45])
def test_element_rescale_volume_and_normals(tmp_path, axis, angle):
    loader = ModelLoader(tmp_path)
    elem = cube_element()
    elem["rotation"] = {"axis": axis, "angle": angle, "origin": [4, 6, 10], "rescale": True}
    faces = loader._model_to_faces(model(elem), "test", closed=True, rot_y=90)
    solid = manifold_from_closed_faces(faces)
    # A rescaled rotation expands two dimensions by sec(angle).
    assert solid.volume() == pytest.approx(1 / math.cos(math.radians(angle)) ** 2, rel=1e-6)
    for face in faces:
        normal = np.array((face.normal.x, face.normal.y, face.normal.z))
        points = np.array([(v.x, v.y, v.z) for v in face.vertices])
        assert np.linalg.norm(normal) == pytest.approx(1)
        assert np.dot(normal, points[1] - points[0]) == pytest.approx(0, abs=1e-9)
        assert np.dot(normal, points[3] - points[0]) == pytest.approx(0, abs=1e-9)
    elem["rotation"]["rescale"] = False
    unscaled = loader._model_to_faces(model(elem), "test", closed=True)
    assert manifold_from_closed_faces(unscaled).volume() == pytest.approx(1, rel=1e-6)


def test_rescale_uses_declared_origin_and_retains_axis_coordinates(tmp_path):
    loader = ModelLoader(tmp_path, minimum_thickness=0)
    elem = {
        "from": [4, 0, 10], "to": [20, 16, 10],
        "rotation": {"axis": "y", "angle": 45, "origin": [4, 0, 10], "rescale": True},
        "faces": {"south": {"texture": "#test"}},
    }
    faces = loader._model_to_faces(model(elem), "test")
    points = np.array([(v.x, v.y, v.z) for f in faces for v in f.vertices])
    assert points.min(axis=0) == pytest.approx((0.25, 0, -0.375))
    assert points.max(axis=0) == pytest.approx((1.25, 1, 0.625))


def world_uv(vertex, normal):
    x, y, z = vertex.x, vertex.y, vertex.z
    direction = (round(normal.x), round(normal.y), round(normal.z))
    return {
        (0, -1, 0): (x, z), (0, 1, 0): (x, 1 - z),
        (0, 0, -1): (1 - x, y), (0, 0, 1): (x, y),
        (-1, 0, 0): (z, y), (1, 0, 0): (1 - z, y),
    }[direction]


@pytest.mark.parametrize("rot_x", [0, 90, 180, 270])
@pytest.mark.parametrize("rot_y", [0, 90, 180, 270])
def test_locked_cube_uvs_stay_aligned_to_world_axes(tmp_path, rot_x, rot_y):
    loader = ModelLoader(tmp_path, visual_textures=True)
    faces = loader._model_to_faces(model(cube_element()), "test", rot_x, rot_y, uvlock=True)
    for face in faces:
        for vertex, uv in zip(face.vertices, face.uvs):
            assert uv == pytest.approx(world_uv(vertex, face.normal))


def test_uvlock_preserves_custom_rectangle_and_face_rotation(tmp_path):
    loader = ModelLoader(tmp_path, visual_textures=True)
    elem = cube_element()
    elem["faces"] = {"up": {"texture": "#test", "uv": [2, 3, 10, 7], "rotation": 90}}
    unlocked = loader._model_to_faces(model(elem), "test", rot_y=90)[0]
    locked = loader._model_to_faces(model(elem), "test", rot_y=90, uvlock=True)[0]
    assert locked.vertices == unlocked.vertices
    assert np.array(unlocked.uvs) == pytest.approx(np.array([
        (2 / 16, 9 / 16), (10 / 16, 9 / 16), (10 / 16, 13 / 16), (2 / 16, 13 / 16),
    ]))
    assert np.array(locked.uvs) == pytest.approx(np.array([
        (9 / 16, 14 / 16), (9 / 16, 6 / 16), (13 / 16, 6 / 16), (13 / 16, 14 / 16),
    ]))


def test_variant_uvlock_reaches_loader_and_does_not_mutate_cached_model(tmp_path):
    models = tmp_path / "assets/minecraft/models/block"
    blockstates = tmp_path / "assets/minecraft/blockstates"
    models.mkdir(parents=True)
    blockstates.mkdir(parents=True)
    original = model(cube_element())
    (models / "test.json").write_text(json.dumps(original))
    (blockstates / "test.json").write_text(json.dumps({"variants": {
        "locked=true": {"model": "minecraft:block/test", "y": 90, "uvlock": True},
        "locked=false": {"model": "minecraft:block/test", "y": 90},
    }}))
    loader = ModelLoader(tmp_path, visual_textures=True)
    locked = loader.resolve("minecraft:test", {"locked": "true"})
    unlocked = loader.resolve("minecraft:test", {"locked": "false"})
    assert locked.status == unlocked.status == "ok"
    assert locked.faces[1].uvs != unlocked.faces[1].uvs
    assert loader._load_model("minecraft:block/test") == original


@pytest.mark.parametrize("thickness", [0, 16])
def test_uvlock_applies_before_transparent_pixel_extrusion(tmp_path, thickness):
    textures = tmp_path / "assets/minecraft/textures/block"
    textures.mkdir(parents=True)
    image = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    image.putpixel((0, 0), (255, 255, 255, 255))
    image.save(textures / "test.png")
    loader = ModelLoader(tmp_path, visual_textures=True)
    elem = {
        "from": [0, 0, 0], "to": [16, thickness, 16],
        "faces": {"up": {"texture": "#test", "uv": [0, 0, 16, 16]}},
    }
    faces = loader._model_to_faces(model(elem), "test", rot_y=90, uvlock=True)
    points = [(v.x, v.z) for f in faces for v in f.vertices]
    # The opaque north-west quarter stays north-west after a locked rotation.
    assert np.min(points, axis=0) == pytest.approx((0, 0), abs=1e-9)
    assert np.max(points, axis=0) == pytest.approx((0.5, 0.5), abs=1e-9)


def test_rescale_also_applies_to_pixel_extrusions(tmp_path):
    textures = tmp_path / "assets/minecraft/textures/block"
    textures.mkdir(parents=True)
    Image.new("RGBA", (2, 2), (255, 255, 255, 255)).save(textures / "test.png")
    loader = ModelLoader(tmp_path, visual_textures=True)
    elem = {
        "from": [0, 0, 8], "to": [16, 16, 8],
        "rotation": {"axis": "y", "angle": 45, "origin": [8, 8, 8], "rescale": True},
        "faces": {"south": {"texture": "#test", "uv": [0, 0, 16, 16]}},
    }
    faces = loader._model_to_faces(model(elem), "test")
    points = np.array([(v.x, v.y, v.z) for f in faces for v in f.vertices])
    # One-pixel thickness adds half a pixel beyond each end after rescaling.
    assert points.min(axis=0) == pytest.approx((-1 / 32, 0, -1 / 32))
    assert points.max(axis=0) == pytest.approx((33 / 32, 1, 33 / 32))
