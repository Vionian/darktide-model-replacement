import argparse
import importlib.util
import math
import pathlib
import sys
import json

import bpy
import numpy as np
from mathutils import Matrix, Vector


ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILDER_PATH = ROOT / "tools" / "model-work" / "build_roshia_native.py"
sys.path.insert(0,str(BUILDER_PATH.parent))
OUT = ROOT / "tools" / "model-work" / "roshia" / "first_build"

spec = importlib.util.spec_from_file_location("roshia_builder", BUILDER_PATH)
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)

parser = argparse.ArgumentParser()
from endfield_profiles import PROFILES as ENDFIELD_PROFILES
parser.add_argument("--model-profile", choices=tuple(ENDFIELD_PROFILES))
parser.add_argument("--source-blend", type=pathlib.Path, default=builder.SOURCE_BLEND)
parser.add_argument("--template-dir", type=pathlib.Path, default=builder.TEMPLATE)
parser.add_argument("--output-dir", type=pathlib.Path, default=OUT)
parser.add_argument("--mesh-object", default=builder.MESH_OBJECT_NAME)
parser.add_argument("--armature-object", default=builder.ARMATURE_OBJECT_NAME)
parser.add_argument("--asset-prefix", default="roshia")
parser.add_argument("--translation-only", action="store_true")
parser.add_argument("--matrix-targets", default="")
parser.add_argument("--hand-retarget-mode", choices=("rigid", "legacy", "coherent"), default="rigid")
parser.add_argument("--focus-hands", action="store_true")
parser.add_argument("--individual-hands", action="store_true")
parser.add_argument('--hands-only',action='store_true',help='Diagnostic render mask after compiled-resource verification; exported assets are unchanged')
parser.add_argument("--first-person", action="store_true")
parser.add_argument("--hide-cloak-blades", action="store_true")
parser.add_argument("--binding-mode", choices=("animation-compatible", "source-rigid", "proportion-fk"), default=builder.BINDING_MODE)
parser.add_argument("--raw-dds-uv", action="store_true", help="Diagnostic only: omit the exported-texture-to-Blender V conversion")
parser.add_argument("--focus-region", choices=("face", "upper-body", "tail", "right-arm", "legs"), help="Frame details of the compiled mesh without modifying it")
parser.add_argument("--diagnostic-solid", action="store_true", help="Show actual mesh silhouette without source texture transparency or shading")
parser.add_argument('--views',nargs='+',choices=('front','side','back','three-quarter'),help='Render only the named views')
parser.add_argument('--lighting-scale',type=float,default=1.0,help='Scale preview lights only; never modifies exported materials')
parser.add_argument('--save-scene',type=pathlib.Path,help='Save the first fully configured view for repeatable material diagnostics')
parser.add_argument('--tail-core-only',action='store_true',help='Diagnostic: show only the compiled opaque tail core, without its outer fur cards')
parser.add_argument("--asset-dir", type=pathlib.Path, help="Built asset directory: verify geometry against .unit and use its exported textures")
parser.add_argument('--runtime-pose',type=pathlib.Path,help='World matrices exported by executing the actual runtime Lua')
parser.add_argument('--serialized-geometry',action='store_true',help='Render actual serialized streams after a verified surface-only patch; do not assert a fresh builder byte match')
parser.add_argument('--skin-profile',help='Recovered outfit profile; use the exact native builder configuration')
parser.add_argument('--camera-elevation',type=float,help='Camera elevation in degrees for underside/backface inspection')
parser.add_argument('--weapon-proxy',action='store_true',help='Show a diagnostic grip rod at the native right-hand contact')
parser.add_argument("--pose", choices=("serialized-rest", "linked-rest", "flex", "grip", "idle"), default="serialized-rest",
                    help="Reconstruct runtime TRS and skin the actual compiled mesh; flex is a synthetic joint stress pose")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
if args.model_profile:
    from endfield_profiles import apply
    apply(builder, args.model_profile)
    args.source_blend=builder.SOURCE_BLEND
    args.mesh_object=builder.MESH_OBJECT_NAME
    args.armature_object=builder.ARMATURE_OBJECT_NAME
    args.asset_prefix=args.model_profile + ('_arms' if args.first_person else '')
    builder.OUTPUT=args.output_dir
if args.asset_dir:
    if args.skin_profile:
        from build_new_skin import configure
        configure(builder,args.skin_profile)
        args.source_blend=builder.SOURCE_BLEND
        args.mesh_object=builder.MESH_OBJECT_NAME
        args.armature_object=builder.ARMATURE_OBJECT_NAME
        args.asset_prefix=args.skin_profile + ('_arms' if args.first_person else '')
    args.asset_dir = args.asset_dir.resolve()
