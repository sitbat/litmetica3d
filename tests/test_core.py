import json
import io
import pathlib
import struct
import tempfile
import unittest

from litmetica3d.block_models import Face, Vec3, _cuboid
from litmetica3d.litematic import _read_packed_index
from litmetica3d.model_loader import ModelLoader
from litmetica3d.optimize import optimize_faces
from litmetica3d.entity_models import get_entity_geometry
from litmetica3d.nbt import _read_string


class NBTStringTests(unittest.TestCase):
    @staticmethod
    def decode(raw):
        return _read_string(io.BytesIO(struct.pack(">H", len(raw)) + raw))

    def test_standard_utf8_is_unchanged(self):
        self.assertEqual("投影😀", self.decode("投影😀".encode("utf-8")))

    def test_java_modified_utf8_nul(self):
        self.assertEqual("A\x00B", self.decode(b"A\xc0\x80B"))

    def test_cesu8_surrogate_pair_becomes_unicode_character(self):
        # U+1F600 encoded as Java UTF-16 surrogates D83D DE00.
        self.assertEqual("😀", self.decode(b"\xed\xa0\xbd\xed\xb8\x80"))

    def test_unpaired_surrogate_does_not_abort_schematic(self):
        self.assertEqual("\ufffd", self.decode(b"\xed\xa0\xbd"))


class PackedBitsTests(unittest.TestCase):
    def test_lsb_and_cross_long_boundary(self):
        values = [3, 17, 31, 4, 29, 1, 16, 7, 12, 25, 2, 30, 9, 11]
        bits = 5
        packed = [0, 0]
        for index, value in enumerate(values):
            offset = index * bits
            li, shift = divmod(offset, 64)
            packed[li] |= value << shift
            if shift + bits > 64:
                packed[li + 1] |= value >> (64 - shift)
        decoded = [_read_packed_index(packed, i, bits) for i in range(len(values))]
        self.assertEqual(values, decoded)


class OptimizerTests(unittest.TestCase):
    def test_exact_opposite_faces_cancel(self):
        faces = _cuboid(0, 0, 0, 1, 1, 1, "stone")
        opposite = Face(
            list(reversed(faces[-1].vertices)), Vec3(-1, 0, 0), "stone"
        )
        result = optimize_faces([faces[-1], opposite], "safe")
        self.assertEqual([], result)

    def test_nearby_planes_never_cancel(self):
        one = _cuboid(0, 0, 0, 1, 1, 1, "lever")[-1]
        two = Face(
            [Vec3(v.x + 0.001, v.y, v.z) for v in reversed(one.vertices)],
            Vec3(-1, 0, 0), "lever",
        )
        self.assertEqual(2, len(optimize_faces([one, two], "safe")))

    def test_adjacent_equal_faces_merge(self):
        a = _cuboid(0, 0, 0, 1, 1, 1, "stone")[1]
        b = Face(
            [Vec3(v.x + 1, v.y, v.z) for v in a.vertices],
            a.normal, a.material,
        )
        result = optimize_faces([a, b], "safe")
        self.assertEqual(1, len(result))
        xs = [v.x for v in result[0].vertices]
        self.assertEqual((0, 2), (min(xs), max(xs)))


class ModelFallbackTests(unittest.TestCase):
    def test_unknown_block_and_unknown_state_are_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            path = root / "assets/minecraft/blockstates"
            path.mkdir(parents=True)
            (path / "known.json").write_text(
                json.dumps({"variants": {"facing=north": {"model": "block/x"}}}),
                encoding="utf-8",
            )
            loader = ModelLoader(root)
            try:
                self.assertEqual(
                    "unknown_block",
                    loader.resolve("other:missing", {}).status,
                )
                self.assertEqual(
                    "unknown_state",
                    loader.resolve("minecraft:known", {"facing": "south"}).status,
                )
                self.assertEqual(
                    "missing_model",
                    loader.resolve("minecraft:known", {"facing": "north"}).status,
                )
            finally:
                loader.close()


class EntityModelTests(unittest.TestCase):
    def test_closed_chest_states_have_geometry(self):
        for facing in ("north", "east", "south", "west"):
            for chest_type in ("single", "left", "right"):
                faces = get_entity_geometry(
                    "minecraft:chest",
                    {"facing": facing, "type": chest_type},
                )
                self.assertIsNotNone(faces)
                self.assertGreater(len(faces), 6)

    def test_all_shulker_directions_have_geometry(self):
        for facing in ("up", "down", "north", "south", "east", "west"):
            self.assertTrue(get_entity_geometry(
                "minecraft:red_shulker_box", {"facing": facing}
            ))

    def test_banner_head_and_conduit(self):
        self.assertTrue(get_entity_geometry(
            "minecraft:white_wall_banner", {"facing": "east"}
        ))
        self.assertTrue(get_entity_geometry(
            "minecraft:player_head", {"rotation": "7"}
        ))
        self.assertTrue(get_entity_geometry("minecraft:conduit", {}))

    def test_bubble_column_is_intentionally_invisible(self):
        self.assertEqual(
            [], get_entity_geometry("minecraft:bubble_column", {"drag": "false"})
        )


if __name__ == "__main__":
    unittest.main()
