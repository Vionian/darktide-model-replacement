"""Add a closed under-fur surface; the source tail consists mostly of cards.

Original mesh, UVs, normals and skin weights are retained. The underlayer is
lofted along the source tail chain, coloured from its existing fur texture.
"""
import math
import bpy,bmesh
import numpy as np
from mathutils import Vector

def prepare(builder,mesh,armature):
    if mesh.get('roshia_tail_core'):return
    bones=sorted((b for b in armature.data.bones if b.name.startswith('tail_base_')),
                 key=lambda b:len(b.parent_recursive))
    if len(bones)<4:raise ValueError('Tail source chain is missing')
    mesh.data.calc_loop_triangles()
    original_normals=[n.vector.copy() for n in mesh.data.corner_normals]
    original_loops=len(mesh.data.loops)
    group_names={g.index:g.name for g in mesh.vertex_groups}
    tail_weight=np.array([sum(g.weight for g in v.groups if group_names[g.group].startswith('tail_base_'))for v in mesh.data.vertices])
    points=np.array([v.co[:]for v in mesh.data.vertices])
    samples=[];colors=[]
    tail_image=None
    for mat_index,mat in enumerate(mesh.data.materials):
        if mat.name!='发Alpha':continue
        triangles=[t for t in mesh.data.loop_triangles if t.material_index==mat_index and min(tail_weight[list(t.vertices)])>.5]
        tail_image=builder.image_pixels_for(mat)
        for triangle in triangles:
            triangle_uv=np.array([mesh.data.uv_layers.active.data[l].uv[:] for l in triangle.loops])
            rgba=builder.sample_image(tail_image,triangle_uv)
            for corner,vertex_index in enumerate(triangle.vertices):
                if rgba[corner,3]>.7:
                    samples.append(points[vertex_index]);colors.append(rgba[corner,:3])
    samples=np.asarray(samples);colors=np.asarray(colors)
    if len(samples)<50:raise ValueError('Tail fur colour samples are missing')
    warm_mask=((colors[:,0]>colors[:,1]*1.04)
               &(colors[:,1]>colors[:,2]*1.025)
               &(colors[:,0]<.90))
    if np.count_nonzero(warm_mask)<50:
        warm_mask=(colors[:,0]-colors[:,2]>.015)&(colors[:,0]<.80)
    fur_samples=samples[warm_mask]
    fur_colors=colors[warm_mask]
    # Some original exports use a neutral/white hair atlas for the tail and
    # rely on the material tint at runtime. Preserve those authored samples
    # instead of failing the build or inventing a brown tint.
    if len(fur_samples)<50:
        fur_samples=samples
        fur_colors=colors
    if len(fur_samples)<50:raise ValueError('Tail fur colour samples are missing from the source atlas')
    to_mesh=mesh.matrix_world.inverted()@armature.matrix_world
    centers=[to_mesh@b.head_local for b in bones]+[to_mesh@bones[-1].tail_local]
    centers=np.array(centers)
    # Keep the authored source centreline. Only a small root penetration and
    # smooth tip drop are applied, and the exact profile is reused by the
    # dynamic helper pivots in build_roshia_native.py.
    coordinate_inverse=builder.source_coordinate3().to_3x3().inverted()
    mesh_inverse=mesh.matrix_world.inverted().to_3x3()
    tail_root=centers[0].copy()
    centers=tail_root+(centers-tail_root)*builder.TAIL_CHAIN_SCALE
    for i in range(len(centers)):
        t=i/max(1,len(centers)-1)
        target_offset=builder.tail_target_offset(t)
        source_offset=coordinate_inverse@target_offset
        centers[i]+=np.asarray(mesh_inverse@source_offset)
    nearest=np.linalg.norm(samples[:,None]-centers[None,:],axis=2).argmin(axis=1)
    radii=[]
    for i,center in enumerate(centers):
        tangent=centers[min(i+1,len(centers)-1)]-centers[max(0,i-1)]
        tangent/=np.linalg.norm(tangent)
        offsets=samples[np.abs(nearest-i)<=1]-center
        radial=offsets-np.outer(offsets@tangent,tangent)
        radius=np.quantile(np.linalg.norm(radial,axis=1),.40) if len(radial) else .025
        radii.append(float(np.clip(radius,.012,.075)))
    radii=np.convolve(np.pad(radii,(1,1),mode='edge'),[.25,.5,.25],mode='valid')
    # Preserve the broad root silhouette from the authored fur cards while
    # keeping a tapered, animatable end cap.
    radii=np.clip(radii*.84,.016,.090)
    radii[0]=max(radii[0],.028);radii[-1]=max(.016,min(radii[-1],.024))
    # A denser ring keeps the closed core round at the root while leaving
    # enough angular resolution for the layered plume shading below.
    segments=96
    ring_points=[];ring_colors=[]
    for i,center in enumerate(centers):
        t=i/max(1,len(centers)-1)
        tangent=centers[min(i+1,len(centers)-1)]-centers[max(0,i-1)]
        tangent/=np.linalg.norm(tangent)
        x=np.array([1.,0,0]);x-=tangent*np.dot(x,tangent);x/=np.linalg.norm(x)
        y=np.cross(tangent,x)
        fan=1+.20*math.sin(math.pi*(.25+.75*t))
        for j in range(segments):
            theta=j/segments*2*math.pi
            # Longitudinal clumps make the core read as a groomed tail rather
            # than a uniformly shaded tube. The variation is bounded so the
            # root still follows the authored body attachment.
            layer_phase=2*math.pi*(t*8.0)+theta*1.35
            fur_edge=(1+.12*math.sin(theta*9+i*.72)
                      +.05*math.sin(theta*17-i*.39)
                      +.022*math.sin(theta*29+i*.25)
                      +.035*math.sin(layer_phase))
            point=center+radii[i]*fur_edge*(x*(fan*1.05*math.cos(theta))
                                             +y*(.72*math.sin(theta)))
            ring_points.append(point)
            distance=np.linalg.norm(fur_samples-point,axis=1)
            nearest_count=min(10,len(distance))
            nearest_indices=np.argpartition(distance,nearest_count-1)[:nearest_count]
            weights=1/np.maximum(distance[nearest_indices],.002)**2
            ring_colors.append(np.average(fur_colors[nearest_indices],axis=0,weights=weights))
    source_tex=np.asarray(ring_colors).reshape(len(centers),segments,3)
    height,width=2048,1024
    u=np.arange(width,dtype=np.float32)/width*segments
    v=np.linspace(0,len(centers)-1,height,dtype=np.float32)
    u0=np.floor(u).astype(int)%segments;u1=(u0+1)%segments;tu=(u-u0)[:,None]
    v0=np.floor(v).astype(int);v1=np.minimum(v0+1,len(centers)-1);tv=(v-v0)[:,None,None]
    low=source_tex[v0[:,None],u0[None,:]]*(1-tu[None,:,:])+source_tex[v0[:,None],u1[None,:]]*tu[None,:,:]
    high=source_tex[v1[:,None],u0[None,:]]*(1-tu[None,:,:])+source_tex[v1[:,None],u1[None,:]]*tu[None,:,:]
    tex=low*(1-tv)+high*tv
    uv=np.arange(width,dtype=np.float32)[None,:]/width
    longitudinal=np.arange(height,dtype=np.float32)[:,None]/height
    strand_count=96
    strand_phase=(uv*strand_count
                  +.22*np.sin(longitudinal*2*math.pi*3+uv*2*math.pi*5)
                  +.08*np.sin(longitudinal*2*math.pi*11-uv*2*math.pi*9))
    fraction=strand_phase-np.floor(strand_phase)
    line_id=np.floor(strand_phase).astype(np.int32)%strand_count
    rng=np.random.default_rng(7319)
    line_value=rng.uniform(-.25,.25,strand_count).astype(np.float32)[line_id]
    highlight=np.exp(-((fraction-.70)/.12)**2)
    groove=np.exp(-((fraction-.27)/.13)**2)
    broad_shade=.72+.28*np.sin(longitudinal*2*math.pi*1.35+np.sin(uv*2*math.pi*3)*.55)
    # Repeated soft bands approximate the layered feather/fur clumps visible
    # on the reference Lolita tail without borrowing its garment geometry.
    layer_bands=.90+.16*np.sin(longitudinal*2*math.pi*8.0+uv*2*math.pi*1.7)
    fine_noise=.018*np.sin(uv*2*math.pi*211+longitudinal*2*math.pi*23)
    strands=1+line_value*(highlight+groove)+.26*highlight-.24*groove+fine_noise
    # Preserve the sampled warm fur colour and add enough strand contrast for
    # the native diffuse shader; the previous dark multiplier made the core
    # read as a flat brown strip in-game.
    tex=np.clip((tex-.06)*1.22+.06,0,1)
    root_shade=.70+.30*longitudinal
    tex=np.clip(tex*strands[:,:,None]*broad_shade[:,:,None]*layer_bands[:,:,None]
                *root_shade[:,:,None]*np.array([1.02,.90,.74])*.92,0,1)
    rgba=np.ones((height,width,4),np.float32)
    rgba[:,:,:3]=np.where(tex<=.0031308,tex*12.92,1.055*np.maximum(tex,0)**(1/2.4)-.055)
    image=bpy.data.images.new('RoshiaTailCore_D.png',width=width,height=height,alpha=True)
    image.colorspace_settings.name='sRGB';image.pixels.foreach_set(rgba.ravel());image.update()
    material=bpy.data.materials.new('RoshiaTailCore');material.use_nodes=True
    node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
    mesh.data.materials.append(material);material_index=len(mesh.data.materials)-1
    bm=bmesh.new();bm.from_mesh(mesh.data)
    deform=bm.verts.layers.deform.verify();uv_layer=bm.loops.layers.uv.verify()
    added=[]
    for i,p in enumerate(ring_points):
        v=bm.verts.new(p);bone=bones[min(i//segments,len(bones)-1)]
        v[deform][mesh.vertex_groups[bone.name].index]=1.;added.append(v)
    for i in range(len(centers)-1):
        for j in range(segments):
            # x cross y points along the chain; outward winding on the tube.
            ids=[i*segments+j,i*segments+(j+1)%segments,(i+1)*segments+(j+1)%segments,(i+1)*segments+j]
            face=bm.faces.new([added[k] for k in ids]);face.material_index=material_index;face.smooth=True
            for loop,uv in zip(face.loops,[(j/segments,i/(len(centers)-1)),((j+1)/segments,i/(len(centers)-1)),((j+1)/segments,(i+1)/(len(centers)-1)),(j/segments,(i+1)/(len(centers)-1))]):loop[uv_layer].uv=uv
    for end_ring,ids in ((0,list(reversed(range(segments)))),
                         (len(centers)-1,list(range((len(centers)-1)*segments,len(centers)*segments)))):
        face=bm.faces.new([added[k]for k in ids]);face.material_index=material_index
        for loop,vertex_index in zip(face.loops,ids):
            loop[uv_layer].uv=((vertex_index%segments)/segments,end_ring/(len(centers)-1))
    bm.to_mesh(mesh.data);bm.free();mesh.data.update()
    normals=original_normals+[n.vector.copy()for n in mesh.data.corner_normals][original_loops:]
    mesh.data.normals_split_custom_set(normals)
    mesh['roshia_tail_core']=True
    print('TAIL_CLOSED_CORE',{'vertices':len(added),'rings':len(centers),'radial_segments':segments,'radius_minmax':[float(min(radii)),float(max(radii))],'sample_count':len(samples),'warm_fur_samples':len(fur_samples),'length_scale':builder.TAIL_CHAIN_SCALE,'root_offset':tuple(float(v) for v in builder.TAIL_ROOT_OFFSET),'tip_offset':tuple(float(v) for v in builder.TAIL_TIP_OFFSET),'texture_strands':strand_count,'texture_size':[width,height]})