builder.SOURCE_BLEND = args.source_blend.resolve()
builder.TEMPLATE = args.template_dir.resolve()
builder.MESH_OBJECT_NAME = args.mesh_object
builder.ARMATURE_OBJECT_NAME = args.armature_object
builder.BINDING_MODE = args.binding_mode
OUT = args.output_dir.resolve()
OUT.mkdir(parents=True, exist_ok=True)
translation_only = args.translation_only
hand_retarget_mode = "rigid"
matrix_targets = [target for target in args.matrix_targets.split(",") if target]
focus_hands = args.focus_hands
individual_hands = args.individual_hands
arm_only = args.first_person
mode_name = "translation" if translation_only else "matrix"
mode_name += "_hand_" + hand_retarget_mode
if args.hide_cloak_blades:
    mode_name += "_no_cloak_blades"
if matrix_targets:
    mode_name += "_selected"
if arm_only:
    mode_name += "_first_person"

# When validating a compiled unit, use its serialized native textures below.
# Source diffuse images may be unavailable in the original blend, but geometry
# collection only carries this temporary image payload; it does not affect the
# compiled-resource comparison or preview material assignment.
bpy.ops.wm.open_mainfile(filepath=str(builder.SOURCE_BLEND))
unit = builder.load_target_unit()
template_bones = builder.BonesResourceDT(
    builder.Cursor(str(builder.TEMPLATE / "qianxia_bones.bones"))
)
node_by_name = builder.named_node_map(unit, template_bones)
mesh = bpy.data.objects[builder.MESH_OBJECT_NAME]
armature = bpy.data.objects[builder.ARMATURE_OBJECT_NAME]
builder.prepare_source(mesh,armature)
if args.asset_dir:
    # Source preparation can generate geometry from real atlas samples (the
    # opaque Roshia tail). White placeholders are safe only after that stage.
    builder.image_pixels_for = lambda _material: (1, 1, np.ones((1, 1, 4), dtype=np.float32), True)
skin = unit.skins[0]
palette_by_node = {node_index: palette for palette, node_index in enumerate(skin.node_indices)}
dynamic_rig = builder.dynamic_rig_mapping(mesh, armature, unit, node_by_name)
if args.binding_mode == 'proportion-fk':
    from roshia_proportion_rig import adapt
    dynamic_rig = adapt(builder, unit, node_by_name, dynamic_rig, arm_only)
if dynamic_rig.get('runtime_fk',{}).get('shoulder_supports') and args.pose!='serialized-rest' and not args.runtime_pose:
    raise ValueError('Shoulder supports require --runtime-pose for animated previews; export actual Lua output with test_roshia_contacts.py')
bone_targets = builder.source_bone_targets(
    armature, node_by_name, dynamic_rig.get("source_to_target")
)
bone_targets.update(dynamic_rig['source_to_target'])
bind_transforms = builder.target_bind_transforms(
    armature, node_by_name, unit,
    translation_only=translation_only,
    matrix_targets=matrix_targets,
)
bind_transforms.update(dynamic_rig["bind_transforms"])
bind_transforms.update(dynamic_rig.get("geometry_bind_transforms", {}))
target_by_palette = {
    palette_by_node[node_by_name[name]]: name for name in bind_transforms
}
_, _, _, builder_positions, _ = builder.vertex_influences(
    mesh, bone_targets, palette_by_node, node_by_name, target_by_palette, bind_transforms,
    source_bind_transforms=dynamic_rig["hand_rig"]["source_transforms"],
)
np.save(OUT / "roshia_builder_retargeted_positions.npy", builder_positions)
inspector_path = OUT / "roshia_inspector_retargeted_positions.npy"
if inspector_path.exists():
    inspector_positions = np.load(inspector_path)
    delta = np.linalg.norm(builder_positions - inspector_positions, axis=1)
    print("RETARGET_DIFF " + str({
        "vertices": len(delta),
        "max": float(delta.max()),
        "mean": float(delta.mean()),
        "p95": float(np.quantile(delta, 0.95)),
        "different_over_001": int(np.count_nonzero(delta > 0.01)),
    }))
if args.serialized_geometry:
    if not args.asset_dir:raise ValueError('--serialized-geometry requires --asset-dir')
    import re
    from native_garment_sides import from_parsed
    built_unit=builder.unit_dt.UnitResourceDT(builder.Cursor(str(args.asset_dir/(args.asset_prefix+'.unit'))))
    manifest=json.loads((args.asset_dir/'build.json').read_text(encoding='utf-8'))
    resources={builder.hash64(a['resource']['name']):a['resource']['name'] for a in manifest['artifacts']
               if a['resource']['type']=='material' and a['role']=='primary'}
    slots={s.ID:r.ID for s,r in built_unit.materials}
    geometries=[from_parsed(builder,g,int(re.search(r'_material_(\d+)$',resources[slots[g.materials[0].ID]]).group(1)))
                for g in built_unit.mesh_geometries]
    print('PREVIEW_ACTUAL_SERIALIZED_STREAMS',len(geometries))
else:
    geometries, _ = builder.build_geometry_chunks(
        mesh, armature, unit, node_by_name, arm_only, args.asset_prefix,
        [builder.IDString32.from_str(f"{args.asset_prefix}_slot_{index:02d}").ID for index in range(builder.GEO_COUNT)],
        translation_only=translation_only,
        matrix_targets=matrix_targets,
        hand_retarget_mode=hand_retarget_mode,
        dynamic_rig=dynamic_rig,
        hide_cloak_blades=args.hide_cloak_blades,
    )
