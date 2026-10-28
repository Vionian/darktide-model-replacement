"""Convert authored RG normals and metallic/gloss maps to native NM/ORM.

The shaded source's material graph explicitly binds *_N to F1_BumpMap and *_P
to F3_MetallicGlossMap. Do not confuse P alpha (gloss) or diffuse alpha (mask)
with generic cloth opacity. No custom face/emissive shader is introduced.
"""
import numpy as np

def authored_settings(proxy):
    from character_material_bridge_user import core
    for material in proxy.data.materials:
        snapshot=core.read_material_column(material)
        if not snapshot:continue
        part,col,width,data=snapshot
        wanted={'_UseBumpMap','_BumpScale','_RoughnessIntensity','_MetallicIntensity',
                '_UseMetallicGlossMap','_Smoothness','_Metallic'}
        return {name:core.read_param(data,width,col,part,name)
                for name in core.param_names(part)if name in wanted}
    return {}

def pixels(image):
    # Data textures must bypass sRGB decoding. Re-reading as Non-Color restores
    # original numeric channels even if the source graph saved another setting.
    image.colorspace_settings.name='Non-Color'
    image.alpha_mode='CHANNEL_PACKED'
    w,h=image.size
    data=np.empty(w*h*4,np.float32);image.pixels.foreach_get(data)
    return data.reshape(h,w,4)

def surface_maps(b,mesh,index):
    mat=mesh.data.materials[index]
    proxy=b.bpy.data.objects.get(mesh.name+'__'+mat.name)
    if not proxy:return {}
    settings=authored_settings(proxy)
    images=[]
    for pm in proxy.data.materials:
        if pm and pm.node_tree:
            images.extend(n.image for n in pm.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
    def find(suffix):
        return next((im for im in images if suffix+'.' in im.name and im.name.startswith('T_actor_') and 'common'not in im.name),None)
    result={}
    # Stylized face/eye normals intentionally stay neutral. Cloth and skin use
    # their own authored maps, never a template model's seams and wrinkles.
    if mat.name.startswith('Cloth') or mat.name in ('肌','面具') or mat.name in getattr(b,'SOURCE_EXTRA_SURFACE_MATERIALS',set()):
        normal=find('_N')
        if normal and settings.get('_UseBumpMap',1)>.5:
            data=pixels(normal).copy();xy=data[:,:,:2]*2-1
            xy*=settings.get('_BumpScale',1)
            # Exported UV V is reversed, hence native tangent B is reversed.
            # Flip the native green channel; the preview undoes this for Blender.
            xy[:,:,1]*=-1
            length=np.linalg.norm(xy,axis=2,keepdims=True)
            xy/=np.maximum(length,1)
            nm=np.ones_like(data);nm[:,:,:2]=xy*.5+.5
            nm[:,:,2]=np.sqrt(np.maximum(0,1-(xy*xy).sum(2)))
            result['nm']=nm
        packed=find('_P')
        if packed and settings.get('_UseMetallicGlossMap',1)>.5:
            data=pixels(packed)
            orm=np.ones_like(data)
            orm[:,:,0]=1 # P.G is not reliably AO in all four source packages.
            orm[:,:,1]=np.clip((1-data[:,:,3])*settings.get('_RoughnessIntensity',1),.22,.94)
            orm[:,:,2]=np.clip(data[:,:,0]*settings.get('_MetallicIntensity',1),0,1)
            result['orm']=orm
        elif settings:
            result['orm']=np.array([[[1,np.clip(1-settings.get('_Smoothness',.3),.22,.94),
                                        settings.get('_Metallic',0),1]]],np.float32)
    if getattr(b,'HAND_AUTHORING_OUTPUT',None):
        import json,pathlib
        folder=pathlib.Path(b.HAND_AUTHORING_OUTPUT)
        file=folder/'surface_materials.json'
        report=json.loads(file.read_text(encoding='utf-8'))if file.exists()else {}
        report[str(index)]={'name':mat.name,'opaque':not b.material_is_alpha(index,mat.name),
            'normal':find('_N').name if 'nm'in result else None,
            'metallic_gloss':find('_P').name if find('_P') and settings.get('_UseMetallicGlossMap',1)>.5 else None,
            'authored_settings':settings,
            'gloss_conversion':'UseMetallicGlossMap: roughness=(1-P.alpha)*roughness_intensity; metallic=P.red*metallic_intensity; otherwise authored uniform values; AO=1'}
        file.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
