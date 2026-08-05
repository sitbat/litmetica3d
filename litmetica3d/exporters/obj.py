"""
Wavefront OBJ format exporter with MTL material support.

Exports:
  - .obj file: vertices and faces
  - .mtl file: materials with block colors (if --color is enabled)

Reference: https://en.wikipedia.org/wiki/Wavefront_.obj_file
"""

import pathlib
import re
from typing import Callable

from ..mesh import Mesh
from .base import Exporter


# ── Block → representative color mapping ────────────────────────────────────
# Colors chosen to approximate Minecraft's default textures.

BLOCK_COLORS: dict[str, tuple[float, float, float]] = {
    # Stone
    "stone": (0.49, 0.49, 0.49),
    "cobblestone": (0.42, 0.42, 0.42),
    "stone_brick": (0.47, 0.47, 0.47),
    # Dirt
    "dirt": (0.53, 0.37, 0.22),
    "grass_block": (0.44, 0.53, 0.27),
    "podzol": (0.42, 0.33, 0.17),
    # Wood
    "oak_planks": (0.64, 0.51, 0.29),
    "oak_log": (0.55, 0.44, 0.27),
    "spruce_planks": (0.45, 0.34, 0.19),
    "birch_planks": (0.77, 0.71, 0.47),
    # Sand
    "sand": (0.85, 0.80, 0.56),
    "sandstone": (0.82, 0.77, 0.55),
    # Water / Lava
    "water": (0.20, 0.40, 0.90),
    "lava": (0.95, 0.50, 0.10),
    # Glass
    "glass": (0.70, 0.85, 1.00),
    # Ore
    "coal_ore": (0.35, 0.35, 0.35),
    "iron_ore": (0.55, 0.45, 0.40),
    "gold_ore": (0.65, 0.55, 0.25),
    "diamond_ore": (0.40, 0.65, 0.75),
    "emerald_ore": (0.30, 0.60, 0.35),
    # Nether
    "netherrack": (0.55, 0.22, 0.22),
    "nether_brick": (0.28, 0.12, 0.13),
    # End
    "end_stone": (0.84, 0.85, 0.66),
    "obsidian": (0.08, 0.05, 0.13),
    # Misc
    "brick": (0.60, 0.30, 0.22),
    "wool": (0.88, 0.88, 0.88),
    "concrete": (0.75, 0.75, 0.75),
    "terracotta": (0.63, 0.37, 0.23),
    # Redstone
    "redstone_wire": (0.70, 0.05, 0.05),
    "redstone_block": (0.65, 0.05, 0.05),
    "redstone_lamp": (0.50, 0.25, 0.10),
    # Leaves
    "oak_leaves": (0.27, 0.44, 0.13),
    "spruce_leaves": (0.17, 0.33, 0.17),
    # Water plants
    "kelp": (0.16, 0.42, 0.16),
    "seagrass": (0.20, 0.47, 0.20),
}

# Color map for commonly used material names (strip namespace and properties)
_NAMED_COLORS = {
    "white": (0.95, 0.95, 0.95),
    "orange": (0.95, 0.60, 0.20),
    "magenta": (0.80, 0.30, 0.80),
    "light_blue": (0.40, 0.70, 1.00),
    "yellow": (0.95, 0.95, 0.20),
    "lime": (0.40, 0.95, 0.20),
    "pink": (0.95, 0.60, 0.70),
    "gray": (0.35, 0.35, 0.35),
    "light_gray": (0.60, 0.60, 0.60),
    "cyan": (0.20, 0.80, 0.80),
    "purple": (0.60, 0.30, 0.85),
    "blue": (0.20, 0.30, 0.90),
    "brown": (0.50, 0.35, 0.20),
    "green": (0.30, 0.60, 0.20),
    "red": (0.85, 0.20, 0.20),
    "black": (0.10, 0.10, 0.10),
    "copper": (0.82, 0.44, 0.25),
    "iron": (0.70, 0.70, 0.70),
    "gold": (0.90, 0.75, 0.25),
    "diamond": (0.30, 0.70, 0.80),
    "emerald": (0.20, 0.70, 0.30),
    "netherite": (0.25, 0.15, 0.15),
    "quartz": (0.90, 0.88, 0.85),
    "prismarine": (0.30, 0.60, 0.50),
    "tuff": (0.40, 0.38, 0.35),
}


def _resolve_block_color(material: str) -> tuple[float, float, float]:
    """Resolve a material name to an RGB color."""
    # Strip namespace
    name = material
    if ":" in name:
        name = name.split(":")[1]

    # Check exact match
    if name in BLOCK_COLORS:
        return BLOCK_COLORS[name]

    # Check partial matches (e.g. oak_log → oak)
    for color_name, color in BLOCK_COLORS.items():
        if color_name in name or name in color_name:
            return color

    # Check named colors
    for color_name, color in _NAMED_COLORS.items():
        if color_name in name:
            return color

    # Fallback: hash-based deterministic color
    h = hash(name) & 0xFFFFFF
    return ((h >> 16) / 255.0, ((h >> 8) & 0xFF) / 255.0, (h & 0xFF) / 255.0)