if args.asset_dir and not args.serialized_geometry:
    built_unit = builder.unit_dt.UnitResourceDT(builder.Cursor(str(args.asset_dir / (args.asset_prefix + ".unit"))))
    if len(built_unit.mesh_geometries) != len(geometries):
        raise ValueError("Preview geometry count differs from compiled unit")
    for parsed, expected in zip(built_unit.mesh_geometries, geometries):
        if any(stream.vertex_data != payload for stream, (payload, _) in zip(parsed.streams, expected["streams"])):
            raise ValueError("Preview geometry differs from compiled unit")
        if parsed.index_stream.data != expected["index_data"]:
            raise ValueError("Preview indices differ from compiled unit")
    print("PREVIEW_UNIT_GEOMETRY_MATCH")


def scaled_pose_delta(delta, gain, thumb=False):
    from mathutils import Quaternion

    def scaled(rotation):
        if rotation.w < 0:
            rotation = Quaternion((-rotation.w, -rotation.x, -rotation.y, -rotation.z))
        axis, angle = rotation.to_axis_angle()
        angle += max(0.0, angle - math.radians(15.0)) * (gain - 1.0)
        return Quaternion(axis, angle)

    if thumb:
        length = math.hypot(delta.z, delta.w)
        if length < 1e-7:
            return scaled(delta)
        twist = Quaternion((delta.w / length, 0.0, 0.0, delta.z / length))
        swing = delta @ twist.inverted()
        return swing @ scaled(twist)
    return scaled(delta)

