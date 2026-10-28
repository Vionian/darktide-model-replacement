"""Offline framing preview using compiled units/textures, not a game screenshot."""
import pathlib,sys,json,struct,subprocess,math
import bpy,numpy as np
from mathutils import Vector,Matrix
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import build_roshia_native as b
from read_native_texture import read_native_top_mip
from roshia_native_materials import read_pbr_fill
from package_share_variants import ENDFIELD
OUT=b.ROOT/'tools/model-work/distribution_fix/portraits'
OUT.mkdir(exist_ok=True)
bounds=json.loads((OUT.parent/'portrait_bounds.json').read_text())
oodle=b.Oodle(b.OODLE_DLL)

def texture(folder,path,linear=False):
    png=OUT/'decoded'/path.with_suffix('.png').name
    if not png.exists():
        png.parent.mkdir(exist_ok=True)
        dds=png.with_suffix('.dds');dds.write_bytes(read_native_top_mip(path,oodle)[0])
        result=subprocess.run([str(b.ROOT/'tools/texconv.exe'),'-nologo','-y','-ft','png','-f',
            'R8G8B8A8_UNORM' if linear else 'R8G8B8A8_UNORM_SRGB','-o',str(png.parent),str(dds)],capture_output=True)
        assert result.returncode==0,result.stdout+result.stderr
    im=bpy.data.images.load(str(png),check_existing=True)
    im.colorspace_settings.name='Non-Color' if linear else 'sRGB'
    return im

for key in ENDFIELD:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    folder=b.ROOT/'Custom'/key
    b.unit_dt.load_stream_dt=lambda p:b.StreamReader(b.Cursor(str(folder/pathlib.Path(p))))
    u=b.unit_dt.UnitResourceDT(b.Cursor(str(folder/(key+'.unit'))))
    material_names={struct.unpack_from('<Q',p.read_bytes(),8)[0]:p.stem for p in folder.glob('*.material')}
    slot_names={slot.ID:material_names[mat.ID] for slot,mat in u.materials}
    materials={};vertices=[];normals=[];faces=[];uv=[];face_mats=[]
    for g in u.mesh_geometries:
        p=np.frombuffer(g.streams[1].vertex_data,dtype='<f2').reshape((-1,4))[:,:3].astype(float)
        indices=np.frombuffer(g.index_stream.data,dtype='<u2').astype(np.int32).reshape((-1,3))
        keep=(p[indices,2].max(1)>=bounds[key]['head_world'][2][3]-.23)
        indices=indices[keep]
        if not len(indices):continue
        name=slot_names[g.materials[0].ID]
        if name not in materials:
            mat=bpy.data.materials.new(name);mat.use_nodes=True;mat.use_backface_culling=True
            bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.85
            bsdf.inputs['Specular IOR Level'].default_value=.12
            diffuse=next(folder.glob(name+'_bc*.texture'))
            tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=texture(folder,diffuse)
            mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
            if diffuse.stem.endswith('_bca'):
                mat.surface_render_method='DITHERED';mat.node_tree.links.new(tex.outputs['Alpha'],bsdf.inputs['Alpha'])
            em=folder/(name+'_em.texture')
            if em.exists():
                emtex=mat.node_tree.nodes.new('ShaderNodeTexImage');emtex.image=texture(folder,em,True)
                mat.node_tree.links.new(emtex.outputs['Color'],bsdf.inputs['Emission Color'])
                fill=read_pbr_fill(folder,name)
                bsdf.inputs['Emission Strength'].default_value=fill['intensity']*fill['multiplier']
            materials[name]=mat
        off=len(vertices);vertices.extend(p.tolist());faces.extend((indices+off).tolist())
        normals.extend(b.mesh_geometry.math_utils.octahedral_decode(g.streams[2].vertex_data).tolist())
        coords=np.frombuffer(g.streams[3].vertex_data,dtype='<f2').reshape((-1,2)).astype(float);coords[:,1]=1-coords[:,1];uv.extend(coords.tolist())
        face_mats.extend([list(materials).index(name)]*len(indices))
    mesh=bpy.data.meshes.new(key);mesh.from_pydata(vertices,[],faces);mesh.update()
    mesh.normals_split_custom_set_from_vertices(normals)
    layer=mesh.uv_layers.new()
    for loop in mesh.loops:layer.data[loop.index].uv=uv[loop.vertex_index]
    for mat in materials.values():mesh.materials.append(mat)
    for poly,index in zip(mesh.polygons,face_mats):poly.material_index=index;poly.use_smooth=True
    obj=bpy.data.objects.new(key,mesh);bpy.context.collection.objects.link(obj)
    # Same head-relative bounds and 80% frame occupancy as the runtime fitter.
    head=Matrix(bounds[key]['head_world']);rotation=head.to_quaternion()
    pts=np.asarray([head.translation+rotation@Vector((x,y,z)) for x in (bounds[key]['min'][0],bounds[key]['max'][0])
         for y in (bounds[key]['min'][1],bounds[key]['max'][1]) for z in (bounds[key]['min'][2],bounds[key]['max'][2])])
    low=pts.min(0);high=pts.max(0);center=(low+high)/2
    fov=math.radians(35);ty=math.tan(fov/2)*.8;tx=ty*.875
    # Front is +Y; camera forward points -Y, so closest corner has the highest Y.
    dist=max(max(abs(p[0]-center[0])/tx,abs(p[2]-center[2])/ty)+(p[1]-center[1]) for p in pts)
    camdata=bpy.data.cameras.new('portrait');camdata.type='PERSP';camdata.lens=32/math.tan(fov/2)/2
    camdata.sensor_fit='VERTICAL';camdata.sensor_height=32
    cam=bpy.data.objects.new('portrait',camdata);bpy.context.collection.objects.link(cam)
    cam.location=Vector((center[0],center[1]+dist,center[2]));cam.rotation_euler=(Vector(center)-cam.location).to_track_quat('-Z','Y').to_euler()
    scene=bpy.context.scene;scene.camera=cam
    scene.render.engine='CYCLES';scene.cycles.samples=12
    scene.render.resolution_x=280;scene.render.resolution_y=320;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('portrait world');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.23,.25,.29,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
    for name,offset,power in [('key',(-.5,.8,.8),65),('fill',(.6,.7,.2),30)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=1.0
        light=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(light);light.location=Vector(center)+Vector(offset)
        light.rotation_euler=(Vector(center)-light.location).to_track_quat('-Z','Y').to_euler()
    scene.view_settings.view_transform='Standard';scene.view_settings.exposure=.2
    scene.render.filepath=str(OUT/(key+'.png'));bpy.ops.render.render(write_still=True)
    print('PORTRAIT_RENDERED',key,flush=True)
