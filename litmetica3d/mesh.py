"""
Mesh builder — face-per-block approach with optional post-processing.

Each non-air block contributes geometry from Minecraft JSON models
(or a 1×1×1 unit cube as fallback).  When *optimize* is enabled
(the default), a post-processing pass removes overlapping internal
faces and merges adjacent coplanar quads into larger faces.
"""

from dataclasses import dataclass, field

from .block_models import (
    Face,
    Vec3,
    get_block_geometry,
)


# ── Mesh data structure ────────────────────────────────────────────────────

@dataclass
class Mesh:
    """An indexed triangle mesh."""
    vertices: list[Vec3] = field(default_factory=list)
    triangles: list[tuple[int, int, int]] = field(default_factory=list)
    materials: list[tuple[int, str]] = field(default_factory=list)
    triangle_uvs: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]] | None] = field(default_factory=list)
    triangle_textures: list[str | None] = field(default_factory=list)
    _vertex_index: dict[tuple[float, float, float], int] = field(
        default_factory=dict, repr=False
    )

    def add_face(self, face: Face) -> None:
        """Add a quad face as two triangles (v0-v1-v2, v0-v2-v3)."""
        indices = []
        for vertex in face.vertices:
            key = (round(vertex.x, 9), round(vertex.y, 9), round(vertex.z, 9))
            vi = self._vertex_index.get(key)
            if vi is None:
                vi = len(self.vertices)
                self.vertices.append(vertex)
                self._vertex_index[key] = vi
            indices.append(vi)
        if len(indices) != 4:
            return
        self.triangles.append((indices[0], indices[1], indices[2]))
        self.triangles.append((indices[0], indices[2], indices[3]))
        self.materials.append((len(self.triangles) - 2, face.material))
        if face.uvs and len(face.uvs) == 4:
            self.triangle_uvs.extend([
                (face.uvs[0], face.uvs[1], face.uvs[2]),
                (face.uvs[0], face.uvs[2], face.uvs[3]),
            ])
        else:
            self.triangle_uvs.extend([None, None])
        self.triangle_textures.extend([face.texture, face.texture])

    @property
    def triangle_count(self) -> int:
        return len(self.triangles)


# ── Main mesh builder ───────────────────────────────────────────────────────

def build_mesh_from_blocks(
    blocks: dict[tuple[int, int, int], tuple[str, dict[str, str]]],
    *,
    optimize: bool = True,
) -> Mesh:
    """
    Build a Mesh from (x, y, z) → (block_name, properties).

    Parameters
    ----------
    blocks:
        Mapping from block coordinates to (name, properties) tuples.
    optimize:
        When True (default), run post-processing to remove overlapping
        internal faces and merge adjacent coplanar quads.  Disable with
        ``--no-optimize`` for raw per-block geometry.
    """
    # ── 1. Collect every face in world space ────────────────────────────
    all_faces: list[Face] = []

    for pos, (block_name, properties) in blocks.items():
        faces = get_block_geometry(block_name, properties)
        if not faces:
            continue

        px, py, pz = float(pos[0]), float(pos[1]), float(pos[2])
        for face in faces:
            translated = Face(
                vertices=[v + Vec3(px, py, pz) for v in face.vertices],
                normal=face.normal,
                material=face.material,
                uvs=face.uvs,
                texture=face.texture,
            )
            all_faces.append(translated)

    # ── 2. Post-process (pure geometry) ─────────────────────────────────
    if optimize:
        from .optimize import optimize_faces
        all_faces = optimize_faces(all_faces)

    # ── 3. Build the final mesh ─────────────────────────────────────────
    mesh = Mesh()
    for face in all_faces:
        mesh.add_face(face)

    return mesh
