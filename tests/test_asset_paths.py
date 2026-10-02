"""ZIP entry separators must not depend on the OS reading bundled assets."""
import io
import json
from unittest.mock import patch
import zipfile

from PIL import Image
import pytest

from litmetica3d.conversion import bundled_asset_path
from litmetica3d.model_loader import ModelLoader


def assets():
    image = io.BytesIO()
    Image.new("RGBA", (16, 16), (100, 50, 20, 255)).save(image, format="PNG")
    return {
        "assets/minecraft/blockstates/test.json": json.dumps({
            "variants": {"": {"model": "minecraft:block/test"}},
        }).encode(),
        "assets/minecraft/models/block/test.json": json.dumps({
            "textures": {"test": "minecraft:block/test"},
            "elements": [{
                "from": [0, 0, 0], "to": [16, 16, 16],
                "faces": {direction: {"texture": "#test"} for direction in
                          ("down", "up", "north", "south", "west", "east")},
            }],
        }).encode(),
        "assets/minecraft/textures/block/test.png": image.getvalue(),
        "assets/minecraft/textures/block/test.png.mcmeta": b'{"animation": {"frametime": 2}}',
    }


@pytest.mark.parametrize("source", ["directory", "slash_zip", "backslash_zip"])
def test_directory_and_zip_resolve_models_textures_and_metadata(tmp_path, source):
    entries = assets()
    path = tmp_path / "assets-source"
    # Emulate Linux's ZipInfo separator behavior even when this test runs on
    # Windows. Only ZIP parsing consults this value; no files are extracted.
    with patch("zipfile.os.sep", "/"):
        if source == "directory":
            for name, data in entries.items():
                destination = path / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
        else:
            separator = "\\" if source == "backslash_zip" else "/"
            with zipfile.ZipFile(path, "w") as archive:
                for name, data in entries.items():
                    archive.writestr(name.replace("/", separator), data)
        loader = ModelLoader(path, visual_textures=True)
        try:
            assert loader.block_count == 1
            assert loader.has_blockstate("minecraft:test")
            result = loader.resolve("minecraft:test", {})
            assert result.status == "ok", result.detail
            assert len(result.faces) == 6
            assert all(face.texture == "minecraft:block/test" for face in result.faces)
            image = Image.open(io.BytesIO(loader.texture_bytes("minecraft:block/test")))
            assert image.getpixel((0, 0)) == (100, 50, 20, 255)
            assert loader._animation_metadata("minecraft:block/test") == {"frametime": 2}
        finally:
            loader.close()


def test_bundled_archive_resolves_with_posix_zip_parsing():
    with patch("zipfile.os.sep", "/"):
        loader = ModelLoader(bundled_asset_path(), visual_textures=True)
        try:
            assert loader.block_count >= 1100
            assert loader.resolve("minecraft:stone", {}).status == "ok"
            assert loader.resolve("minecraft:glowstone", {}).status == "ok"
            assert loader.texture_bytes("minecraft:block/stone")
        finally:
            loader.close()