vertices = []
faces = []
colors = []
uvs = []
normals = []
joint_indices = []
joint_weights = []
face_materials = []
for geometry in geometries:
    positions = builder.geometry_positions(geometry)
    # Stream 0 stores tangent/negative-bitangent octahedral pairs, not colors.
    rgba = np.ones((len(positions), 4), dtype=np.float32)
    texcoords = np.frombuffer(geometry["streams"][3][0], dtype="<f2").reshape((-1, 2)).astype(np.float32)
    # Both source-PNG and compiled-texture previews consume make_geometry's
    # DDS-oriented UV stream. Convert it back exactly once in either mode.
    if not args.raw_dds_uv:
        texcoords[:, 1] = 1.0 - texcoords[:, 1]
    normal_data = geometry["streams"][2][0]
    joint_data = np.frombuffer(geometry["streams"][5][0], dtype=np.uint8).reshape((-1, 4))
    weight_data = np.frombuffer(geometry["streams"][4][0], dtype="<f2").reshape((-1, 4))
    decoded_normals = builder.mesh_geometry.math_utils.octahedral_decode(normal_data).astype(np.float32)
    offset = len(vertices)
    vertices.extend(positions.astype(np.float32).tolist())
    colors.extend(rgba.astype(np.float32).tolist())
    uvs.extend(texcoords.astype(np.float32).tolist())
    normals.extend(decoded_normals.tolist())
    joint_indices.extend(joint_data.tolist())
    joint_weights.extend(weight_data.astype(np.float32).tolist())
    faces.extend(np.arange(offset, offset + len(positions), dtype=np.int32).reshape((-1, 3)).tolist())
    face_materials.extend([geometry["material_index"]] * (len(positions) // 3))

if args.tail_core_only:
    core_materials={i for i,m in enumerate(mesh.data.materials) if m.name=='RoshiaTailCore'}
    visible=[(face,material) for face,material in zip(faces,face_materials) if material in core_materials]
    if not visible:
        raise ValueError('Compiled mesh has no solid tail core')
    faces,face_materials=map(list,zip(*visible))
    mode_name+='_solid_tail_diagnostic'

if args.asset_dir:
    # Never trust the cached world matrix alone: the engine evaluates local TRS.
    # This reproduces the old serialization fault that a static mesh render hid.
    pose_worlds = {}
    runtime_data=json.loads(args.runtime_pose.read_text()) if args.runtime_pose else None
    if runtime_data:
        pose_worlds={i:Matrix(m) for i,m in enumerate(runtime_data['worlds'])}
    visiting = set()
    flex_angles = {"j_leftforearm": 25, "j_rightforearm": -25,
                   "j_leftfoot": 12, "j_rightfoot": -12, "j_head": 10}
    built_names = {index: name for name, index in node_by_name.items()}

    def pose_world(index):
        if index in pose_worlds:
            return pose_worlds[index]
        if index in visiting:
            raise ValueError("Serialized rig contains a parent cycle")
        visiting.add(index)
        node = built_unit.scene_graph.nodes[index]
        if args.pose == "linked-rest" and args.binding_mode != 'proportion-fk' and built_names.get(index, "").startswith("j_"):
            # Simulate native node-name animation linking to the reference rig.
            pose_worlds[index] = unit.scene_graph.nodes[index].world_transform.copy()
            visiting.remove(index)
            return pose_worlds[index]
        local = node.local_transform.copy()
        if args.pose == 'idle':
            name = built_names.get(index, '')
            if name in ('j_leftarm', 'j_rightarm'):
                parent_world = pose_world(node.parent_index)
                current = parent_world @ local
                child_index = node_by_name['j_leftforearm' if name == 'j_leftarm' else 'j_rightforearm']
                child_local = built_unit.scene_graph.nodes[child_index].local_transform.translation
                axis = current.to_3x3() @ child_local
                target = Vector((-0.18 if name == 'j_leftarm' else 0.18, 0.06, -1)).normalized()
                rotated = axis.normalized().rotation_difference(target).to_matrix() @ current.to_3x3()
                current_rotation = (parent_world.to_3x3().inverted() @ rotated).to_4x4()
                current_rotation.translation = local.translation
                local = current_rotation
        if args.pose == "flex" and built_names.get(index) in flex_angles:
            local = local @ Matrix.Rotation(np.radians(flex_angles[built_names[index]]), 4, "Z")
        if args.pose == "grip":
            name = built_names.get(index, "")
            grip_angle = None
            if "inhand" not in name and any(f"hand{finger}" in name for finger in ("index", "middle", "ring", "pinky")):
                grip_angle = 40 if name.endswith("1") else 55
            elif "handthumb" in name:
                grip_angle = 25
            if grip_angle is not None:
                if args.binding_mode == 'proportion-fk':
                    from mathutils import Quaternion
                    record = next(d for d in dynamic_rig['runtime_fk']['bones'] if d['name'] == name)
                    delta = Matrix.Rotation(np.radians(grip_angle), 4, "Z")
                    def qmatrix(key):
                        x,y,z,w = record[key]
                        return Quaternion((w,x,y,z)).to_matrix().to_4x4()
                    post = qmatrix('rotation_post')
                    delta = post.inverted() @ delta @ post
                    if arm_only:
                        gain = record.get('curl_gain', 1.0)
                        delta = scaled_pose_delta(delta.to_quaternion(), gain,
                                                 thumb="handthumb" in name).to_matrix().to_4x4()
                    rotated = qmatrix('rest_rotation') @ delta
                    rotated.translation = local.translation
                    local = rotated
                else:
                    local = local @ Matrix.Rotation(np.radians(grip_angle), 4, 'Z')
        world = (pose_world(node.parent_index) @ local
                 if node.parent_type == builder.ParentType.INTERNAL else local)
        pose_worlds[index] = world
        visiting.remove(index)
        return world

    skin_matrices = np.asarray([
        pose_world(node_index) @ inverse
        for node_index, inverse in zip(built_unit.skins[0].node_indices,
                                       built_unit.skins[0].inv_bind_matrices)
    ], dtype=np.float32)
    weights = np.asarray(joint_weights, dtype=np.float32)
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-8)
    blended = (skin_matrices[np.asarray(joint_indices)] * weights[:, :, None, None]).sum(axis=1)
    original = np.asarray(vertices, dtype=np.float32)
    posed = np.einsum("nij,nj->ni", blended[:, :3, :3], original) + blended[:, :3, 3]
    delta = np.linalg.norm(posed - original, axis=1)
    print("SERIALIZED_TRS_SKIN " + str({"pose": runtime_data.get('case','runtime') if runtime_data else args.pose, "max_vertex_delta": float(delta.max()),
                                        "mean_vertex_delta": float(delta.mean())}))
    vertices = posed.tolist()
    normals_array = np.asarray(normals, dtype=np.float32)
    normal_transforms=np.linalg.inv(blended[:, :3, :3]).transpose(0,2,1)
    normals = np.einsum("nij,nj->ni", normal_transforms, normals_array)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-8)
    normals = normals.tolist()
    if args.pose != "serialized-rest":
        mode_name += "_" + args.pose

if individual_hands:
    hand_joint_positions = []
    patched_hands = {
        record["name"]: record["world"].translation
        for record in dynamic_rig["hand_node_transforms"].values()
    }
    for side in ("left", "right"):
        names = [f"j_{side}hand"]
        names.extend(f"j_{side}handthumb{index}" for index in (1, 2, 3))
        for finger in ("index", "middle", "ring", "pinky"):
            names.extend(f"j_{side}hand{finger}{index}" for index in (1, 2, 3))
        hand_joint_positions.append({
            name: (pose_world(node_by_name[name]).translation if args.asset_dir else patched_hands.get(
                name, unit.scene_graph.nodes[node_by_name[name]].world_transform.translation
            ))
            for name in names if name in node_by_name
        })
    print(f"HAND_PREVIEW full_mesh_triangles={len(faces)}")

if args.hands_only:
    hand_nodes={i for name,i in node_by_name.items() if name.startswith(('j_lefthand','j_righthand','j_leftinhand','j_rightinhand'))}
    palettes=(built_unit.skins[0].node_indices if args.asset_dir else skin.node_indices)
    hand_palettes=[p for p,i in enumerate(palettes) if i in hand_nodes]
    mass=np.where(np.isin(np.asarray(joint_indices),hand_palettes),np.asarray(joint_weights),0).sum(axis=1)
    visible=[(f,m) for f,m in zip(faces,face_materials) if min(mass[f])>.25]
    if not visible:raise ValueError('Hand isolation mask found no compiled faces')
    faces,face_materials=map(list,zip(*visible))
    print('PREVIEW_HAND_ISOLATION',len(faces))

