"""Bounded-memory OBJ indexing without geometric or material approximation.

Indices are reused within each source chunk, so temporary memory does not grow
with the entire model. UVs have their own indices: texture seams stay intact.
Only axis-aligned rectangles with rectangular/constant UVs become polygons.
Other faces retain exactly the original (0,1,2), (0,2,3) triangles.
"""
from __future__ import annotations

import numpy as np


def _serialized_unique(values):
    unique, inverse = np.unique(values, axis=0, return_inverse=True)
    # Classify using the actual OBJ coordinates, not pre-serialization floats.
    # Keep the same precision as the legacy exporter; never snap nearby points.
    rows = [tuple(format(float(v), '.7g') for v in row) for row in unique]
    exported = np.asarray(rows, dtype=np.float64).reshape(unique.shape)
    return rows, exported, inverse


def rectangle_mask(vertices, uvs):
    edges = np.roll(vertices, -1, axis=1) - vertices
    rectangle = (
        (np.count_nonzero(np.ptp(vertices, axis=1), axis=1) == 2)
        & np.all(np.count_nonzero(edges, axis=2) == 1, axis=1)
        & np.all(edges[:, 0] == -edges[:, 2], axis=1)
        & np.all(edges[:, 1] == -edges[:, 3], axis=1)
    )
    # Paired UV sums are order-independent here; insist on repeated extrema
    # as well, avoiding skewed UVs and any rounding-dependent interpolation.
    low, high = uvs.min(axis=1), uvs.max(axis=1)
    uv_corners = np.all((uvs == low[:, None]) | (uvs == high[:, None]), axis=(1, 2))
    affine = np.all(uvs[:, 0] + uvs[:, 2] == uvs[:, 1] + uvs[:, 3], axis=1)
    return rectangle & uv_corners & affine


def write_indexed_geometry(mesh, stream, combinations, progress=None):
    """Emit surfaces in original order, preserving UV seams and flat shading."""
    stats = dict(
        enabled=True, source_vertices=mesh.vertex_count,
        exported_vertices=0, source_uvs=mesh.vertex_count, exported_uvs=0,
        source_polygons=mesh.triangle_count, exported_polygons=0,
        quad_polygons=0, triangle_polygons=0,
        render_triangles=mesh.triangle_count,
    )
    stream.write('s off\n')
    active = None
    total = max(1, len(mesh.chunks))
    for number, chunk in enumerate(mesh.chunks):
        if progress:
            progress(number / total, f'自动优化视觉模型：区块 {number + 1}/{total}')
        vrows, positions, vi = _serialized_unique(chunk.vertices.reshape(-1, 3))
        trows, coords, ti = _serialized_unique(chunk.uvs.reshape(-1, 2))
        vi, ti = vi.reshape(-1, 4), ti.reshape(-1, 4)
        is_quad = rectangle_mask(positions[vi], coords[ti])
        stream.writelines('v ' + ' '.join(row) + '\n' for row in vrows)
        stream.writelines('vt ' + ' '.join(row) + '\n' for row in trows)
        vertex_base, uv_base = stats['exported_vertices'] + 1, stats['exported_uvs'] + 1
        for i, (material, texture, emission, strength) in enumerate(zip(
            chunk.materials, chunk.textures, chunk.emissions, chunk.emission_strengths,
        )):
            group = combinations[(int(material), int(texture), int(emission), round(float(strength), 5))]
            if group != active:
                stream.write(f'usemtl visual_{group}\n')
                active = group
            corners = [f'{int(v) + vertex_base}/{int(t) + uv_base}' for v, t in zip(vi[i], ti[i])]
            if is_quad[i]:
                stream.write('f ' + ' '.join(corners) + '\n')
            else:
                stream.write(f'f {corners[0]} {corners[1]} {corners[2]}\n')
                stream.write(f'f {corners[0]} {corners[2]} {corners[3]}\n')
        quads = int(is_quad.sum())
        triangles = 2 * (len(chunk.vertices) - quads)
        stats['quad_polygons'] += quads
        stats['triangle_polygons'] += triangles
        stats['exported_polygons'] += quads + triangles
        stats['exported_vertices'] += len(vrows)
        stats['exported_uvs'] += len(trows)
    if progress:
        progress(1.0, '自动优化完成：顶点 '
                 f"{stats['source_vertices']} → {stats['exported_vertices']}，多边形 "
                 f"{stats['source_polygons']} → {stats['exported_polygons']}")
    return stats
