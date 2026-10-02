"""Numerically stable transforms and checks for float32 export geometry."""

from __future__ import annotations

import numpy as np


def transform_vertices(vertices, scale, offset=(0.0, 0.0, 0.0)):
    # Perform arithmetic before float32 conversion: converting an otherwise
    # finite scale to float32 first can itself overflow or underflow.
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        result = ((vertices.astype(np.float64) + offset) * scale).astype(np.float32)
    if not np.isfinite(result).all():
        raise ValueError("scale 或模型坐标超出导出网格的有限数值范围")
    return result


def triangle_normals(points):
    """Normalize in float64 so valid large/small float32 meshes keep normals."""
    points = np.asarray(points, dtype=np.float64)
    normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    nonzero = lengths > 0
    normals[nonzero] /= lengths[nonzero, None]
    return normals


def validate_export_geometry(vertices, triangles=None, batch_size=65536):
    """Reject nonfinite coordinates and collapsed triangles before any writes.

    Indexed vertices use ``triangles``; otherwise vertices are batches of
    quadrilaterals with the exporter's fixed (0,1,2), (0,2,3) triangulation.
    Float64 cross products avoid misclassifying small valid geometry as zero.
    """
    if not np.isfinite(vertices).all():
        raise ValueError("scale 或模型坐标超出导出网格的有限数值范围")
    count = len(triangles) if triangles is not None else len(vertices)
    for start in range(0, count, batch_size):
        if triangles is not None:
            batches = (vertices[triangles[start:start + batch_size]],)
        else:
            quads = vertices[start:start + batch_size]
            batches = (quads[:, (0, 1, 2)], quads[:, (0, 2, 3)])
        for points in batches:
            points = points.astype(np.float64)
            cross = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
            if np.any(np.all(cross == 0, axis=1)):
                raise ValueError("scale 或模型精度导致导出三角形退化，请调整缩放比例")
