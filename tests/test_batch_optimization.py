import io
from collections import Counter
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from litmetica3d.block_models import Face, Vec3, _cuboid
from litmetica3d.visual_mesh import CompactVisualMesh, export_compact_obj
from litmetica3d.conversion import ConversionOptions, convert
from litmetica3d.litematic import Schematic, Region, BlockState

def test_batch_matches_single_faces_and_chunk_boundaries():
    faces=_cuboid(-.03125,0,0,1,1,1,'stone') * 9
    faces.insert(3,Face([Vec3(float('nan'),0,0)]*4,Vec3(0,1,0),'invalid'))
    faces.insert(8,Face([Vec3(0,0,0)]*3,Vec3(0,1,0),'triangle'))
    a,b=CompactVisualMesh(chunk_size=7),CompactVisualMesh(chunk_size=7)
    for face in faces:
        a.add_face(face,offset=(-9876543.0,5.0,9.0))
    b.add_faces(faces,offset=(-9876543.0,5.0,9.0))
    assert a.face_count==b.face_count==54
    assert a.material_names==b.material_names==['stone']
    a.flush(); b.flush()
    assert len(a.chunks)==len(b.chunks)
    for x,y in zip(a.chunks,b.chunks):
        for name in ('vertices','uvs','materials','textures','emissions','emission_strengths'):
            assert np.array_equal(getattr(x,name),getattr(y,name))
        assert len(y.vertices)<=7
    assert np.array_equal(a.bounds_min,b.bounds_min)
    assert np.array_equal(a.bounds_max,b.bounds_max)

def test_texture_encoding_once_per_texture_preserves_all_materials(tmp_path):
    calls=Counter()
    def image(kind):
        def provide(name):
            calls[(kind,name)]+=1
            output=io.BytesIO()
            Image.new('RGBA',(2,2),(10,200,40,127)).save(output,format='PNG')
            return output.getvalue()
        return provide
    mesh=CompactVisualMesh()
    for level in range(1,9):
        faces=_cuboid(level,0,0,level+1,1,1,'stone')
        for f in faces:
            f.texture='test:shared'
            f.emission_texture='test:emission'
            f.emission_strength=level
        mesh.add_faces(faces)
    export_compact_obj(mesh,tmp_path/'model.obj',image('color'),image('alpha'),image('emission'))
    assert all(v==1 for v in calls.values())
    mtl=(tmp_path/'model.mtl').read_text()
    assert mtl.count('newmtl ')==8
    assert mtl.count('map_Kd ')==mtl.count('map_d ')==mtl.count('map_Ke ')==8

def test_non_emissive_skips_profiles_but_explicit_emission_is_not_skipped(tmp_path):
    schematic=Schematic(6,0,regions={'r':Region('r',(0,0,0),(1,1,1),[BlockState('minecraft:stone')],{(0,0,0):0})})
    options=ConversionOptions(Path('fixture'),tmp_path/'model.obj',
        asset_path=Path(__file__).parents[1]/'litmetica3d/mc_assets/26.2.zip',
        output_format='obj',geometry='visual',blender_lights='material')
    with patch('litmetica3d.conversion.load_schematic',return_value=schematic), \
         patch('litmetica3d.conversion.emission_profile',return_value=None) as profile:
        convert(options)
        profile.assert_not_called()
    from litmetica3d.model_loader import ModelResult
    faces=_cuboid(0,0,0,1,1,1,'minecraft:stone')
    faces[0].texture='minecraft:block/stone'
    faces[0].emission_strength=4
    with patch('litmetica3d.conversion.load_schematic',return_value=schematic), \
         patch('litmetica3d.model_loader.ModelLoader.resolve',return_value=ModelResult(tuple(faces))), \
         patch('litmetica3d.conversion.emission_profile',return_value=None) as profile:
        convert(options)
        assert profile.call_count==6

def test_colliding_texture_filenames_preserve_legacy_last_write(tmp_path):
    mesh=CompactVisualMesh()
    calls=[]
    def provide(name):
        calls.append(name)
        buf=io.BytesIO()
        Image.new('RGBA',(1,1),(255,0,0,255) if name=='test:a/b' else (0,255,0,255)).save(buf,format='PNG')
        return buf.getvalue()
    for strength, texture in enumerate(('test:a/b','test:a_b','test:a/b')):
        faces=_cuboid(strength,0,0,strength+1,1,1,'test')
        for f in faces:
            f.texture=texture
            f.emission_strength=strength
        mesh.add_faces(faces)
    export_compact_obj(mesh,tmp_path/'model.obj',provide)
    assert calls==['test:a/b','test:a_b','test:a/b']
    with Image.open(tmp_path/'model_textures/test_a_b.png') as im:
        assert im.getpixel((0,0))==(255,0,0,255)