preview_mesh = bpy.data.meshes.new("RoshiaPreUnitMesh")
preview_mesh.from_pydata(vertices, [], faces)
preview_mesh.update()
# Imported buffers contain explicit split normals; do not flag their faces flat.
for polygon in preview_mesh.polygons:
    polygon.use_smooth = True
preview_mesh.normals_split_custom_set([
    normals[loop.vertex_index] for loop in preview_mesh.loops
])
preview_obj = bpy.data.objects.new("RoshiaPreUnitPreview", preview_mesh)
bpy.context.scene.collection.objects.link(preview_obj)

color_attr = preview_mesh.color_attributes.new(name="SourceColor", type="FLOAT_COLOR", domain="POINT")
for index, rgba in enumerate(colors):
    color_attr.data[index].color = rgba
uv_layer = preview_mesh.uv_layers.new(name="UVMap")
for loop in preview_mesh.loops:
    uv_layer.data[loop.index].uv = uvs[loop.vertex_index]

def decode_texture_preview(basename, linear=False):
    from read_native_texture import read_native_top_mip
    decoded_dir=OUT/'decoded_textures'/args.asset_prefix
    decoded_dir.mkdir(parents=True,exist_ok=True)
    dds=decoded_dir/(basename+'.dds')
    decoded,metadata=read_native_top_mip(args.asset_dir/(basename+'.texture'),builder.Oodle(builder.OODLE_DLL))
    dds.write_bytes(decoded)
    print('PREVIEW_NATIVE_TEXTURE '+basename+' '+str(metadata))
    completed=builder.subprocess.run([
        str(ROOT/'tools'/'texconv.exe'),'-nologo','-y','-ft','png',
        '-f','R8G8B8A8_UNORM' if linear else 'R8G8B8A8_UNORM_SRGB',
        '-o',str(decoded_dir),str(dds),
    ],capture_output=True,text=True,errors='replace')
    if completed.returncode:
        raise RuntimeError(completed.stdout+completed.stderr)
    return decoded_dir/(basename+'.png')

