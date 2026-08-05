"""
STL (STereoLithography) format exporter.

Supports both binary and ASCII STL formats.
Binary is recommended for all practical use (much smaller files).

Reference: https://en.wikipedia.org/wiki/STL_(file_format)
"""

import pathlib
import struct

from ..mesh import Mesh, Vec3
from .base import Exporter


class STLExporter(Exporter):
    """Export mesh to STL format."""

    def __init__(self, binary: bool = True):
        self.binary = binary

    @property
    def extension(self) -> str:
        return "stl"

    def export(self, mesh: Mesh, path: pathlib.Path) -> None:
        if self.binary:
            self._export_binary(mesh, path)
        else:
            self._export_ascii(mesh, path)

    # ── Binary STL ──────────────────────────────────────────────────────

    def _export_binary(self, mesh: Mesh, path: pathlib.Path) -> None:
        """
        Binary STL format:
          - 80-byte header (UINT8[80])
          - 4-byte triangle count (UINT32 LE)
          - For each triangle:
            - Normal: 3× FLOAT32 LE (12 bytes)
            - Vertex 1: 3× FLOAT32 LE (12 bytes)
            - Vertex 2: 3× FLOAT32 LE (12 bytes)
            - Vertex 3: 3× FLOAT32 LE (12 bytes)
            - Attribute byte count: UINT16 LE (2 bytes)
          = 50 bytes per triangle
        """
        with open(path, "wb") as f:
            # Header (80 bytes)
            header = b"Binary STL exported by litmetica3d" + b"\x00" * 46
            f.write(header[:80])

            # Triangle count
            num_triangles = mesh.triangle_count
            f.write(struct.pack("<I", num_triangles))

            # Write each triangle
            for ti in range(0, len(mesh.triangles)):
                vi0, vi1, vi2 = mesh.triangles[ti]
                v0 = mesh.vertices[vi0]
                v1 = mesh.vertices[vi1]
                v2 = mesh.vertices[vi2]

                # Compute face normal
                edge1 = Vec3(v1.x - v0.x, v1.y - v0.y, v1.z - v0.z)
                edge2 = Vec3(v2.x - v0.x, v2.y - v0.y, v2.z - v0.z)
                normal = _cross(edge1, edge2)
                # Normalize
                length = (normal.x**2 + normal.y**2 + normal.z**2) ** 0.5
                if length > 0:
                    normal = Vec3(normal.x / length, normal.y / length, normal.z / length)

                # Normal (3 floats)
                f.write(struct.pack("<fff", normal.x, normal.y, normal.z))
                # Vertex 1
                f.write(struct.pack("<fff", v0.x, v0.y, v0.z))
                # Vertex 2
                f.write(struct.pack("<fff", v1.x, v1.y, v1.z))
                # Vertex 3
                f.write(struct.pack("<fff", v2.x, v2.y, v2.z))
                # Attribute byte count
                f.write(struct.pack("<H", 0))

    # ── ASCII STL ───────────────────────────────────────────────────────

    def _export_ascii(self, mesh: Mesh, path: pathlib.Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"solid litmetica3d_export\n")

            for ti in range(0, len(mesh.triangles)):
                vi0, vi1, vi2 = mesh.triangles[ti]
                v0 = mesh.vertices[vi0]
                v1 = mesh.vertices[vi1]
                v2 = mesh.vertices[vi2]

                edge1 = Vec3(v1.x - v0.x, v1.y - v0.y, v1.z - v0.z)
                edge2 = Vec3(v2.x - v0.x, v2.y - v0.y, v2.z - v0.z)
                normal = _cross(edge1, edge2)
                length = (normal.x**2 + normal.y**2 + normal.z**2) ** 0.5
                if length > 0:
                    normal = Vec3(normal.x / length, normal.y / length, normal.z / length)

                f.write(f"  facet normal {normal.x:.6e} {normal.y:.6e} {normal.z:.6e}\n")
                f.write(f"    outer loop\n")
                f.write(f"      vertex {v0.x:.6e} {v0.y:.6e} {v0.z:.6e}\n")
                f.write(f"      vertex {v1.x:.6e} {v1.y:.6e} {v1.z:.6e}\n")
                f.write(f"      vertex {v2.x:.6e} {v2.y:.6e} {v2.z:.6e}\n")
                f.write(f"    endloop\n")
                f.write(f"  endfacet\n")

            f.write(f"endsolid litmetica3d_export\n")


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return Vec3(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x,
    )
