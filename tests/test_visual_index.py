import io
from pathlib import Path

import numpy as np

from litmetica3d.block_models import Face, Vec3, _cuboid
from litmetica3d.visual_mesh import CompactVisualMesh, export_compact_obj
from litmetica3d.visual_index import rectangle_mask


def read_obj(path):
    vertices, uvs, triangles, polygons = [], [], [], []
    material = None
    for line in path.read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == 'v':
            vertices.append(tuple(map(float, fields[1:])))
        elif fields[0] == 'vt':
            uvs.append(tuple(map(float, fields[1:])))
        elif fields[0] == 'usemtl':
            material = fields[1]
        elif fields[0] == 'f':
            corners = []
            for field in fields[1:]:
                v, t = map(int, field.split('/'))
                corners.append((vertices[v-1], uvs[t-1]))
            polygons.append(corners)
            for i in range(1, len(corners)-1):
                triangles.append((material, (corners[0], corners[i], corners[i+1])))
    return vertices, uvs, triangles, polygons


def expected_triangles(mesh):
    combinations = {}
    output = []
    for chunk in mesh.chunks:
        for v, uv, m, t, e, s in zip(chunk.vertices, chunk.uvs, chunk.materials,
                                     chunk.textures, chunk.emissions, chunk.emission_strengths):
            key = (int(m), int(t), int(e), round(float(s), 5))
            group = combinations.setdefault(key, len(combinations))
            corners = [(tuple(float(f'{n:.7g}') for n in p),
                        tuple(float(f'{n:.7g}') for n in q)) for p, q in zip(v, uv)]
            for ids in ((0,1,2), (0,2,3)):
                output.append((f'visual_{group}', tuple(corners[i] for i in ids)))
    return output


def test_uv_seams_and_materials_are_exact(tmp_path):
    mesh = CompactVisualMesh(chunk_size=7)
    for x in range(5):
        for i, f in enumerate(_cuboid(x, 0, 0, x+1, 1, 1, f'material{x%2}')):
            f.uvs = [(0,0),(0,1),(1,1),(1,0)] if i%2 else [(1,0),(1,1),(0,1),(0,0)]
            mesh.add_face(f)
    mesh.flush()
    path = tmp_path/'indexed.obj'
    stats = export_compact_obj(mesh, path)
    v, uv, triangles, polygons = read_obj(path)
    assert triangles == expected_triangles(mesh)
    assert len(polygons) == mesh.face_count
    assert len(v) < mesh.vertex_count
    assert len(uv) < mesh.vertex_count
    assert stats['exported_vertices'] == len(v)
    assert stats['exported_polygons'] == len(polygons)
    assert 's off' in path.read_text()


def test_rotated_nonplanar_and_distorted_uv_remain_triangles(tmp_path):
    mesh = CompactVisualMesh()
    faces = [
        Face([Vec3(0,0,0),Vec3(1,0,1),Vec3(1,1,1),Vec3(0,1,0)],Vec3(0,0,1),'rotated'),
        Face([Vec3(0,0,0),Vec3(1,0,0),Vec3(1,1,.01),Vec3(0,1,0)],Vec3(0,0,1),'bent'),
        Face([Vec3(0,0,0),Vec3(1,0,0),Vec3(1,1,0),Vec3(0,1,0)],Vec3(0,0,1),'distorted',
             [(0,0),(1,0),(.8,1),(0,1)]),
    ]
    for f in faces:
        mesh.add_face(f)
    mesh.flush()
    path = tmp_path/'special.obj'
    stats = export_compact_obj(mesh,path)
    assert stats['quad_polygons'] == 0
    assert read_obj(path)[2] == expected_triangles(mesh)


def test_nearby_points_not_snapped_and_duplicates_not_deleted(tmp_path):
    mesh = CompactVisualMesh()
    for delta in (0, 0, 0.00125):
        for f in _cuboid(delta,0,0,1+delta,1,1,'glass'):
            mesh.add_face(f)
    mesh.flush()
    path=tmp_path/'overlap.obj'
    export_compact_obj(mesh,path)
    assert read_obj(path)[2] == expected_triangles(mesh)


def test_all_asset_faces_roundtrip(tmp_path):
    from litmetica3d.model_loader import ModelLoader
    assets = Path(__file__).parents[1]/'litmetica3d/mc_assets/26.2'
    loader=ModelLoader(assets, visual_textures=True)
    try:
        mesh=CompactVisualMesh(chunk_size=31)
        for name, props in [
            ('stone', {}), ('grass_block', {'snowy':'false'}),
            ('oak_log', {'axis':'x'}), ('lantern', {'hanging':'true','waterlogged':'false'}),
            ('red_stained_glass', {}), ('glass', {}),
            ('tube_coral_fan', {'waterlogged':'false'}),
            ('short_grass', {}), ('lever', {'face':'wall','facing':'east','powered':'true'}),
        ]:
            result=loader.resolve('minecraft:'+name, props)
            assert result.status == 'ok', name
            for face in result.faces:
                mesh.add_face(face)
        mesh.flush()
        path=tmp_path/'assets.obj'
        export_compact_obj(mesh,path,loader.texture_bytes,loader.texture_alpha_bytes)
        assert read_obj(path)[2] == expected_triangles(mesh)
    finally:
        loader.close()


def test_progress_and_cancel_are_chunked(tmp_path):
    mesh=CompactVisualMesh(chunk_size=1)
    for f in _cuboid(0,0,0,1,1,1,'stone'):
        mesh.add_face(f)
    events=[]
    export_compact_obj(mesh,tmp_path/'progress.obj',progress=lambda p,t:events.append(p))
    assert events == sorted(events) and events[0] == 0 and events[-1] == 1
    assert len(events) == 7
    def cancel(p,t):
        raise InterruptedError('cancel')
    import pytest
    with pytest.raises(InterruptedError):
        export_compact_obj(mesh,tmp_path/'cancel.obj',progress=cancel)