source_materials = list(mesh.data.materials)
material_slots = {}
for source_index in sorted(set(face_materials)):
    source_material = source_materials[source_index]
    alpha = builder.material_is_alpha(source_index, source_material.name)
    channel = "bca" if alpha else "bc"
    png = ((args.asset_dir / "source_textures") if args.asset_dir else (OUT / "source_textures")) / f"{args.asset_prefix}_material_{source_index}_{channel}.png"
    if args.asset_dir:
        # Read the deployed-format resource and its high-mip stream, not the
        # intermediate DDS cache. A missing/corrupt final stream must fail here.
        png=decode_texture_preview(png.stem)
    if not args.asset_dir:
        _, _, pixels, srgb = builder.image_pixels_for(source_material)
        pixels = pixels.copy()
        if not srgb:
            rgb = pixels[:, :, :3]
            pixels[:, :, :3] = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.maximum(rgb, 0) ** (1/2.4) - 0.055)
        if not alpha:
            pixels[:, :, 3] = 1
        from roshia_native_materials import FACE_FILL,FACE_DIFFUSE,face_texture_pair
        if source_index in FACE_DIFFUSE:
            pixels,emission=face_texture_pair(source_index,pixels)
            if source_index in FACE_FILL:
                builder.write_png(png.with_name(f'{args.asset_prefix}_material_{source_index}_em.png'),emission)
        builder.write_png(png, pixels)
    material = bpy.data.materials.new(f"RoshiaNativeMaterial_{source_index}")
    material.use_nodes = True
    material.use_backface_culling = True
    material.surface_render_method = "DITHERED"
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(png), check_existing=False)
    texture.image.colorspace_settings.name = "sRGB"
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    from roshia_native_materials import FACE_FILL,ROUGHNESS,read_pbr_fill
    shader.inputs["Roughness"].default_value = ROUGHNESS.get(source_index,.85)
    shader.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in shader.inputs:
        shader.inputs["Specular IOR Level"].default_value = 0.08 if source_index in (0, 1, 2, 3) else 0.2
    material.node_tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
    if getattr(builder,'material_surface_maps',None):
        surface=builder.material_surface_maps(mesh,source_index)
        for kind,format_name in (('nm','normal'),('orm','surface')):
            if kind not in surface:continue
            basename=f'{args.asset_prefix}_material_{source_index}_{kind}'
            data_png=(decode_texture_preview(basename,linear=True)if args.asset_dir else OUT/(basename+'.png'))
            if not args.asset_dir:builder.write_png(data_png,surface[kind])
            tex=nodes.new('ShaderNodeTexImage')
            tex.image=bpy.data.images.load(str(data_png),check_existing=False)
            tex.image.colorspace_settings.name='Non-Color'
            separate=nodes.new('ShaderNodeSeparateColor')
            material.node_tree.links.new(tex.outputs['Color'],separate.inputs['Color'])
            if kind=='orm':
                material.node_tree.links.new(separate.outputs['Green'],shader.inputs['Roughness'])
                material.node_tree.links.new(separate.outputs['Blue'],shader.inputs['Metallic'])
            else:
                # Native UV V is reversed relative to Blender's preview UV.
                flip=nodes.new('ShaderNodeMath');flip.operation='SUBTRACT';flip.inputs[0].default_value=1
                material.node_tree.links.new(separate.outputs['Green'],flip.inputs[1])
                combine=nodes.new('ShaderNodeCombineColor')
                material.node_tree.links.new(separate.outputs['Red'],combine.inputs['Red'])
                material.node_tree.links.new(flip.outputs[0],combine.inputs['Green'])
                # BC5 stores XY; reconstruct positive Z before Blender's map.
                def math_node(operation,a=None,c=None):
                    node=nodes.new('ShaderNodeMath');node.operation=operation
                    for slot,value in enumerate((a,c)):
                        if value is None:continue
                        if isinstance(value,(float,int)):node.inputs[slot].default_value=value
                        else:material.node_tree.links.new(value,node.inputs[slot])
                    return node.outputs[0]
                nx=math_node('SUBTRACT',math_node('MULTIPLY',separate.outputs['Red'],2),1)
                ny=math_node('SUBTRACT',math_node('MULTIPLY',flip.outputs[0],2),1)
                z2=math_node('SUBTRACT',1,math_node('ADD',math_node('MULTIPLY',nx,nx),math_node('MULTIPLY',ny,ny)))
                encoded_z=math_node('MULTIPLY',math_node('ADD',math_node('SQRT',math_node('MAXIMUM',z2,0)),1),.5)
                material.node_tree.links.new(encoded_z,combine.inputs['Blue'])
                normal=nodes.new('ShaderNodeNormalMap')
                material.node_tree.links.new(combine.outputs['Color'],normal.inputs['Color'])
                material.node_tree.links.new(normal.outputs['Normal'],shader.inputs['Normal'])
    if source_index in FACE_FILL:
        basename=f'{args.asset_prefix}_material_{source_index}'
        settings=(read_pbr_fill(args.asset_dir,basename) if args.asset_dir else
                  {'intensity':FACE_FILL[source_index],'multiplier':1.,'color':(1.,1.,1.)})
        if args.asset_dir:
            expected_em=f'{builder.RESOURCE_ROOT}/{basename}_em'
            if settings['textures'][0x5f9dfbfb]!=builder.hash64(expected_em):
                raise ValueError('Unexpected native emission texture binding')
        emission_png=(decode_texture_preview(basename+'_em',linear=True) if args.asset_dir
                      else png.with_name(basename+'_em.png'))
        emission_texture=nodes.new('ShaderNodeTexImage')
        emission_texture.image=bpy.data.images.load(str(emission_png),check_existing=False)
        emission_texture.image.colorspace_settings.name='Non-Color'
        tint=nodes.new('ShaderNodeMixRGB')
        tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1
        tint.inputs[2].default_value=(*settings['color'],1.)
        material.node_tree.links.new(emission_texture.outputs['Color'],tint.inputs[1])
        material.node_tree.links.new(tint.outputs[0],shader.inputs['Emission Color'])
        shader.inputs['Emission Strength'].default_value=settings['intensity']*settings['multiplier']
        print('PREVIEW_NATIVE_FILL '+str({'material':source_index,**settings}))
    if alpha:
        material.node_tree.links.new(texture.outputs["Alpha"], shader.inputs["Alpha"])
    if args.diagnostic_solid:
        for socket in ('Base Color','Alpha','Normal'):
            for link in list(shader.inputs[socket].links):
                material.node_tree.links.remove(link)
        shader.inputs['Base Color'].default_value=(
            (.05,.3,.7,1) if source_material.get('costume_skin') else
            ((.65,.12,.05,1) if source_index%2==0 else (.1,.65,.12,1)))
        shader.inputs['Alpha'].default_value=1
        shader.inputs['Roughness'].default_value=.8
    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    material_slots[source_index] = len(preview_mesh.materials)
    preview_mesh.materials.append(material)
for polygon, source_index in zip(preview_mesh.polygons, face_materials):
    polygon.material_index = material_slots[source_index]

scene = bpy.context.scene
for obj in scene.objects:
    if obj != preview_obj:
        obj.hide_render = True
