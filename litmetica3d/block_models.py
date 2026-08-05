"""
Block geometry lookup engine.

Simple approach: every non-air block renders as a 1×1×1 full cube.
Each of the 6 faces is an independent quad — matching Minecraft's
face-based rendering model.

When a ModelLoader is initialized (via init_model_loader), block
geometry is sourced from Minecraft's JSON asset files instead,
giving pixel-perfect non-full-block shapes.
"""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model_loader import ModelLoader


# ── Data types ──────────────────────────────────────────────────────────────

@dataclass
class Vec3:
    """A 3D vector / point."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)


@dataclass
class Face:
    """A quadrilateral face in 3D space."""
    vertices: list[Vec3]   # 4 corners, CCW from outside
    normal: Vec3           # outward-facing normal
    material: str          # block name (for coloring)
    uvs: list[tuple[float, float]] | None = None
    texture: str | None = None
    emission_texture: str | None = None
    emission_strength: float = 0.0


# ── Block sets ──────────────────────────────────────────────────────────────

AIR_BLOCKS = {
    "minecraft:air",
    "minecraft:cave_air",
    "minecraft:void_air",
    "minecraft:structure_void",
}


# ── Model loader (optional) ────────────────────────────────────────────────

_loader: "ModelLoader | None" = None


def init_model_loader(jar_path: str) -> "ModelLoader":
    """Initialize the Minecraft asset model loader from a version JAR."""
    global _loader
    from .model_loader import ModelLoader
    _loader = ModelLoader(jar_path)
    return _loader


# ── Unit cube geometry ──────────────────────────────────────────────────────

def _cuboid(x1: float, y1: float, z1: float,
            x2: float, y2: float, z2: float,
            material: str = "unknown") -> list[Face]:
    """
    Generate 6 independent quads for an axis-aligned cuboid.

    Vertex winding is CCW when viewed from outside the cube
    (right-hand rule: cross(v1→v2, v2→v3) = outward normal).
    """
    v = [
        Vec3(x1, y1, z1),  # v0: bottom-front-left
        Vec3(x2, y1, z1),  # v1: bottom-front-right
        Vec3(x2, y1, z2),  # v2: bottom-back-right
        Vec3(x1, y1, z2),  # v3: bottom-back-left
        Vec3(x1, y2, z1),  # v4: top-front-left
        Vec3(x2, y2, z1),  # v5: top-front-right
        Vec3(x2, y2, z2),  # v6: top-back-right
        Vec3(x1, y2, z2),  # v7: top-back-left
    ]

    return [
        Face([v[0], v[1], v[2], v[3]], Vec3(0, -1, 0), material),   # Bottom
        Face([v[4], v[7], v[6], v[5]], Vec3(0, 1, 0), material),    # Top
        Face([v[0], v[4], v[5], v[1]], Vec3(0, 0, -1), material),   # Front (-Z)
        Face([v[3], v[2], v[6], v[7]], Vec3(0, 0, 1), material),    # Back (+Z)
        Face([v[0], v[3], v[7], v[4]], Vec3(-1, 0, 0), material),   # Left (-X)
        Face([v[1], v[5], v[6], v[2]], Vec3(1, 0, 0), material),    # Right (+X)
    ]


# ── Public API ──────────────────────────────────────────────────────────────

def get_block_geometry(
    block_name: str,
    properties: dict[str, str] | None = None,
) -> list[Face]:
    """
    Return the 3D geometry for a block.

    Resolution order:
      1. AIR → empty list
      2. ModelLoader (if available) → pixel-accurate from Minecraft JSON
      3. Fallback → 1×1×1 unit cube
    """
    if block_name in AIR_BLOCKS:
        return []

    if properties is None:
        properties = {}

    # Sentinel: force full-cube or partial-height cube geometry.
    # "__force_cube__": "true"  →  full 1×1×1 cube
    # "__force_cube__": "0.5"   →  cuboid from y=0 to y=0.5
    force_cube = properties.get("__force_cube__")
    if force_cube:
        if force_cube == "true":
            return _cuboid(0.0, 0.0, 0.0, 1.0, 1.0, 1.0, block_name)
        else:
            try:
                h = float(force_cube)
                return _cuboid(0.0, 0.0, 0.0, 1.0, max(h, 0.001), 1.0, block_name)
            except ValueError:
                return _cuboid(0.0, 0.0, 0.0, 1.0, 1.0, 1.0, block_name)

    # Try JSON model from Minecraft assets
    if _loader is not None:
        faces = _loader.get_faces(block_name, properties)
        if faces is not None and len(faces) > 0:
            return faces

    # Fallback: full 1×1×1 cube
    return _cuboid(0.0, 0.0, 0.0, 1.0, 1.0, 1.0, block_name)
