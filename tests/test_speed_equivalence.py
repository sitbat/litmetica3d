import pathlib
from copy import deepcopy
import numpy as np
from litmetica3d.model_loader import ModelLoader
from litmetica3d.block_models import Face, Vec3, _cuboid
from litmetica3d.visual_mesh import CompactVisualMesh

ASSET = pathlib.Path(__file__).parents[1]/'litmetica3d/mc_assets/26.2.zip'

def test_random_selection_reuses_geometry_not_coordinate():
    cached=ModelLoader(ASSET,visual_textures=True)
    fresh=ModelLoader(ASSET,visual_textures=True)
    try:
        for i in range(200):
            pos=(i-100,i%7,i*3)
            fresh._geometry_cache.clear()
            expected=fresh.resolve('minecraft:stone',{},pos)
            actual=cached.resolve('minecraft:stone',{},pos)
            assert expected == actual
        assert len(cached._geometry_cache)==4
    finally:
        cached.close(); fresh.close()

def test_translation_is_exact_and_does_not_mutate_cached_faces():
    faces=_cuboid(.0125,0,-.125,.9375,1,.8125,'test')
    for f in faces:
        f.uvs=[(0,0),(1,0),(1,1),(0,1)]
    original=deepcopy(faces)
    old,new=CompactVisualMesh(chunk_size=7),CompactVisualMesh(chunk_size=7)
    for pos in ((0,0,0),(-123,17,9),(1000001,-1000001,33)):
        offset=Vec3(*map(float,pos))
        for f in faces:
            old.add_face(Face([v+offset for v in f.vertices],f.normal,f.material,f.uvs,f.texture,f.emission_texture,f.emission_strength))
            new.add_face(f,offset=pos)
    old.flush(); new.flush()
    assert faces==original
    for a,b in zip(old.chunks,new.chunks):
        for key in ('vertices','uvs','materials','textures','emissions','emission_strengths'):
            assert np.array_equal(getattr(a,key),getattr(b,key))
    assert np.array_equal(old.bounds_min,new.bounds_min)
    assert np.array_equal(old.bounds_max,new.bounds_max)