minimum = Vector(tuple(min(vertex.co[axis] for vertex in preview_mesh.vertices) for axis in range(3)))
maximum = Vector(tuple(max(vertex.co[axis] for vertex in preview_mesh.vertices) for axis in range(3)))
center = Vector((0.0, 0.0, 1.25)) if focus_hands else (minimum + maximum) * 0.5
extent = maximum - minimum
if args.focus_region:
    points = np.asarray(vertices, dtype=np.float32)
    if args.focus_region == 'face':
        selected=np.zeros(len(points),dtype=bool)
        selected[np.asarray(faces)[np.asarray(face_materials)==0].ravel()]=True
    elif args.focus_region == "upper-body":
        selected = points[:, 2] >= minimum.z + extent.z * 0.60
    elif args.focus_region == 'legs':
        leg_nodes = {index for name,index in node_by_name.items()
                     if name.startswith(('j_left','j_right')) and any(s in name for s in ('leg','knee','thigh'))}
        leg_palette = [p for p,n in enumerate(built_unit.skins[0].node_indices) if n in leg_nodes]
        selected = np.where(np.isin(np.asarray(joint_indices),leg_palette),np.asarray(joint_weights),0).sum(axis=1) > .5
    elif args.focus_region == 'right-arm':
        arm_nodes = {index for name,index in node_by_name.items()
                     if name.startswith('j_right') and any(s in name for s in ('arm','hand'))}
        arm_palette = [p for p,n in enumerate(built_unit.skins[0].node_indices) if n in arm_nodes]
        selected = np.where(np.isin(np.asarray(joint_indices),arm_palette),np.asarray(joint_weights),0).sum(axis=1) > .5
    else:
        tail_nodes = {node_by_name[r["node"]] for r in dynamic_rig["runtime_bones"] if r["group"] == "tail"}
        tail_palette = [p for p, n in enumerate(built_unit.skins[0].node_indices) if n in tail_nodes] if args.asset_dir else [palette_by_node[n] for n in tail_nodes]
        selected = np.where(np.isin(np.asarray(joint_indices), tail_palette), np.asarray(joint_weights), 0).sum(axis=1) > 0.05
    if not np.any(selected):
        raise ValueError("Requested preview detail contains no vertices")
    minimum = Vector(points[selected].min(axis=0))
    maximum = Vector(points[selected].max(axis=0))
    center = (minimum + maximum) * 0.5
    extent = maximum - minimum
    mode_name += "_" + args.focus_region
if args.weapon_proxy and runtime_data:
    wi=node_by_name['j_righthand']
    native_world=Matrix(runtime_data['driver_worlds'][wi])
    native_world.translation+=Vector(runtime_data.get('contact_shift',(0,0,0)))
    bind_hand=built_unit.scene_graph.nodes[wi].world_transform
    mi=node_by_name['j_righthandmiddle1'];pi=node_by_name['j_righthandpinky1'];ii=node_by_name['j_righthandindex1']
    # A rod is a contact diagnostic, not a replica of an equipped game weapon.
    center_local=bind_hand.inverted() @ built_unit.scene_graph.nodes[mi].world_transform.translation
    palm_local=bind_hand.to_3x3().transposed() @ (built_unit.scene_graph.nodes[ii].world_transform.translation-built_unit.scene_graph.nodes[pi].world_transform.translation).normalized()
    grip_center=native_world @ (center_local*.62)
    axis=native_world.to_3x3() @ palm_local
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=.012,depth=.30,location=grip_center)
    rod=bpy.context.object;rod.name='DIAGNOSTIC_WEAPON_GRIP';rod.rotation_euler=axis.to_track_quat('Z','Y').to_euler()
    mat=bpy.data.materials.new('GripRod');mat.diffuse_color=(.04,.18,.23,1);rod.data.materials.append(mat)
radius = max(extent.length * 0.65, 1.0)
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1200
scene.render.resolution_y = 1400
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.render.use_compositing = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.exposure = 0.0
scene.view_settings.look = 'None'
if args.model_profile:
    scene.view_settings.look='AgX - Medium High Contrast'
scene.view_settings.gamma = 1.0
scene.eevee.taa_render_samples = 128
scene.camera = None
# Do not inherit the MMD source world's nodes/HDRI. Make the preview lighting
# deterministic; this affects only the offline render, never game textures.
scene.world = bpy.data.worlds.new('RoshiaNeutralPreviewWorld')
scene.world.use_nodes = True
background = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
background.inputs['Color'].default_value = (0.18, 0.21, 0.26, 1)
background.inputs['Strength'].default_value = 0.22
if args.model_profile:background.inputs['Strength'].default_value=.10

directions = (((0, 1, 0.2), "front"), ((0, -1, 0.2), "back")) if focus_hands else (
    ((0.0, 1.0, 0.05), "front"),
    ((1.0, 0.0, 0.05), "side"),
    ((0.0, -1.0, 0.05), "back"),
)
if args.focus_region=='face':
    directions=(((0.0,1.0,-.06),'front'),((1.0,0.0,.05),'side'),
                ((0.0,-1.0,.05),'back'),((.38,1.0,-.04),'three-quarter'))
if args.views:
    direction_by_view=dict((view,direction)for direction,view in directions)
    direction_by_view['three-quarter']=(.38,1.0,-.04) if args.focus_region=='face' else (.60,1.0,.05)
    directions=tuple((direction_by_view[view],view)for view in args.views)
elif args.focus_region=='face':
    directions=(((0.0,1.0,-.06),'front'),((.38,1.0,-.04),'three-quarter'))