class OBJExporter(Exporter):
    """Export mesh to Wavefront OBJ format with optional MTL materials."""

    def __init__(
        self,
        with_colors: bool = True,
        texture_provider: Callable[[str], bytes | None] | None = None,
        alpha_provider: Callable[[str], bytes | None] | None = None,
    ):
        self.with_colors = with_colors
        self.texture_provider = texture_provider
        self.alpha_provider = alpha_provider

    @property
    def extension(self) -> str:
        return "obj"

    def export(self, mesh: Mesh, path: pathlib.Path) -> None:
        obj_path = path
        mtl_path = path.with_suffix(".mtl")
        mtl_name = mtl_path.name

        material_faces: dict[str, list[tuple[int, tuple[int, int, int]]]] = {}
        starts = iter(sorted(mesh.materials))
        next_start = next(starts, None)
        mat = "default"
        for i, tri in enumerate(mesh.triangles):
            while next_start is not None and next_start[0] <= i:
                mat = next_start[1]
                next_start = next(starts, None)
            texture = (
                mesh.triangle_textures[i]
                if i < len(mesh.triangle_textures) else None
            )
            key = f"texture:{texture}" if texture else mat
            material_faces.setdefault(key, []).append((i, tri))

        # Write MTL file if colors requested
        if self.with_colors:
            self._write_mtl(mtl_path, material_faces.keys(), obj_path)

        # Write OBJ file
        self._mesh_uvs = mesh.triangle_uvs
        self._write_obj(obj_path, mtl_name if self.with_colors else None,
                        mesh.vertices, material_faces)

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)

    def _write_mtl(self, path: pathlib.Path, materials, obj_path: pathlib.Path) -> None:
        """Write an MTL file with colors for each material."""
        with open(path, "w", encoding="utf-8") as f:
            f.write("# MTL file generated by litmetica3d\n")
            for mat in sorted(materials):
                texture = mat[len("texture:"):] if mat.startswith("texture:") else None
                r, g, b = (1.0, 1.0, 1.0) if texture else _resolve_block_color(mat)
                safe_name = self._safe_name(mat)
                f.write(f"\nnewmtl {safe_name}\n")
                f.write(f"Kd {r:.4f} {g:.4f} {b:.4f}\n")    # diffuse
                f.write(f"Ka {r:.4f} {g:.4f} {b:.4f}\n")    # ambient
                f.write(f"Ks 0.1 0.1 0.1\n")                 # specular
                f.write(f"Ns 10.0\n")                         # specular exponent
                f.write(f"d 1.0\n")                           # opacity
                if texture and self.texture_provider:
                    raw = self.texture_provider(texture)
                    if raw:
                        texture_dir = obj_path.parent / f"{obj_path.stem}_textures"
                        texture_dir.mkdir(parents=True, exist_ok=True)
                        filename = self._safe_name(texture) + ".png"
                        (texture_dir / filename).write_bytes(raw)
                        f.write(f"map_Kd {texture_dir.name}/{filename}\n")
                        if self.alpha_provider:
                            alpha = self.alpha_provider(texture)
                            if alpha:
                                alpha_name = (
                                    self._safe_name(texture) + "_alpha.png"
                                )
                                (texture_dir / alpha_name).write_bytes(alpha)
                                f.write(
                                    f"map_d {texture_dir.name}/{alpha_name}\n"
                                )

    def _write_obj(self, path: pathlib.Path, mtl_name: str | None,
                   vertices: list, material_faces: dict) -> None:
        """Write an OBJ file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write("# OBJ file generated by litmetica3d\n")
            f.write(f"# Vertices: {len(vertices)}\n")
            f.write(f"# Materials: {len(material_faces)}\n")

            if mtl_name:
                f.write(f"\nmtllib {mtl_name}\n")

            # Write vertices and per-corner texture coordinates.
            for v in vertices:
                f.write(f"v {v.x:.6f} {v.y:.6f} {v.z:.6f}\n")
            uv_indices = {}
            triangle_uv_indices = []
            for tri_uv in getattr(self, "_mesh_uvs", []):
                indices = []
                if tri_uv:
                    for uv in tri_uv:
                        key = (round(uv[0], 8), round(uv[1], 8))
                        if key not in uv_indices:
                            uv_indices[key] = len(uv_indices) + 1
                        indices.append(uv_indices[key])
                triangle_uv_indices.append(indices or None)
            for uv, _index in sorted(uv_indices.items(), key=lambda item: item[1]):
                f.write(f"vt {uv[0]:.8f} {uv[1]:.8f}\n")

            # Write faces grouped by material
            for mat, faces in sorted(material_faces.items()):
                safe_name = self._safe_name(mat)
                if mtl_name:
                    f.write(f"\nusemtl {safe_name}\n")
                f.write(f"g {safe_name}\n")
                for tri_index, (v0, v1, v2) in faces:
                    tuv = triangle_uv_indices[tri_index] if tri_index < len(triangle_uv_indices) else None
                    if tuv:
                        f.write(
                            f"f {v0+1}/{tuv[0]} {v1+1}/{tuv[1]} "
                            f"{v2+1}/{tuv[2]}\n"
                        )
                    else:
                        f.write(f"f {v0+1} {v1+1} {v2+1}\n")