render_views = []
if individual_hands:
    for side in ("left", "right"):
        wrist_name = f"j_{side}hand"
        tips = ("thumb", "index", "middle", "ring", "pinky")
        landmarks = hand_joint_positions[0 if side == "left" else 1]
        root = landmarks[wrist_name]
        tips_world = [landmarks[f"j_{side}hand{finger}3"] for finger in tips]
        hand_center = (root + sum(tips_world, Vector((0.0, 0.0, 0.0))) / len(tips_world)) * 0.5
        long_axis = (sum(tips_world, Vector((0.0, 0.0, 0.0))) / len(tips_world) - root).normalized()
        index_tip = landmarks[f"j_{side}handindex3"]
        pinky_tip = landmarks[f"j_{side}handpinky3"]
        width_axis = (pinky_tip - index_tip).normalized()
        palm_normal = long_axis.cross(width_axis).normalized()
        for sign, view in ((-1, "front"), (1, "back")):
            if args.views and view not in args.views:
                continue
            render_views.append((hand_center, palm_normal * sign, f"{side}_{view}", 0.30))
else:
    portrait_scale=max(extent.x,extent.y,extent.z)*1.75 if args.focus_region=='face' else max(extent.x,extent.y,extent.z)*1.5
    render_views = [(center, direction, view, 1.6 if focus_hands else portrait_scale)
                    for direction, view in directions]

for view_index, (center, direction, view, ortho_scale) in enumerate(render_views):
    camera_data = bpy.data.cameras.new(f"PreUnitCamera_{view}")
    camera = bpy.data.objects.new(f"PreUnitCamera_{view}", camera_data)
    scene.collection.objects.link(camera)
    camera_direction=Vector(direction)
    if args.camera_elevation is not None:
        camera_direction.z=math.hypot(camera_direction.x,camera_direction.y)*math.tan(math.radians(args.camera_elevation))
    camera.location = center + camera_direction * (2.0 if individual_hands else (1.0 if focus_hands else radius))
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = ortho_scale
    camera_data.clip_start = .001
    camera_data.clip_end = 100.
    scene.camera = camera

    key_data = bpy.data.lights.new(f"PreUnitKey_{view}", "AREA")
    key = bpy.data.objects.new(f"PreUnitKey_{view}", key_data)
    scene.collection.objects.link(key)
    view_direction = Vector(direction).normalized()
    face_focus=args.focus_region=='face'
    # Use the camera quaternion directly; matrix_world can be stale until
    # a dependency-graph update after assigning the new camera's Euler angles.
    camera_right = camera.rotation_euler.to_quaternion() @ Vector((1, 0, 0))
    key.location = (center + view_direction * (radius * .75)
                    + camera_right * (radius * .30) + Vector((0,0,radius*.35))
                    if face_focus else
                    center + view_direction * (radius * .45) + Vector((0,0,radius*.65)))
    key.rotation_euler = (center - key.location).to_track_quat("-Z", "Y").to_euler()
    key_data.energy = (12 if individual_hands else (48 if face_focus else 45))*args.lighting_scale
    key_data.size = 0.35 if individual_hands else radius * (1.0 if face_focus else 0.75)

    fill_data = bpy.data.lights.new(f"PreUnitFill_{view}", "AREA")
    fill = bpy.data.objects.new(f"PreUnitFill_{view}", fill_data)
    scene.collection.objects.link(fill)
    fill.location = (center + view_direction * (radius * .55)
                     - camera_right * (radius * .50) + Vector((0,0,radius*.15))
                     if face_focus else
                     center + view_direction * (radius * .1)
                     - camera_right * (radius * .65) + Vector((0,0,radius*.25)))
    fill.rotation_euler = (center - fill.location).to_track_quat("-Z", "Y").to_euler()
    fill_data.energy = (4 if individual_hands else (8 if face_focus else 20))*args.lighting_scale
    fill_data.size = 0.25 if individual_hands else radius * (1.1 if face_focus else 0.8)

    focus_tag = "_hands" if focus_hands else ""
    individual_tag = "_closeup" if individual_hands else ""
    scene.render.filepath = str(OUT / f"roshia_preunit_{mode_name}{focus_tag}{individual_tag}_{view}_preview.png")
    print('PREVIEW_VIEW ' + json.dumps({
        'view': view, 'camera': list(camera.location), 'target': list(center),
        'ortho_scale': ortho_scale, 'key_location': list(key.location),
        'key_energy': key_data.energy, 'fill_location': list(fill.location),
        'fill_energy': fill_data.energy, 'world_strength': background.inputs['Strength'].default_value,
        'exposure': scene.view_settings.exposure, 'view_transform': scene.view_settings.view_transform,
        'look': scene.view_settings.look, 'lighting_scale': args.lighting_scale,
    }))
    if args.save_scene and view_index == 0:
        args.save_scene.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.save_scene.resolve()))
    bpy.ops.render.render(write_still=True)
    # A previous view's lights must not accumulate in later views.
    key.hide_render = True
    fill.hide_render = True

print("PREUNIT_PREVIEW " + str({"mode": mode_name, "output": str(OUT)}))
