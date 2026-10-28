import json
import argparse
import math
import pathlib
import struct
import sys
import types
import subprocess
import zlib
import binascii
import re

import bpy
import numpy as np
from mathutils import Matrix, Vector


ROOT = pathlib.Path(__file__).resolve().parents[2]
ADDON = ROOT / "tools" / "bitsquid-addon"
TEMPLATE = ROOT / "Custom" / "qianxia"
SOURCE_BLEND = pathlib.Path(r"<SOURCE_ROOT>\Rossia\洛茜.blend")
OUTPUT = ROOT / "tools" / "model-work" / "roshia" / "first_build" / "Custom"
RESOURCE_ROOT = "content/mods/roshia"
MESH_OBJECT_NAME = "洛茜_mesh"
ARMATURE_OBJECT_NAME = "洛茜_arm"
SCALE = 1.30  # Uniform stature fit: source shoulders reach the shared human rig.
BINDING_MODE = "proportion-fk"
GEO_COUNT = 31
ARM_MATERIALS = {13}
# The source eye, sclera, highlight, and lash meshes are closed opaque islands.
# Their PNGs carry no useful opacity channel (alpha is 1.0 everywhere), so they
# must use the same diffuse path as the body.  Treating them as BCA alpha cards
# makes the game alpha shader discard or darken the painted eye detail.
EYE_MATERIALS = set()
# The source tail chain is already authored against the source cape/back.  The
# previous candidate applied separate hard-coded lateral/rear/root offsets to
# the generated shell and a different drop to the runtime pivots, which made
# the tail detach from the body.  Keep one shared target-space offset profile
# for both the shell and the helper bones.
TAIL_CHAIN_SCALE = 1.0
TAIL_ROOT_OFFSET = Vector((0.0, 0.020, -0.010))
TAIL_TIP_OFFSET = Vector((0.0, -0.020, -0.160))
# First-person hands retain the source mesh proportions and joint distances.
# Only the wrist is aligned to the native hand; local animation is transferred
# through a rest-basis correction, without fitting every joint to the template.
FP_DIGIT_LENGTH_SCALE = 1.0
FP_THUMB_LENGTH_SCALE = 1.0
FP_DIGIT_WIDTH_SCALE = 1.0


def tail_target_offset(t):
    """Return the small, continuous target-space offset along the source tail."""
    t = min(1.0, max(0.0, float(t)))
    curve = t * t * (3.0 - 2.0 * t)
    return TAIL_ROOT_OFFSET.lerp(TAIL_TIP_OFFSET, curve)
SKIP_MATERIAL_NAMES = ("目影", "发影", "表情", "emo1", "emo3")
ALPHA_MATERIAL_NAMES = ("发Alpha",)
FIRST_PERSON_EXCLUDED_MATERIAL_NAMES = (
    "面", "目", "口", "发", "髪", "face", "eye", "mouth", "hair", "cloth2",
)
OODLE_DLL = pathlib.Path(r"<DARKTIDE_GAME>\binaries\oo2core_9_win64.dll")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from native_texture import Oodle, pack_texture


def source_coordinate3():
    return Matrix((
        (-SCALE, 0, 0),
        (0, -SCALE, 0),
        (0, 0, SCALE),
    ))


def side_bone_candidates(stem, suffix):
    prefix = "左" if suffix == ".L" else "右"
    return (f"{stem}{suffix}", f"{prefix}{stem}", f"{prefix}{stem}{suffix}")


def find_source_bone(armature, candidates):
    return next((armature.data.bones.get(name) for name in candidates
                 if armature.data.bones.get(name) is not None), None)


def material_is_alpha(index, name):
    lowered = name.casefold()
    return index in ARM_MATERIALS or index in EYE_MATERIALS or any(token.casefold() in lowered
                                         for token in ALPHA_MATERIAL_NAMES)


def prepare_source(mesh,armature):
    # MMD imports often leave material nodes pointing at empty external
    # placeholders while a packed image with the same stem is present in the
    # blend. Rebind those nodes in-memory before any diffuse/normal sampling.
    # The source .blend remains untouched on disk.
    def identity(name):
        name = re.sub(r'\.\d{3}$', '', name)
        return re.sub(r'\.(png|dds|tga|jpg|bmp)$', '', name, flags=re.I)
    packed = {}
    for image in bpy.data.images:
        if image.size[0] and image.size[1] and image.packed_file:
            packed.setdefault(identity(image.name), []).append(image)
    for material in mesh.data.materials:
        if not material or not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            image = node.image if node.type == 'TEX_IMAGE' else None
            if image is None or (image.size[0] and image.size[1]):
                continue
            candidates = packed.get(identity(image.name), ())
            if not candidates and material.name in ('目','目HL') and 'wulfa_iris' in image.name:
                # The supplied CMB preset embeds iris_01 while the MMD slots
                # retain a broken external iris_00 path. Both eye slots use the
                # inspected full-colour iris carrier, never a material fallback.
                candidates=tuple(im for im in bpy.data.images if im.packed_file and im.size[0]
                                 and identity(im.name)=='T_actor_wulfa_iris_01_D')
            if candidates:
                node.image = max(candidates, key=lambda item: item.size[0] * item.size[1])
    prepare_skirt_arm_clearance(mesh, armature)
    from roshia_tail_fur import prepare
    prepare(sys.modules[__name__],mesh,armature)


def prepare_skirt_arm_clearance(mesh, armature):
    """Keep the authored skirt silhouette; collision is handled by animation."""
    coordinate3 = source_coordinate3()
    target_to_source = coordinate3.to_3x3().inverted()
    mesh_to_source = mesh.matrix_world.to_3x3().inverted()
    group_names = {group.index: group.name for group in mesh.vertex_groups}
    hips = find_source_bone(armature, ("腰", "全ての親"))
    center = (coordinate3 @ (armature.matrix_world @ hips.head_local)
              if hips else Vector((0.0, 0.0, 0.0)))
    moved = 0
    max_contraction = 0.0

    def smoothstep(low, high, value):
        t = min(1.0, max(0.0, (value - low) / (high - low)))
        return t * t * (3.0 - 2.0 * t)

    for vertex in mesh.data.vertices:
        skirt_weight = sum(
            assignment.weight for assignment in vertex.groups
            if group_names.get(assignment.group, "").startswith("スカート_")
        )
        if skirt_weight < 0.20:
            continue
        target_position = coordinate3 @ (mesh.matrix_world @ vertex.co)
        height = float(target_position.z)
        vertical_mask = smoothstep(0.20, 0.42, height) * (1.0 - smoothstep(1.12, 1.30, height))
        # A previous radial contraction made the hem visibly cave inward.  The
        # source skirt is already smooth and should remain unchanged in the
        # replacement; native arm animation is the only reliable collision fix.
        contraction = 0.0 * min(1.0, skirt_weight) * vertical_mask
        radial = Vector((target_position.x - center.x, target_position.y - center.y, 0.0))
        source_delta = target_to_source @ (-radial * contraction)
        if source_delta.length <= 0.0001:
            continue
        vertex.co += mesh_to_source @ source_delta
        moved += 1
        max_contraction = max(max_contraction, contraction)
    print("SKIRT_ARM_CLEARANCE " + json.dumps({
        "vertices": moved, "max_radial_contraction": max_contraction,
        "method": "preserve source skirt silhouette (zero contraction)",
        "height_range_m": [0.20, 1.30],
        "weight_prefix": "スカート_",
    }, ensure_ascii=False))


def lua_string(value):
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n")
    return '"' + escaped + '"'


def package(name, path):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
    return module


package("bitsquid", ADDON)
parser_module = types.ModuleType("bitsquid.import_base")
parser_module.Parser = type("Parser", (), {})
sys.modules["bitsquid.import_base"] = parser_module
package("bitsquid.murmur", ADDON / "murmur")
package("bitsquid.stingray.unit", ADDON / "stingray" / "unit")
stream_module = types.ModuleType("bitsquid.stream")
sys.modules["bitsquid.stream"] = stream_module

from bitsquid.deserializing import Cursor
from bitsquid.murmur.murmurhash64 import hash32, hash64
from bitsquid.murmur.rainbow_table import IDString32, IDString64, IDStringBase, resource_map


class StreamReader:
    def __init__(self, cursor):
        self.cursor = cursor

    def next_u32(self):
        return self.cursor.ReadU32()

    def next_data(self):
        return self.cursor.ReadByteArray()


stream_module.StreamDataReader = StreamReader
stream_module.load_stream_dt = lambda path: StreamReader(Cursor(str(TEMPLATE / pathlib.Path(path))))
IDStringBase.lookup = lambda value: resource_map.trylookup_idstring(value)

import bitsquid.stingray as stingray
import bitsquid.stingray.unit.dt as unit_dt
import bitsquid.stingray.mesh_geometry as mesh_geometry
import bitsquid.stingray.material as material_module
material_module.EXPECTED_MATERIAL_VERSIONS_DT.add(62)
from bitsquid.stingray.bones import BonesResourceDT
from bitsquid.stingray.material import MaterialResourceDT
from bitsquid.stingray.scene_graph import ParentType

unit_dt.load_stream_dt = stream_module.load_stream_dt
material_module.load_stream_dt = stream_module.load_stream_dt


def u32(value):
    return struct.pack("<I", int(value))


def u64(value):
    return struct.pack("<Q", int(value))


def f32(value):
    return struct.pack("<f", float(value))


def pack_array(values, dtype):
    return np.asarray(values, dtype=dtype).tobytes()


def read_unit_offsets(path):
    raw = path.read_bytes()
    c = Cursor(str(path))
    c.seek(unit_dt.HEADER_SIZE)
    if c.ReadU32() != unit_dt.EXPECTED_VERSION_DT:
        raise ValueError("Unexpected template unit version")
    geometry_count = c.ReadU32()
    geometry_start = c.tell()
    geometries = [mesh_geometry.MeshGeometryDT(c) for _ in range(geometry_count)]
    geometry_end = c.tell()

    skin_array_start = c.tell()
    skins = stingray.Array(stingray.SkinData, c)
    skin_array_end = c.tell()
    c.ReadByteArray()
    stingray.Array(stingray.SimpleAnimationGroup, c)
    scene_graph_start = c.tell()
    scene_graph = stingray.scene_graph.SceneGraphDT(c)
    scene_graph_end = c.tell()
    mesh_objects_array_offset = c.tell()
    mesh_objects = stingray.Array(stingray.mesh_object.MeshObjectDT, c)
    if len(mesh_objects) != geometry_count:
        raise ValueError("Template mesh objects do not match geometry count")
    stingray.Array(stingray.actor_resource.ActorResourceDT, c)
    stingray.Array(stingray.actor_resource.ActorResourceDT, c)
    c.ReadU32Array()
    stingray.Array(stingray.camera.CameraDT, c)
    stingray.Array(stingray.light.LightDT, c)
    c.ReadByteArray()
    stingray.Array(stingray.lod_object_data.LODObjectDataDT, c)
    stingray.Array(stingray.terrain_data.TerrainDataDT, c)
    stingray.Array(unit_dt.Unk11Struct, c)
    stingray.Array(stingray.joint_desc.JointDescDT, c)
    stingray.Array(stingray.MoverDesc, c)
    stingray.Array(unit_dt.Unk15Struct, c)
    c.ReadBool()
    c.ReadByteArray()
    c.ReadByteArray()
    for _ in range(c.ReadU32()):
        c.ReadIDString32()
        c.ReadU32Array()
    c.ReadByteArray()
    c.ReadByteArray()
    c.ReadByteArray()
    c.ReadByteArray()

    default_material_offset = c.tell()
    c.ReadIDString64()
    material_count = c.ReadU32()
    materials_offset = c.tell()
    c.seek(materials_offset + material_count * 12)
    c.ReadU32()  # empty unknown material map
    stingray.Array(unit_dt.Unk17Struct, c)
    c.ReadByteArray()
    stingray.Array(unit_dt.Unk19Struct, c)
    skeleton_offset = c.tell()
    c.ReadIDString64()

    return {
        "raw": raw,
        "geometries": geometries,
        "geometry_start": geometry_start,
        "geometry_end": geometry_end,
        "skin_array_start": skin_array_start,
        "skin_array_end": skin_array_end,
        "skins": skins,
        "scene_graph_start": scene_graph_start,
        "scene_graph_end": scene_graph_end,
        "scene_graph": scene_graph,
        "mesh_objects": mesh_objects,
        "mesh_objects_array_offset": mesh_objects_array_offset,
        "default_material_offset": default_material_offset,
        "materials_offset": materials_offset,
        "material_count": material_count,
        "skeleton_offset": skeleton_offset,
    }


def source_bone_targets(armature, node_by_name=None, dynamic_targets=None):
    exact = {
        "全ての親": "j_hips", "センター": "j_hips", "センター2": "j_hips",
        "グルーブ": "j_hips", "グルーブ2": "j_hips", "腰": "j_hips",
        "下半身": "j_hips", "上半身": "j_spine", "上半身1": "j_spine1",
        "上半身2": "j_spine2", "上半身3": "j_spine2", "首": "j_neck", "頭": "j_head",
        "左肩": "j_leftshoulder", "左腕": "j_leftarm", "左ひじ": "j_leftforearm",
        "左手首": "j_lefthand", "右肩": "j_rightshoulder", "右腕": "j_rightarm",
        "右ひじ": "j_rightforearm", "右手首": "j_righthand",
        "左足": "j_leftupleg", "左ひざ": "j_leftleg", "左足首": "j_leftfoot",
        "左つま先": "j_leftfoot", "右足": "j_rightupleg", "右ひざ": "j_rightleg",
        "右足首": "j_rightfoot", "右つま先": "j_rightfoot",
        "cape_base_L_a_01_jnt": "j_spine2",
        "cape_base_R_a_01_jnt": "j_spine2",
        "gs_base_Back_a_01_jnt": "j_spine2",
        "gs_base_Back_a_02_jnt": "j_spine2",
        "gs_base_Back_a_03_jnt": "j_spine2",
    }
    target = {name: name for name in (
        "j_hips", "j_spine", "j_spine1", "j_spine2", "j_neck", "j_head",
        "j_leftshoulder", "j_leftarm", "j_leftforearm", "j_lefthand",
        "j_rightshoulder", "j_rightarm", "j_rightforearm", "j_righthand",
        "j_leftupleg", "j_leftleg", "j_leftfoot", "j_rightupleg", "j_rightleg", "j_rightfoot",
    )}
    finger_specs = {
        "親指": ("thumb", ("０", "１", "２"), ("handthumb1", "handthumb2", "handthumb3")),
        "人指": ("index", ("１", "２", "３"), ("handindex1", "handindex2", "handindex3")),
        "中指": ("middle", ("１", "２", "３"), ("handmiddle1", "handmiddle2", "handmiddle3")),
        "薬指": ("ring", ("１", "２", "３"), ("handring1", "handring2", "handring3")),
        "小指": ("pinky", ("１", "２", "３"), ("handpinky1", "handpinky2", "handpinky3")),
    }
    for source_stem, (target_stem, source_segments, target_segments) in finger_specs.items():
        for side, suffix in (("left", ".L"), ("right", ".R")):
            for source_segment, target_segment in zip(source_segments, target_segments):
                for candidate in side_bone_candidates(source_stem + source_segment, suffix):
                    exact[candidate] = f"j_{side}{target_segment}"
    exact.update({
        "Bip001_L_Hand_ty_minus": "j_lefthand",
        "Bip001_L_Hand_ty_plus": "j_lefthand",
        "Bip001_R_Hand_ty_minus": "j_righthand",
        "Bip001_R_Hand_ty_plus": "j_righthand",
        **{f"Bip001_L_FingerTop{index}": "j_lefthand" for index in range(1, 5)},
        **{f"Bip001_R_FingerTop{index}": "j_righthand" for index in range(1, 5)},
    })
    for bone in armature.data.bones:
        name = bone.name
        if (name.startswith(("paw_base_L_", "paw_base_R_", "waistband_base_R_"))
                and bone.parent and dynamic_targets
                and bone.parent.name in dynamic_targets):
            exact[name] = dynamic_targets[bone.parent.name]
        elif name.startswith(("cape_base_L_", "cape_base_R_", "gs_base_Back_")):
            exact[name] = "j_spine2"
        elif name.startswith("shawl_base_L_"):
            # All source shawl controls are parented to 腕.L, not 肩.L.
            # Follow the sleeve's A-pose-to-animation rotation at the same pivot.
            exact[name] = "j_leftarm"
        elif name.startswith("shawl_base_R_"):
            exact[name] = "j_rightarm"
        elif name.startswith("hand_base_L_"):
            exact[name] = "j_leftforearm"
        elif name.startswith("hand_base_R_"):
            exact[name] = "j_rightforearm"
        elif name.startswith("hat_base_"):
            exact[name] = "j_head"

    def infer(name):
        if name in exact:
            return exact[name]
        side = "left" if ("左" in name or ".L" in name or "_L" in name or "left" in name.lower()) else None
        if side is None and ("右" in name or ".R" in name or "_R" in name or "right" in name.lower()):
            side = "right"
        if side:
            # MMD's 足先EX is the toe deform bone, not a thigh/leg control.
            # Resolve it before the broad 足 -> upleg fallback.
            if "つま先" in name or "足先" in name:
                return f"j_{side}foot"
            if "足首" in name or "足ＩＫ" in name or "足IK" in name:
                return f"j_{side}foot"
            if "ひざ" in name or "膝" in name:
                return f"j_{side}leg"
            if "足" in name or "腿" in name or "股" in name:
                return f"j_{side}upleg"
            if "腕捩" in name:
                return f"j_{side}arm"
            if "手捩" in name:
                return f"j_{side}forearm"
            if "手首" in name or "手" in name or "指" in name:
                return f"j_{side}hand"
            if "ひじ" in name or "肘" in name:
                return f"j_{side}forearm"
            if "肩" in name:
                return f"j_{side}shoulder"
            if "腕" in name:
                return f"j_{side}arm"
        lowered = name.lower()
        if "head" in lowered or "髪" in name or "顔" in name or "目" in name or "前髪" in name:
            return "j_head"
        if "neck" in lowered or "首" in name:
            return "j_neck"
        if "胸" in name or "上半身3" in name or "上半身2" in name:
            return "j_spine2"
        if "上半身1" in name:
            return "j_spine1"
        if "上半身" in name or "spine" in lowered:
            return "j_spine"
        if "腰" in name or "センター" in name or "グルーブ" in name or "下半身" in name:
            return "j_hips"
        return None

    result = {}
    for bone in armature.data.bones:
        current = bone
        mapped = None
        while current and mapped is None:
            mapped = infer(current.name)
            current = current.parent
        result[bone.name] = mapped or "j_hips"
    for name, mapped in result.items():
        if "足先" in name or "つま先" in name:
            if mapped not in ("j_leftfoot", "j_rightfoot"):
                raise ValueError(f"Toe control mapped outside foot: {name} -> {mapped}")
    return result


def source_head_in_target(armature, bone, root_map):
    coordinate3 = source_coordinate3()
    source_head = coordinate3 @ (armature.matrix_world @ bone.head_local)
    return root_map @ source_head


def shared_root_map(armature, unit, node_by_name, mesh=None):
    if mesh is None:
        mesh = bpy.data.objects.get(MESH_OBJECT_NAME)
    if mesh is None:
        raise ValueError("Cannot compute the shared root map without the source mesh")
    source_hips = find_source_bone(armature, ("腰", "全ての親"))
    if source_hips is None:
        raise ValueError("Cannot resolve source hips for the shared root map")

    coordinate3 = source_coordinate3()
    source_hips_position = coordinate3 @ (armature.matrix_world @ source_hips.head_local)
    source_positions = np.asarray([
        coordinate3 @ (mesh.matrix_world @ vertex.co)
        for vertex in mesh.data.vertices
    ], dtype=np.float32)
    source_floor_z = float(source_positions[:, 2].min())

    target_hips = unit.scene_graph.nodes[node_by_name["j_hips"]].world_transform
    target_floor_points = []
    for mesh_object in unit.meshes:
        if not mesh_object.has_mesh_geo():
            continue
        bounds = mesh_object.bounding_volume
        node_world = unit.scene_graph.nodes[mesh_object.node_index].world_transform
        for x in (bounds.lower_bounds.x, bounds.upper_bounds.x):
            for y in (bounds.lower_bounds.y, bounds.upper_bounds.y):
                for z in (bounds.lower_bounds.z, bounds.upper_bounds.z):
                    target_floor_points.append(node_world @ Vector((x, y, z)))
    if not target_floor_points:
        foot_nodes = [
            unit.scene_graph.nodes[index].world_transform.translation.z
            for name, index in node_by_name.items()
            if name in ("j_leftfoot", "j_rightfoot", "j_lefttoebase", "j_righttoebase")
        ]
        target_floor_z = min(foot_nodes) if foot_nodes else target_hips.translation.z
    else:
        target_floor_z = min(point.z for point in target_floor_points)

    root_translation = target_hips.translation - source_hips_position
    root_translation.z = target_floor_z - source_floor_z
    root_map = Matrix.Translation(root_translation)
    print("SHARED_ROOT_MAP " + json.dumps({
        "source_floor_z": source_floor_z,
        "target_floor_z": target_floor_z,
        "translation": tuple(round(float(value), 6) for value in root_translation),
    }))
    return root_map


def scene_graph_transform_records(unit, desired_worlds, parent_overrides=None):
    parent_overrides = parent_overrides or {}

    def depth(node_index):
        value = 0
        node = unit.scene_graph.nodes[node_index]
        while node.parent_type == ParentType.INTERNAL:
            value += 1
            node = unit.scene_graph.nodes[node.parent_index]
        return value

    records = {}
    for node_index in sorted(desired_worlds, key=depth):
        node = unit.scene_graph.nodes[node_index]
        parent_index = parent_overrides.get(node_index, node.parent_index)
        if node.parent_type != ParentType.INTERNAL:
            raise ValueError(f"Mapped rig node has no internal parent: {node.name.lookup()}")
        parent_world = desired_worlds.get(
            parent_index, unit.scene_graph.nodes[parent_index].world_transform
        )
        world = desired_worlds[node_index]
        records[node_index] = {
            "name": node.name.lookup(),
            "world": world,
            "parent_index": parent_index,
            "local": parent_world.inverted() @ world,
        }
    return records


def source_bone_direction(armature, bone):
    direction = source_coordinate3() @ armature.matrix_world.to_3x3() @ (
        bone.tail_local - bone.head_local
    )
    if direction.length_squared < 1e-12:
        raise ValueError(f"Source bone has a zero-length direction: {bone.name}")
    return direction.normalized()


def aligned_world_rotation(world, delta_rotation, translation):
    result = delta_rotation @ world.to_3x3()
    aligned = result.to_4x4()
    aligned.translation = translation
    return aligned


def orthogonal_frame(long_axis, width_axis):
    longitudinal = long_axis.normalized()
    width = width_axis - longitudinal * width_axis.dot(longitudinal)
    if width.length_squared < 1e-12:
        raise ValueError("Cannot construct a hand frame from collinear landmarks")
    width.normalize()
    normal = longitudinal.cross(width).normalized()
    width = normal.cross(longitudinal).normalized()
    return Matrix((longitudinal, width, normal)).transposed()


def target_bind_transforms(armature, node_by_name, unit, translation_only=False,
                           matrix_targets=(), node_records=None, mesh=None):
    canonical_sources = {
        "j_hips": ("腰", "全ての親"),
        "j_spine": ("上半身",),
        "j_spine1": ("上半身1", "上半身2"),
        "j_spine2": ("上半身2", "上半身3"),
        "j_neck": ("首",),
        "j_head": ("頭",),
        "j_leftshoulder": side_bone_candidates("肩", ".L") + ("肩C.L",),
        "j_leftarm": side_bone_candidates("腕", ".L"),
        "j_leftforearm": side_bone_candidates("ひじ", ".L") + ("肘.L", "左肘"),
        "j_lefthand": side_bone_candidates("手首", ".L"),
        "j_rightshoulder": side_bone_candidates("肩", ".R") + ("肩C.R",),
        "j_rightarm": side_bone_candidates("腕", ".R"),
        "j_rightforearm": side_bone_candidates("ひじ", ".R") + ("肘.R", "右肘"),
        "j_righthand": side_bone_candidates("手首", ".R"),
        "j_leftupleg": side_bone_candidates("足", ".L"),
        "j_leftleg": side_bone_candidates("ひざ", ".L") + ("膝.L", "左膝"),
        "j_leftfoot": side_bone_candidates("足首", ".L"),
        "j_rightupleg": side_bone_candidates("足", ".R"),
        "j_rightleg": side_bone_candidates("ひざ", ".R") + ("膝.R", "右膝"),
        "j_rightfoot": side_bone_candidates("足首", ".R"),
    }
    finger_specs = {
        "thumb": (("親指０", "親指１", "親指２"), ("handthumb1", "handthumb2", "handthumb3")),
        "index": (("人指１", "人指２", "人指３"), ("handindex1", "handindex2", "handindex3")),
        "middle": (("中指１", "中指２", "中指３"), ("handmiddle1", "handmiddle2", "handmiddle3")),
        "ring": (("薬指１", "薬指２", "薬指３"), ("handring1", "handring2", "handring3")),
        "pinky": (("小指１", "小指２", "小指３"), ("handpinky1", "handpinky2", "handpinky3")),
    }
    for finger, (source_segments, target_segments) in finger_specs.items():
        for side, suffix in (("left", ".L"), ("right", ".R")):
            for source_segment, target_segment in zip(source_segments, target_segments):
                target_name = f"j_{side}{target_segment}"
                canonical_sources[target_name] = side_bone_candidates(source_segment, suffix)
    root_map = shared_root_map(armature, unit, node_by_name, mesh)
    root_transform = np.asarray(root_map, dtype=np.float32)
    limb_children = {
        "j_leftarm": "j_leftforearm",
        "j_leftforearm": "j_lefthand",
        "j_rightarm": "j_rightforearm",
        "j_rightforearm": "j_righthand",
        "j_leftupleg": "j_leftleg",
        "j_leftleg": "j_leftfoot",
        "j_rightupleg": "j_rightleg",
        "j_rightleg": "j_rightfoot",
    }
    transforms = {}
    desired_worlds = {}
    missing = []
    arm_bend_planes = {}
    for side in ('left', 'right'):
        chain = [f'j_{side}{part}' for part in ('arm','forearm','hand')]
        source_points = [source_head_in_target(armature, find_source_bone(armature, canonical_sources[n]), root_map) for n in chain]
        target_points = [unit.scene_graph.nodes[node_by_name[n]].world_transform.translation for n in chain]
        source_normal = (source_points[1]-source_points[0]).cross(source_points[2]-source_points[1])
        target_normal = (target_points[1]-target_points[0]).cross(target_points[2]-target_points[1])
        if min(source_normal.length_squared,target_normal.length_squared)>1e-12:
            for name in chain[:2]:
                arm_bend_planes[name] = (source_normal.normalized(),target_normal.normalized())
    for target_name, candidates in canonical_sources.items():
        node_index = node_by_name.get(target_name)
        source_bone = find_source_bone(armature, candidates)
        if node_index is None or source_bone is None:
            missing.append(target_name)
            continue
        transforms[target_name] = root_transform.copy()
        world = unit.scene_graph.nodes[node_index].world_transform.copy()
        translation = source_head_in_target(armature, source_bone, root_map)
        child_name = limb_children.get(target_name)
        if child_name:
            child_index = node_by_name.get(child_name)
            if child_index is None:
                raise ValueError(f"Missing target child node for limb rotation: {child_name}")
            target_child_world = unit.scene_graph.nodes[child_index].world_transform
            target_direction = target_child_world.translation - world.translation
            if target_direction.length_squared < 1e-12:
                raise ValueError(f"Target limb segment has zero length: {target_name} -> {child_name}")
            child_bone = find_source_bone(armature, canonical_sources[child_name])
            source_direction = (source_head_in_target(armature, child_bone, root_map)
                                - translation).normalized()
            delta_rotation = target_direction.normalized().rotation_difference(
                source_direction
            ).to_matrix()
            if target_name in arm_bend_planes:
                # Direction alone leaves roll undetermined. A common elbow
                # plane prevents upper/lower arms from acquiring contradictory
                # rolls when converting the almost-straight MMD rest pose.
                source_normal,target_normal = arm_bend_planes[target_name]
                delta_rotation = (orthogonal_frame(source_direction,source_normal)
                                  @ orthogonal_frame(target_direction,target_normal).transposed())
            world = aligned_world_rotation(world, delta_rotation, translation)
        else:
            world.translation = translation
        desired_worlds[node_index] = world
    if missing:
        raise ValueError("Cannot retarget MMD bind pose; missing target/source bones: " + ", ".join(missing))
    if node_records is not None:
        node_records.update(scene_graph_transform_records(unit, desired_worlds))
    return transforms


def source_hand_bind_transforms(armature, bone_targets, node_by_name, unit, root_map=None):
    """Keep hand geometry fixed and orient animation pivots to the source palm plane."""
    if root_map is None:
        root_map = shared_root_map(armature, unit, node_by_name)
    root_transform = np.asarray(root_map, dtype=np.float32)
    finger_specs = (
        ("thumb", ("親指０", "親指１", "親指２"),
         ("handthumb1", "handthumb2", "handthumb3")),
        ("index", ("人指１", "人指２", "人指３"),
         ("handindex1", "handindex2", "handindex3")),
        ("middle", ("中指１", "中指２", "中指３"),
         ("handmiddle1", "handmiddle2", "handmiddle3")),
        ("ring", ("薬指１", "薬指２", "薬指３"),
         ("handring1", "handring2", "handring3")),
        ("pinky", ("小指１", "小指２", "小指３"),
         ("handpinky1", "handpinky2", "handpinky3")),
    )
    source_transforms = {}
    desired_worlds = {}
    coordinate3 = source_coordinate3()
    armature_world = armature.matrix_world.copy()

    def source_head(bone):
        return coordinate3 @ (armature_world @ bone.head_local)

    for side, suffix in (("left", ".L"), ("right", ".R")):
        wrist_bone = find_source_bone(armature, side_bone_candidates("手首", suffix))
        wrist_node = node_by_name.get(f"j_{side}hand")
        if wrist_bone is None or wrist_node is None:
            raise ValueError(f"Missing {side} wrist frame landmark")
        for bone in armature.data.bones:
            target_name = bone_targets.get(bone.name, "")
            if target_name.startswith((f"j_{side}hand", f"j_{side}inhand")):
                source_transforms[bone.name] = root_transform.copy()

        source_index = find_source_bone(armature, side_bone_candidates("人指１", suffix))
        source_pinky = find_source_bone(armature, side_bone_candidates("小指１", suffix))
        # A palm frame must use metacarpophalangeal roots, not a curled distal
        # fingertip. The template's middle3 includes its rest finger curl;
        # aligning a straight source palm to it incorrectly pitches the wrist.
        source_middle_root = find_source_bone(armature, side_bone_candidates("中指１", suffix))
        target_index = node_by_name.get(f"j_{side}handindex1")
        target_pinky = node_by_name.get(f"j_{side}handpinky1")
        target_middle_root = node_by_name.get(f"j_{side}handmiddle1")
        if not all((source_index, source_pinky, source_middle_root,
                    target_index is not None, target_pinky is not None,
                    target_middle_root is not None)):
            raise ValueError(f"Missing {side} hand-frame landmarks")
        wrist_template = unit.scene_graph.nodes[wrist_node].world_transform
        target_frame = orthogonal_frame(
            unit.scene_graph.nodes[target_middle_root].world_transform.translation - wrist_template.translation,
            unit.scene_graph.nodes[target_pinky].world_transform.translation
            - unit.scene_graph.nodes[target_index].world_transform.translation,
        )
        source_frame = orthogonal_frame(
            source_head(source_middle_root) - source_head(wrist_bone),
            source_head(source_pinky) - source_head(source_index),
        )
        hand_delta = source_frame @ target_frame.transposed()

        wrist_world = unit.scene_graph.nodes[wrist_node].world_transform.copy()
        wrist_world = aligned_world_rotation(
            wrist_world, hand_delta, source_head_in_target(armature, wrist_bone, root_map)
        )
        desired_worlds[wrist_node] = wrist_world
        for _, source_segments, target_segments in finger_specs:
            for segment_index, (source_segment, target_segment) in enumerate(zip(source_segments, target_segments)):
                source_bone = find_source_bone(
                    armature, side_bone_candidates(source_segment, suffix)
                )
                target_name = f"j_{side}{target_segment}"
                target_index = node_by_name.get(target_name)
                if source_bone is None or target_index is None:
                    raise ValueError(f"Missing {side} finger pivot {source_segment} -> {target_name}")
                world = unit.scene_graph.nodes[target_index].world_transform.copy()
                finger_delta = hand_delta
                if BINDING_MODE in ("animation-compatible", "proportion-fk"):
                    # Palm alignment alone does not describe each finger's rest
                    # curl/splay. Use the real neighbouring joint, retaining the
                    # palm frame's roll as the reference for the shortest turn.
                    neighbour = min(segment_index + 1, 2)
                    previous = max(segment_index - 1, 0)
                    a, c = ((segment_index, neighbour) if segment_index < 2
                            else (previous, segment_index))
                    source_a = find_source_bone(armature, side_bone_candidates(source_segments[a], suffix))
                    source_c = find_source_bone(armature, side_bone_candidates(source_segments[c], suffix))
                    target_a = unit.scene_graph.nodes[node_by_name[f"j_{side}{target_segments[a]}"]].world_transform.translation
                    target_c = unit.scene_graph.nodes[node_by_name[f"j_{side}{target_segments[c]}"]].world_transform.translation
                    source_axis = (source_head(source_c) - source_head(source_a)).normalized()
                    target_axis = (target_c - target_a).normalized()
                    finger_delta = (hand_delta @ target_axis).rotation_difference(source_axis).to_matrix() @ hand_delta
                world = aligned_world_rotation(
                    world, finger_delta,
                    source_head_in_target(armature, source_bone, root_map),
                )
                desired_worlds[target_index] = world
                if target_segments[0] != "handthumb1":
                    inhand_name = f"j_{side}inhand{target_segments[0][4:-1]}"
                    inhand_index = node_by_name.get(inhand_name)
                    if inhand_index is not None and target_segment == target_segments[0]:
                        inhand_world = unit.scene_graph.nodes[inhand_index].world_transform.copy()
                        inhand_world = aligned_world_rotation(
                            inhand_world, hand_delta,
                            source_head_in_target(armature, source_bone, root_map),
                        )
                        desired_worlds[inhand_index] = inhand_world

    node_transforms = scene_graph_transform_records(unit, desired_worlds)
    return {
        "source_transforms": source_transforms,
        "node_transforms": node_transforms,
    }


def vertex_influences(mesh, bone_targets, palette_by_node, node_by_name, target_by_palette,
                      bind_transforms, source_bind_transforms=None):
    group_names = {group.index: group.name for group in mesh.vertex_groups}
    vertex_targets = np.zeros((len(mesh.data.vertices), 4), dtype=np.uint8)
    vertex_weights = np.zeros((len(mesh.data.vertices), 4), dtype=np.float32)
    arm_weights = np.zeros(len(mesh.data.vertices), dtype=np.float32)
    retargeted_positions = np.zeros((len(mesh.data.vertices), 3), dtype=np.float32)
    retargeted_linear = np.zeros((len(mesh.data.vertices), 3, 3), dtype=np.float32)
    source_to_target_coordinates = source_coordinate3()
    source_positions = np.asarray([
        (source_to_target_coordinates @ (mesh.matrix_world @ vertex.co))[:]
        for vertex in mesh.data.vertices
    ], dtype=np.float32)
    source_bind_transforms = source_bind_transforms or {}
    finger_width_scale = float(source_bind_transforms.get('__finger_width_scale', 1.0))
    hand_warp_values={}
    if '__hand_warps' in source_bind_transforms:
        from roshia_hand_fit import evaluate
        for side,warp in source_bind_transforms['__hand_warps'].items():
            warped,jacobians=evaluate(warp,source_positions)
            hand_warp_values[side]=(warped,jacobians,warp.get('finger_axes',{}))
    for vertex in mesh.data.vertices:
        merged = {}
        source_by_palette = {}
        arm_weight_by_palette = {}
        for assignment in vertex.groups:
            source_name = group_names.get(assignment.group)
            target_name = bone_targets.get(source_name)
            if target_name is None:
                continue
            palette = palette_by_node[node_by_name[target_name]]
            merged[palette] = merged.get(palette, 0.0) + assignment.weight
            transform = source_bind_transforms.get(source_name, bind_transforms[target_name])
            weighted = source_by_palette.setdefault(palette, [0.0, np.zeros((4, 4), dtype=np.float32)])
            weighted[0] += assignment.weight
            weighted[1] += assignment.weight * transform
            if (
                target_name.startswith(("j_left", "j_right"))
                and any(part in target_name for part in ("arm", "hand", "inhand", "finger", "thumb", "index", "middle", "ring", "pinky"))
                and not source_name.startswith(("shawl_base_L_", "shawl_base_R_"))
            ):
                arm_weight_by_palette[palette] = arm_weight_by_palette.get(palette, 0.0) + assignment.weight
        if not merged:
            palette = palette_by_node[node_by_name["j_hips"]]
            merged[palette] = 1.0
            source_by_palette[palette] = [1.0, bind_transforms["j_hips"]]
        source_position = source_positions[vertex.index]
        chosen = sorted(merged.items(), key=lambda item: item[1], reverse=True)[:4]
        total = sum(weight for _, weight in chosen)
        for i, (palette, weight) in enumerate(chosen):
            normalized_weight = weight / total if total else 1.0
            vertex_targets[vertex.index, i] = palette
            vertex_weights[vertex.index, i] = normalized_weight
            target_name = target_by_palette[palette]
            source_weight, weighted_transform = source_by_palette[palette]
            if total and source_weight:
                arm_weights[vertex.index] += (
                    normalized_weight * arm_weight_by_palette.get(palette, 0.0) / source_weight
                )
            transform = weighted_transform / source_weight if source_weight else bind_transforms[target_name]
            linear = transform[:3, :3]
            side = ('left' if target_name.startswith(('j_lefthand','j_leftinhand')) else
                    'right' if target_name.startswith(('j_righthand','j_rightinhand')) else None)
            if side in hand_warp_values:
                warped,jacobians,_=hand_warp_values[side]
                jac=jacobians[vertex.index]
                if np.linalg.det(jac)<=0:
                    raise ValueError(f'Hand fit folded vertex {vertex.index} ({side})')
                retargeted_positions[vertex.index]+=normalized_weight*warped[vertex.index]
                retargeted_linear[vertex.index]+=normalized_weight*np.linalg.inv(jac).T
                continue
            retargeted_positions[vertex.index] += normalized_weight * (
                linear @ source_position + transform[:3, 3]
            )
            try:
                retargeted_linear[vertex.index] += normalized_weight * np.linalg.inv(linear).T
            except np.linalg.LinAlgError:
                retargeted_linear[vertex.index] += normalized_weight * linear

        # The source mesh has unusually tapered digits. Apply a small radial
        # expansion around each fitted finger centreline while leaving palm,
        # wrist and the native animation pivots untouched. Blend at finger
        # webs using the actual post-pruning skin weights.
        digit_weights = {}
        for palette, weight in chosen:
            target_name = target_by_palette[palette]
            side = 'left' if target_name.startswith('j_lefthand') else (
                'right' if target_name.startswith('j_righthand') else None
            )
            if side is None:
                continue
            suffix = target_name[len(f'j_{side}hand'):]
            digit = next((name for name in ('thumb','index','middle','ring','pinky')
                          if suffix.startswith(name)
                          and suffix[len(name):] in ('1','2','3')), None)
            if digit is None or side not in hand_warp_values:
                continue
            digit_weights[(side,digit)] = digit_weights.get((side,digit),0.0) + (
                weight / total if total else 0.0
            )
        if digit_weights and finger_width_scale > 1.0:
            position = retargeted_positions[vertex.index].copy()
            width_normal = np.eye(3, dtype=np.float32)
            width_weight = 0.0
            correction = np.zeros(3, dtype=np.float32)
            for (side,digit), influence in digit_weights.items():
                axes = hand_warp_values[side][2]
                if digit not in axes or influence <= 0.0:
                    continue
                start, end = axes[digit]
                axis = np.asarray(end-start, dtype=np.float64)
                axis_length_squared = float(np.dot(axis,axis))
                if axis_length_squared <= 1e-12:
                    continue
                axis /= math.sqrt(axis_length_squared)
                scale = finger_width_scale
                projection = min(1.0,max(0.0,float(np.dot(position-start,axis))))
                center = np.asarray(start + axis*projection,dtype=np.float32)
                radial = position-center
                correction += influence * (scale-1.0) * radial
                radial_plane = np.eye(3,dtype=np.float32)-np.outer(axis,axis).astype(np.float32)
                width_normal += influence * (1.0/scale-1.0) * radial_plane
                width_weight += influence
            if width_weight > 0.0:
                retargeted_positions[vertex.index] += correction
                retargeted_linear[vertex.index] = width_normal @ retargeted_linear[vertex.index]
    result=(vertex_targets, vertex_weights, arm_weights, retargeted_positions, retargeted_linear)
    if source_bind_transforms.get('__wrist_continuity'):
        from costume_wrist_continuity import apply as join_wrists
        result=join_wrists(source_positions,result,target_by_palette,source_bind_transforms['__wrist_continuity'],mesh)
    hook=globals().get('postprocess_skin_influences')
    return hook(mesh,target_by_palette,result,source_bind_transforms) if hook else result


def validate_shared_root_binding(bind_transforms, source_bind_transforms):
    root = bind_transforms.get("j_hips")
    if root is None:
        raise ValueError("Rigid root binding is missing j_hips")
    for label, transforms in (("target", bind_transforms), ("source hand", source_bind_transforms)):
        for name, transform in transforms.items():
            if not np.array_equal(np.asarray(transform, dtype=np.float32), root):
                raise ValueError(f"Non-rigid bind transform would deform the source mesh: {label} {name}")


def image_pixels_for(material):
    if material and material.use_nodes:
        for node in material.node_tree.nodes:
            image = node.image if node.type == "TEX_IMAGE" else None
            if image and ("_D." in image.name or image.name.endswith("_D.png")):
                w, h = image.size
                # MMD imports can leave an empty external placeholder before
                # the packed duplicate is resolved. Do not sample a 0x0 image;
                # continue to the next diffuse node instead.
                if not w or not h:
                    continue
                pixels = np.empty(w * h * 4, dtype=np.float32)
                image.pixels.foreach_get(pixels)
                return w, h, pixels.reshape((h, w, 4)), image.colorspace_settings.name == "sRGB"
    if material:
        color = np.array(material.diffuse_color[:], dtype=np.float32)
    else:
        color = np.ones(4, dtype=np.float32)
    return 1, 1, color.reshape((1, 1, 4)), False


def sample_image(image_data, uv):
    width, height, pixels, srgb = image_data
    if width == 1 and height == 1:
        sampled = np.repeat(pixels.reshape((1, 4)), len(uv), axis=0)
        if srgb:
            rgb = sampled[:, :3]
            sampled[:, :3] = np.where(rgb <= 0.04045, rgb / 12.92,
                                      ((rgb + 0.055) / 1.055) ** 2.4)
        return sampled
    wrapped = uv - np.floor(uv)
    x = wrapped[:, 0] * width - 0.5
    y = wrapped[:, 1] * height - 0.5
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    tx = (x - x0)[:, None]
    ty = (y - y0)[:, None]
    x0 %= width
    y0 %= height
    x1 = (x0 + 1) % width
    y1 = (y0 + 1) % height
    a = pixels[y0, x0] * (1 - tx) + pixels[y0, x1] * tx
    b = pixels[y1, x0] * (1 - tx) + pixels[y1, x1] * tx
    sampled = np.clip(a * (1 - ty) + b * ty, 0.0, 1.0)
    if srgb:
        rgb = sampled[:, :3]
        sampled[:, :3] = np.where(rgb <= 0.04045, rgb / 12.92,
                                  ((rgb + 0.055) / 1.055) ** 2.4)
    return sampled


def encode_octahedral(normals):
    normals = np.asarray(normals, dtype=np.float64)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    invalid = (~np.isfinite(normals).all(axis=1)) | (~np.isfinite(lengths[:, 0])) | (lengths[:, 0] < 1e-10)
    if np.any(invalid):
        raise ValueError(f"Cannot oct-encode {int(invalid.sum())} invalid/zero direction vectors")
    n = normals / lengths
    denom = np.abs(n).sum(axis=1, keepdims=True)
    p = n[:, :2] / denom
    lower = n[:, 2] < 0
    if np.any(lower):
        px = p[lower, 0].copy()
        py = p[lower, 1].copy()
        p[lower, 0] = (1 - np.abs(py)) * np.where(px >= 0, 1, -1)
        p[lower, 1] = (1 - np.abs(px)) * np.where(py >= 0, 1, -1)
    return np.clip(p * 0.5 + 0.5, 0, 1).astype("<f2")


def stabilize_corner_normals(positions, normals):
    """Repair only missing corner normals using valid corners from that triangle.

    Opposing or degenerate smooth-face sums can collapse a few corner
    normals. Zero normals serialize as NaN in octahedral
    space and also make the tangent cross-product undefined. Keep all valid
    transported normals untouched; replace a collapsed corner with the mean
    of its valid triangle neighbors, falling back to the geometric normal.
    """
    positions = np.asarray(positions, dtype=np.float64).reshape((-1, 3, 3))
    result = np.asarray(normals, dtype=np.float64).reshape((-1, 3, 3)).copy()
    lengths = np.linalg.norm(result, axis=2)
    valid = np.isfinite(result).all(axis=2) & np.isfinite(lengths) & (lengths > 1e-10)
    if np.all(valid):
        result /= lengths[:, :, None]
        return result.reshape((-1, 3)), 0

    normalized = np.zeros_like(result)
    normalized[valid] = result[valid] / lengths[valid, None]
    repaired = 0
    for triangle_index in range(len(result)):
        invalid_corners = np.flatnonzero(~valid[triangle_index])
        if not len(invalid_corners):
            continue
        neighboring = normalized[triangle_index, valid[triangle_index]].sum(axis=0)
        neighbor_length = float(np.linalg.norm(neighboring))
        if np.isfinite(neighbor_length) and neighbor_length > 1e-10:
            fallback = neighboring / neighbor_length
        else:
            p = positions[triangle_index]
            fallback = np.cross(p[1] - p[0], p[2] - p[0])
            face_length = float(np.linalg.norm(fallback))
            if not np.isfinite(face_length) or face_length <= 1e-12:
                raise ValueError(f"Triangle {triangle_index} has invalid corner normals and degenerate geometry")
            fallback /= face_length
        normalized[triangle_index, invalid_corners] = fallback
        repaired += len(invalid_corners)
    return normalized.reshape((-1, 3)), repaired


def allocate_chunks(triangle_counts):
    active = [i for i, count in enumerate(triangle_counts) if count > 0]
    if len(active) > GEO_COUNT:
        raise ValueError("More material groups than target geometry slots")
    allocation = {i: 1 for i in active}
    remaining = GEO_COUNT - len(active)
    total = sum(triangle_counts[i] for i in active)
    exact = {i: remaining * triangle_counts[i] / total for i in active}
    for i in active:
        whole = math.floor(exact[i])
        allocation[i] += whole
    left = GEO_COUNT - sum(allocation.values())
    for i in sorted(active, key=lambda key: exact[key] - math.floor(exact[key]), reverse=True)[:left]:
        allocation[i] += 1
    return allocation


def collect_triangles(mesh, armature, bone_targets, palette_by_node, node_by_name,
                      target_by_palette, bind_transforms, arm_only,
                      source_bind_transforms=None, hide_cloak_blades=False):
    mesh.data.calc_loop_triangles()
    if not mesh.data.uv_layers.active:
        raise ValueError("Source model has no active UV map")
    corner_normals = getattr(mesh.data, "corner_normals", None)
    if corner_normals is None:
        raise ValueError("Blender did not expose the source corner normals")
    joint_indices, joint_weights, arm_weights, retargeted_positions, retargeted_linear = vertex_influences(
        mesh, bone_targets, palette_by_node, node_by_name, target_by_palette, bind_transforms,
        source_bind_transforms=source_bind_transforms,
    )
    spine_palettes = np.asarray(
        [palette for palette, target_name in target_by_palette.items()
         if target_name.startswith("j_spine")],
        dtype=np.uint8,
    )
    shoulder_palettes = np.asarray(
        [palette for palette, target_name in target_by_palette.items()
         if target_name in ("j_leftshoulder", "j_rightshoulder")],
        dtype=np.uint8,
    )
    spine_weights = np.zeros(len(mesh.data.vertices), dtype=np.float32)
    if len(spine_palettes):
        spine_weights = np.where(
            np.isin(joint_indices, spine_palettes), joint_weights, 0.0
        ).sum(axis=1)
    shoulder_weights = np.zeros(len(mesh.data.vertices), dtype=np.float32)
    if len(shoulder_palettes):
        shoulder_weights = np.where(
            np.isin(joint_indices, shoulder_palettes), joint_weights, 0.0
        ).sum(axis=1)
    print("ARM_WEIGHT_STATS " + json.dumps({
        "max": float(arm_weights.max()),
        "p50": float(np.quantile(arm_weights, 0.50)),
        "p90": float(np.quantile(arm_weights, 0.90)),
        "vertices_over_005": int(np.count_nonzero(arm_weights > 0.05)),
        "mapped_arm_bones": sum(1 for value in bone_targets.values() if value.startswith(("j_left", "j_right"))),
    }))
    mat_count = len(mesh.data.materials)
    tri_count = len(mesh.data.loop_triangles)
    tri_material = np.empty(tri_count, dtype=np.int16)
    tri_vertices = np.empty((tri_count, 3), dtype=np.int32)
    tri_uv = np.empty((tri_count, 3, 2), dtype=np.float32)
    tri_normals = np.empty((tri_count, 3, 3), dtype=np.float32)
    tri_keep_arm = np.zeros(tri_count, dtype=bool)
    tri_hide_cloak_blades = np.zeros(tri_count, dtype=bool)
    tri_hide_tail_cards = np.zeros(tri_count, dtype=bool)
    group_names = {group.index: group.name for group in mesh.vertex_groups}
    tail_weight = np.zeros(len(mesh.data.vertices), dtype=np.float32)
    for vertex in mesh.data.vertices:
        tail_weight[vertex.index] = sum(
            assignment.weight for assignment in vertex.groups
            if group_names.get(assignment.group, "").startswith("tail_base_")
        )
    coordinate3 = source_coordinate3()
    source_positions = np.asarray([
        (coordinate3 @ (mesh.matrix_world @ vertex.co))[:]
        for vertex in mesh.data.vertices
    ], dtype=np.float32)
    upper_arm_weight = np.zeros((len(mesh.data.vertices), 2), dtype=np.float32)
    for vertex in mesh.data.vertices:
        for assignment in vertex.groups:
            source_name = group_names.get(assignment.group)
            target_name = bone_targets.get(source_name)
            if target_name == "j_leftarm":
                upper_arm_weight[vertex.index, 0] += assignment.weight
            elif target_name == "j_rightarm":
                upper_arm_weight[vertex.index, 1] += assignment.weight
    upper_arm_cut_ok = np.ones(len(mesh.data.vertices), dtype=bool)
    for side_index, suffix in enumerate((".L", ".R")):
        upper_arm = find_source_bone(armature, side_bone_candidates("腕", suffix))
        forearm = find_source_bone(
            armature, side_bone_candidates("ひじ", suffix) + ("肘" + suffix, "左肘" if suffix == ".L" else "右肘")
        )
        if upper_arm is None or forearm is None:
            continue
        axis_start = coordinate3 @ (armature.matrix_world @ upper_arm.head_local)
        axis_end = coordinate3 @ (armature.matrix_world @ forearm.head_local)
        axis = axis_end - axis_start
        axis_length_squared = float(axis.length_squared)
        if axis_length_squared < 1e-8:
            continue
        axis_start_np = np.asarray(axis_start, dtype=np.float32)
        axis_np = np.asarray(axis, dtype=np.float32)
        projection = ((source_positions - axis_start_np) @ axis_np) / axis_length_squared
        influenced = upper_arm_weight[:, side_index] >= 0.05
        upper_arm_cut_ok[influenced] &= projection[influenced] >= 0.10
    cloak_blade_bones = {
        name for name in bone_targets
        if (parts := name.split("_"))[:2] == ["clothes", "cloak"]
        and len(parts) >= 6 and parts[2] in ("L", "R")
        and parts[3] in ("d", "e", "f", "g") and parts[4] == "01"
        and parts[-1] == "jnt"
    }
    if hide_cloak_blades and not cloak_blade_bones:
        raise ValueError("--hide-cloak-blades was set, but no cloak blade bones were found")
    cloak_blade_weight_by_vertex = np.zeros(len(mesh.data.vertices), dtype=np.float32)
    cloak_blade_weight_stats = {name: [0.0, 0] for name in cloak_blade_bones}
    if hide_cloak_blades:
        for vertex in mesh.data.vertices:
            for assignment in vertex.groups:
                source_name = group_names.get(assignment.group)
                if source_name in cloak_blade_weight_stats:
                    stats = cloak_blade_weight_stats[source_name]
                    stats[0] += assignment.weight
                    stats[1] += 1
                    cloak_blade_weight_by_vertex[vertex.index] += assignment.weight
    uv_layer = mesh.data.uv_layers.active.data
    coordinate_normal_matrix = source_coordinate3().normalized()
    face_vertices={v for p in mesh.data.polygons if p.material_index==0 for v in p.vertices}
    face_points=source_positions[list(face_vertices)]
    face_center=(face_points.min(axis=0)+face_points.max(axis=0))*.5
    face_extent=np.maximum(face_points.max(axis=0)-face_points.min(axis=0),1e-5)
    for ti, triangle in enumerate(mesh.data.loop_triangles):
        tri_material[ti] = triangle.material_index
        arm_corner = []
        arm_axis_corner = []
        spine_corner = []
        shoulder_corner = []
        for ci, loop_index in enumerate(triangle.loops):
            loop = mesh.data.loops[loop_index]
            vertex_index = loop.vertex_index
            tri_vertices[ti, ci] = vertex_index
            uv = uv_layer[loop_index].uv
            tri_uv[ti, ci] = (float(uv.x), float(uv.y))
            normal = corner_normals[loop_index].vector
            source_normal = mesh.matrix_world.to_3x3().inverted().transposed() @ normal
            source_normal = coordinate_normal_matrix @ source_normal
            source_normal.normalize()
            if triangle.material_index==0 and source_normal.y>0:
                # Broad face shading normals soften nose/socket self-shading
                # without erasing geometry or overexposing the texture.
                pos=source_positions[vertex_index]
                broad=Vector(((pos[0]-face_center[0])/face_extent[0],1.,
                              (pos[2]-face_center[2])/face_extent[2]*.6)).normalized()
                source_normal=source_normal.lerp(broad,globals().get('FACE_NORMAL_BLEND',.75)).normalized()
            tri_normals[ti, ci] = retargeted_linear[vertex_index] @ np.asarray(source_normal, dtype=np.float32)
            arm_corner.append(arm_weights[vertex_index])
            arm_axis_corner.append(upper_arm_cut_ok[vertex_index])
            spine_corner.append(spine_weights[vertex_index])
            shoulder_corner.append(shoulder_weights[vertex_index])
        if hide_cloak_blades:
            triangle_vertices = tri_vertices[ti]
            tri_hide_cloak_blades[ti] = (
                int((cloak_blade_weight_by_vertex[triangle_vertices] >= 0.5).sum()) >= 2
            )
        if (triangle.material_index < len(mesh.data.materials)
                and mesh.data.materials[triangle.material_index]
                and mesh.data.materials[triangle.material_index].name == "发Alpha"):
            tail_corner = tail_weight[tri_vertices[ti]]
            # Any meaningful tail-bone influence identifies a source fur card.
            # Keeping partially weighted cards leaves transparent patches on
            # the cape in-game; the opaque tail shell replaces those cards.
            tri_hide_tail_cards[ti] = float(tail_corner.max()) >= 0.20
        if (not tri_hide_cloak_blades[ti] and min(arm_corner) >= 0.50
                and sum(arm_corner) / 3.0 >= 0.50
                and max(spine_corner) <= 0.30 and max(shoulder_corner) <= 0.30
                and all(arm_axis_corner)):
            tri_keep_arm[ti] = True

    if hide_cloak_blades:
        print("CLOAK_BLADE_FILTER " + json.dumps({
            "source_bones": sorted(cloak_blade_bones),
            "weight_stats": cloak_blade_weight_stats,
            "primary_weight_vertices": int(np.count_nonzero(cloak_blade_weight_by_vertex >= 0.5)),
            "removed_triangles": int(tri_hide_cloak_blades.sum()),
        }, ensure_ascii=False))

    grouped = []
    for material_index in range(mat_count):
        material = mesh.data.materials[material_index] if material_index < mat_count else None
        material_name = material.name if material else ""
        skip_material = any(token.casefold() in material_name.casefold()
                            for token in SKIP_MATERIAL_NAMES)
        indices = (np.empty(0, dtype=np.int64) if skip_material
                   else np.flatnonzero((tri_material == material_index)
                                       & ~tri_hide_cloak_blades & ~tri_hide_tail_cards))
        if arm_only:
            excluded = any(token.casefold() in material_name.casefold()
                           for token in FIRST_PERSON_EXCLUDED_MATERIAL_NAMES)
            indices = (np.empty(0, dtype=np.int64) if excluded
                       else indices[tri_keep_arm[indices]])
        grouped.append({
            "triangles": indices,
            "vertices": tri_vertices,
            "uv": tri_uv,
            "normals": tri_normals,
            "joint_indices": joint_indices,
            "joint_weights": joint_weights,
            "retargeted_positions": retargeted_positions,
            "image": image_pixels_for(material),
            "material_name": material_name,
        })
    alpha_tail_triangles = (tri_material == next((i for i, m in enumerate(mesh.data.materials)
                                                  if m and m.name == "发Alpha"), -1))
    tail_weighted_alpha = alpha_tail_triangles & (tail_weight[tri_vertices].max(axis=1) >= 0.20)
    print("TAIL_CARD_FILTER " + json.dumps({
        "material": "发Alpha", "removed_triangles": int(tri_hide_tail_cards.sum()),
        "tail_weighted_alpha_triangles": int(tail_weighted_alpha.sum()),
        "remaining_tail_weighted_alpha_triangles": int((tail_weighted_alpha & ~tri_hide_tail_cards).sum()),
        "tail_weighted_vertices": int(np.count_nonzero(tail_weight >= 0.45)),
        "retained_tail_core_material": "RoshiaTailCore",
    }, ensure_ascii=False))
    return grouped


def packed_tangent_frame(positions, normals, uv):
    """Stingray semantic 4 is oct(T), oct(-B), NOT vertex RGBA."""
    # Thin authored triangles can have a UV tangent almost parallel to their
    # smooth normal. Float32 projection loses its perpendicular component;
    # normalizing that cancellation residue produces a nonorthogonal TBN.
    # Keep the computation stable, then pack to the unchanged native format.
    p = np.asarray(positions,dtype=np.float64).reshape((-1, 3, 3))
    t = np.asarray(uv,dtype=np.float64).reshape((-1, 3, 2))
    normals=np.asarray(normals,dtype=np.float64)
    normal_lengths=np.linalg.norm(normals,axis=1,keepdims=True)
    if (not np.isfinite(normals).all()) or np.any(normal_lengths < 1e-10):
        raise ValueError("Tangent frame received invalid normals; stabilize source corner normals first")
    normals/=normal_lengths
    e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    d1, d2 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
    det = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
    valid = np.abs(det) > 1e-12
    inv = np.divide(1.0, det, out=np.zeros_like(det), where=valid)
    tangent = (e1 * d2[:, 1, None] - e2 * d1[:, 1, None]) * inv[:, None]
    bitangent = (e2 * d1[:, 0, None] - e1 * d2[:, 0, None]) * inv[:, None]
    tangent = np.repeat(tangent, 3, axis=0)
    bitangent = np.repeat(bitangent, 3, axis=0)
    raw_length=np.linalg.norm(tangent,axis=1,keepdims=True)
    tangent -= normals * np.sum(tangent * normals, axis=1, keepdims=True)
    length = np.linalg.norm(tangent, axis=1, keepdims=True)
    helper = np.zeros_like(normals)
    helper[:, 2] = 1
    helper[np.abs(normals[:, 2]) > 0.9] = (0, 1, 0)
    fallback = np.cross(helper, normals)
    tangent = np.where(length > np.maximum(1e-12,raw_length*np.finfo(np.float32).eps), tangent, fallback)
    tangent_length = np.linalg.norm(tangent, axis=1, keepdims=True)
    if (not np.isfinite(tangent).all()) or np.any(tangent_length < 1e-10):
        raise ValueError("Could not construct a finite orthogonal tangent direction")
    tangent /= tangent_length
    cross_nt = np.cross(normals, tangent)
    cross_length = np.linalg.norm(cross_nt, axis=1, keepdims=True)
    if (not np.isfinite(cross_nt).all()) or np.any(cross_length < 1e-10):
        raise ValueError("Could not construct a finite bitangent direction")
    cross_nt /= cross_length
    handedness = np.where(np.sum(cross_nt * bitangent, axis=1, keepdims=True) < 0, -1, 1)
    bitangent = cross_nt * handedness
    return np.column_stack((encode_octahedral(tangent), encode_octahedral(-bitangent))).astype('<f2')


def bounds_sphere(bounds):
    minimum, maximum = np.asarray(bounds[:3]), np.asarray(bounds[3:6])
    center = (minimum + maximum) * 0.5
    # Include half-float quantization and a small animated surface margin.
    radius = float(np.linalg.norm(maximum - minimum) * 0.5 + 0.02)
    return np.concatenate((center, [radius])).astype('<f4')


def make_geometry(group, source_triangles, material_index, slot_id):
    triangles = group["triangles"][source_triangles]
    if len(triangles) == 0:
        raise ValueError("Empty geometry chunk")
    # Match the shipped, working reference meshes: winding agrees with normals.
    # Only a handedness-changing coordinate conversion needs an index swap.
    order = np.array([0, 2, 1] if source_coordinate3().determinant() < 0
                     else [0, 1, 2], dtype=np.int64)
    vertex_ids = group["vertices"][triangles][:, order].reshape(-1)
    uv = group["uv"][triangles][:, order].reshape((-1, 2)).copy()
    # Blender samples image UVs from bottom-left; Stingray/DDS uses top-left.
    # PNG writing already puts the top image row first, so convert V exactly once.
    uv[:, 1] = 1.0 - uv[:, 1]
    normals = group["normals"][triangles][:, order].reshape((-1, 3)).copy()
    positions = group["retargeted_positions"][vertex_ids]
    face_overlay_depth = globals().get("FACE_OVERLAY_DEPTH", {1: 0.0015, 2: 0.0018, 3: 0.0010, 5: 0.0012})
    if material_index in face_overlay_depth:
        # These source islands sit just above the face. Keep their authored
        # opaque diffuse materials, while a small normal offset prevents the
        # native depth buffer from hiding the iris/sclera/lash layers.
        positions = positions + normals * np.float32(face_overlay_depth[material_index])
    normals, repaired_normals = stabilize_corner_normals(positions, normals)
    if repaired_normals:
        print("NORMAL_FALLBACK " + json.dumps({
            "material_index": int(material_index), "geometry_slot": int(slot_id),
            "repaired_corners": int(repaired_normals),
            "method": "same-triangle-valid-corner-average-or-geometric-normal",
        }))
    tangent_frame = packed_tangent_frame(positions, normals, uv)
    joints = group["joint_indices"][vertex_ids]
    weights = group["joint_weights"][vertex_ids]

    # Hair/eyelashes/eye highlights are source alpha cards; render both faces.
    # Reverse normals too, so the second side has a physically valid TBN frame.
    if material_is_alpha(material_index, group['material_name']) or group.get('double_sided_garment', False):
        reverse = np.arange(len(vertex_ids)).reshape((-1, 3))[:, [0, 2, 1]].reshape(-1)
        positions = np.concatenate((positions, positions[reverse]))
        normals = np.concatenate((normals, -normals[reverse]))
        uv = np.concatenate((uv, uv[reverse]))
        joints = np.concatenate((joints, joints[reverse]))
        weights = np.concatenate((weights, weights[reverse]))
        tangent_frame = packed_tangent_frame(positions, normals, uv)

    n = len(positions)
    if n > 65535:
        raise ValueError('Geometry exceeds uint16 index range after double-sided expansion')
    # Dense uncovered fingers lose up to 0.55 mm at native world height when
    # stored as HALF4. The Ink Mist profile keeps their fitted surface in
    # FLOAT3; skin matrices, contact nodes and all other streams stay unchanged.
    float_positions = globals().get('POSITION_FLOAT32', False)
    position_stream = (positions.astype('<f4').tobytes(), 12) if float_positions else (
        np.column_stack((positions, np.ones(n, dtype=np.float32))).astype('<f2').tobytes(), 8)
    streams = [
        (tangent_frame.tobytes(), 8),
        position_stream,
        (encode_octahedral(normals).tobytes(), 4),
        (uv.astype("<f2").tobytes(), 4),
        (weights.astype("<f2").tobytes(), 8),
        (joints.astype(np.uint8).tobytes(), 4),
    ]
    index_data = np.arange(n, dtype="<u2").tobytes()
    minimum = positions.min(axis=0)
    maximum = positions.max(axis=0)
    bounds = np.concatenate((minimum, maximum)).astype(np.float32)
    return {
        "streams": streams,
        "index_data": index_data,
        "vertices": n,
        "indices": n,
        "bounds": bounds,
        "material_index": material_index,
        "is_alpha": material_is_alpha(material_index, group["material_name"]),
        "slot_id": slot_id,
        "triangle_count": n // 3,
        "channels": [(4, 17, 0, 0), (0, 2 if float_positions else 17, 0, 1), (1, 15, 0, 2),
                     (5, 15, 0, 3), (8, 17, 0, 4), (7, 19, 0, 5)],
    }


def geometry_positions(geometry):
    """Read the generated position channel using its actual declared format."""
    _, kind, _, stream_index = next(c for c in geometry['channels'] if c[0] == 0)
    payload, stride = geometry['streams'][stream_index]
    if (kind, stride) == (2, 12):
        return np.frombuffer(payload, '<f4').reshape(-1, 3)
    if (kind, stride) == (17, 8):
        return np.frombuffer(payload, '<f2').reshape(-1, 4)[:, :3]
    raise ValueError(('Unsupported POSITION channel', kind, stride))


def serialize_geometry(geometry):
    out = bytearray()
    out += u32(1)
    out += u32(len(geometry["streams"]))
    for payload, stride in geometry["streams"]:
        out += u32(len(payload)) + payload
        out += u32(0) + u32(0) + u32(geometry["vertices"]) + u32(stride)
    out += u32(len(geometry["channels"]))
    for component, channel_type, channel_set, stream_index in geometry["channels"]:
        out += u32(component) + u32(channel_type) + u32(channel_set) + u32(stream_index) + b"\x00"
    out += u32(0) + u32(0) + u32(0) + u32(geometry["indices"])
    out += u32(len(geometry["index_data"])) + geometry["index_data"]
    out += u32(1) + u32(0) + u32(0) + u32(geometry["triangle_count"]) + u32(0)
    out += geometry["bounds"].astype("<f4").tobytes() + bounds_sphere(geometry["bounds"]).tobytes()
    out += u32(1) + u32(geometry["slot_id"])
    out += u32(0)
    return bytes(out)


def build_geometry_chunks(mesh, armature, unit, node_by_name, arm_only, prefix, material_ids,
                          translation_only=False, matrix_targets=(), hand_retarget_mode="legacy",
                          dynamic_rig=None, hide_cloak_blades=False):
    skin = unit.skins[0]
    palette_by_node = {node_index: palette for palette, node_index in enumerate(skin.node_indices)}
    bone_targets = source_bone_targets(
        armature, node_by_name,
        dynamic_rig.get("source_to_target") if dynamic_rig else None,
    )
    required_targets = [
        "j_hips", "j_spine", "j_spine1", "j_spine2", "j_neck", "j_head",
        "j_leftshoulder", "j_leftarm", "j_leftforearm", "j_lefthand",
        "j_rightshoulder", "j_rightarm", "j_rightforearm", "j_righthand",
        "j_leftupleg", "j_leftleg", "j_leftfoot", "j_rightupleg", "j_rightleg", "j_rightfoot",
    ]
    for side in ("left", "right"):
        for finger in ("handthumb1", "handthumb2", "handthumb3"):
            required_targets.append(f"j_{side}{finger}")
        toe_target = f"j_{side}toebase"
        if toe_target in bone_targets.values():
            required_targets.append(toe_target)
        for finger in ("handindex1", "handindex2", "handindex3",
                       "handmiddle1", "handmiddle2", "handmiddle3",
                       "handring1", "handring2", "handring3",
                       "handpinky1", "handpinky2", "handpinky3"):
            required_targets.append(f"j_{side}{finger}")
    for target in required_targets:
        if target not in node_by_name or node_by_name[target] not in palette_by_node:
            raise ValueError(f"Target skeleton is missing weighted node {target}")
    if dynamic_rig:
        bone_targets.update(dynamic_rig["source_to_target"])
    bind_transforms = target_bind_transforms(
        armature, node_by_name, unit, translation_only=translation_only,
        matrix_targets=matrix_targets,
    )
    if dynamic_rig:
        bind_transforms.update(dynamic_rig["bind_transforms"])
    hand_rig = (
        dynamic_rig["hand_rig"] if dynamic_rig and "hand_rig" in dynamic_rig
        else source_hand_bind_transforms(
            armature, bone_targets, node_by_name, unit,
            root_map=Matrix(bind_transforms["j_hips"].tolist()),
        )
    )
    if dynamic_rig and "geometry_bind_transforms" in dynamic_rig:
        bind_transforms.update(dynamic_rig["geometry_bind_transforms"])
    else:
        validate_shared_root_binding(bind_transforms, hand_rig["source_transforms"])
    target_by_palette = {
        palette_by_node[node_by_name[name]]: name for name in bind_transforms
        if name in node_by_name and node_by_name[name] in palette_by_node
    }
    groups = collect_triangles(
        mesh, armature, bone_targets, palette_by_node, node_by_name,
        target_by_palette, bind_transforms, arm_only,
        source_bind_transforms=hand_rig["source_transforms"],
        hide_cloak_blades=hide_cloak_blades,
    )
    counts = [len(group["triangles"]) * (2 if group.get('double_sided_garment', False) else 1)
              for group in groups]
    allocation = allocate_chunks(counts)
    output = []
    chunk_materials = []
    for material_index, chunk_count in allocation.items():
        indices = groups[material_index]["triangles"]
        partitions = np.array_split(np.arange(len(indices), dtype=np.int32), chunk_count)
        for partition in partitions:
            geometry = make_geometry(
                groups[material_index], partition, material_index,
                IDString32.from_str(f"{prefix}_slot_{len(output):02d}").ID,
            )
            output.append(geometry)
            chunk_materials.append(material_index)
    if len(output) != GEO_COUNT:
        raise ValueError(f"Expected {GEO_COUNT} geometry chunks, got {len(output)}")
    return output, chunk_materials


def write_png(path, pixels):
    """Write the same bottom-up RGBA samples used by the source UV sampler."""
    rgba = np.rint(np.clip(pixels, 0, 1) * 255).astype(np.uint8)
    height, width = rgba.shape[:2]
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xffffffff)
    rows = b"".join(b"\0" + row.tobytes() for row in rgba[::-1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def write_texture(folder, resource_name, pixels, dxgi_format):
    """Native v67 Oodle texture with inline low mips and tiled high mip stream."""
    basename = resource_name.rsplit("/", 1)[-1]
    png = folder / "source_textures" / (basename + ".png")
    write_png(png, pixels)
    dds_dir = folder / "source_textures" / "dds"
    dds_dir.mkdir(parents=True, exist_ok=True)
    height, width = pixels.shape[:2]
    width = min(4096, max(512, 1 << (width - 1).bit_length()))
    height = min(4096, max(512, 1 << (height - 1).bit_length()))
    command = [str(ROOT / "tools" / "texconv.exe"), "-nologo", "-y", "-dx10", "-f", dxgi_format,
               "-w", str(width), "-h", str(height), "-m", "0", "-o", str(dds_dir), str(png)]
    if dxgi_format.endswith("_SRGB"):
        # PNG samples are already sRGB encoded; decode before the sRGB BC output conversion.
        command.insert(1, "-srgbi")
    completed = subprocess.run(command, capture_output=True, text=True, errors="replace")
    if completed.returncode:
        raise RuntimeError("texconv failed: " + completed.stdout + completed.stderr)
    dds = (dds_dir / (basename + ".dds")).read_bytes()
    if dds[:4] != b"DDS " or dds[84:88] != b"DX10":
        raise ValueError("Texture encoder did not produce a DX10 DDS")
    stream_relative = f"data/at/{hash64(resource_name + '_stream'):016x}.stream"
    stream = folder / stream_relative
    stream.parent.mkdir(parents=True, exist_ok=True)
    # This footer is a texture profile identifier, not a DDS CRC.
    profile = (0xae01e4bc if resource_name.endswith('_em') else
               {'BC1_UNORM_SRGB':0xa88c22b7,'BC3_UNORM_SRGB':0x6bd03744,
                'BC5_UNORM':0x3390aba5,'BC1_UNORM':0xe514d1dc}[dxgi_format])
    body, tail, high_mips = pack_texture(dds, stream_relative, Oodle(OODLE_DLL),profile)
    stream.write_bytes(high_mips)
    primary = (u64(hash64("texture")) + u64(hash64(resource_name))
               + u32(1) + u32(0) + u32(0) + b"\x00"
               + u32(len(body)) + b"\x01" + u32(len(tail)) + body + tail)
    (folder / (basename + ".texture")).write_bytes(primary)
    # Verify resource wrapper, stream identity, dimensions, and complete mip chain.
    if primary[-31:].split(b"\0")[0].decode() != stream_relative or stream.read_bytes() != high_mips:
        raise ValueError("Native texture stream round-trip failed")
    stored_height, stored_width = struct.unpack_from("<II", dds, 12)
    if (stored_width, stored_height) != (width, height):
        raise ValueError("Native texture dimensions do not match DDS")
    mip_count = struct.unpack_from("<I", dds, 28)[0]
    block_bytes = 8 if dxgi_format.startswith("BC1_") else 16
    expected_bytes = 148 + sum(max(1, ((width >> mip) + 3) // 4)
                               * max(1, ((height >> mip) + 3) // 4) * block_bytes
                               for mip in range(mip_count))
    if len(dds) != expected_bytes or mip_count != max(width, height).bit_length():
        raise ValueError("Native DDS mip chain is incomplete")
    return {"resource": {"type": "texture", "name": resource_name}, "primary": basename + ".texture",
            "stream": stream_relative, "png": str(png), "format": dxgi_format,
            "width": width, "height": height}


def write_native_materials(folder, asset_prefix, mesh, geometries):
    from roshia_native_materials import providers,pbr_fill,FACE_FILL,FACE_DIFFUSE,ROUGHNESS,set_cutoff,face_texture_pair
    textures, materials, resources = [], [], {}
    if any(g['material_index'] in FACE_FILL for g in geometries):
        provider,parent,shader_materials=providers(sys.modules[__name__],folder,asset_prefix)
        materials.extend(shader_materials)
    alpha_shader = f"{RESOURCE_ROOT}/{asset_prefix}_alpha_shader"
    alpha_parent = f"{RESOURCE_ROOT}/{asset_prefix}_alpha_parent"
    if any(g['is_alpha'] for g in geometries):
        materials.append(copy_shader_material(folder, alpha_parent, 'qianxia_shader_345c8a27a643dc8e.material'))
        materials.append(copy_shader_material(folder, alpha_shader, 'qianxia_shader_e03ea781c4162268.material'))
        shader_stream=folder/materials[-1]['stream']
        shader_data=bytearray(shader_stream.read_bytes())
        shader_offset=struct.unpack_from('<I',shader_data,4)[0]
        struct.pack_into('<Q',shader_data,shader_offset+12,hash64(alpha_parent))
        shader_stream.write_bytes(shader_data)
    nm_name = f"{RESOURCE_ROOT}/{asset_prefix}_neutral_nm"
    orm_name = f"{RESOURCE_ROOT}/{asset_prefix}_neutral_orm"
    textures.append(write_texture(folder, nm_name, np.array([[[128/255, 128/255, 1, 1]]]), "BC5_UNORM"))
    textures.append(write_texture(folder, orm_name, np.array([[[1, 0.85, 0, 1]]]), "BC1_UNORM"))
    for index in sorted({geometry["material_index"] for geometry in geometries}):
        material = mesh.data.materials[index]
        alpha = material_is_alpha(index, material.name)
        channel = "bca" if alpha else "bc"
        resource = f"{RESOURCE_ROOT}/{asset_prefix}_material_{index}"
        texture_name = resource + "_" + channel
        _, _, pixels, srgb = image_pixels_for(material)
        pixels = pixels.copy()
        if not srgb:
            rgb = pixels[:, :, :3]
            pixels[:, :, :3] = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.maximum(rgb, 0) ** (1/2.4) - 0.055)
        if not alpha:
            pixels[:, :, 3] = 1
        if index in FACE_DIFFUSE:
            pixels,emission=face_texture_pair(index,pixels)
        textures.append(write_texture(folder, texture_name, pixels, "BC3_UNORM_SRGB" if alpha else "BC1_UNORM_SRGB"))
        template = "qianxia_material_10.material" if alpha else "qianxia_material_0.material"
        own_orm=f'{resource}_orm'
        details=globals().get('material_surface_maps')
        surface=details(mesh,index) if details else {}
        own_nm=nm_name
        if 'nm' in surface:
            own_nm=resource+'_nm'
            textures.append(write_texture(folder,own_nm,surface['nm'],'BC5_UNORM'))
        textures.append(write_texture(folder,own_orm,surface.get('orm',np.array([[[1,ROUGHNESS.get(index,.85),0,1]]])),'BC1_UNORM'))
        if index in FACE_FILL:
            em_name=resource+'_em'
            textures.append(write_texture(folder,em_name,emission,'BC1_UNORM'))
            info=pbr_fill(sys.modules[__name__],folder,resource,provider,parent,{'bc':texture_name,'em':em_name,'nm':own_nm,'orm':own_orm},FACE_FILL[index])
        else:
            info = write_material(folder, resource, template, {channel: texture_name, "nm": own_nm,"orm": own_orm})
        if alpha:
            stream = folder / info['stream']
            data = bytearray(stream.read_bytes())
            material_offset = struct.unpack_from('<I', data, 4)[0]
            struct.pack_into('<Q', data, material_offset + 4, hash64(alpha_shader))
            struct.pack_into('<Q', data, material_offset + 12, hash64(alpha_parent))
            stream.write_bytes(data)
            set_cutoff(stream,0.15 if index==13 else 0.28)
        materials.append(info)
        resources[index] = resource
    return resources, materials, textures


def copy_shader_material(folder, resource_name, template):
    header = bytearray((TEMPLATE / template).read_bytes())
    original = header[38:68].split(b'\0', 1)[0].decode('ascii')
    relative = f"data/am/{hash64(resource_name + '_stream'):016x}"
    target = folder / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((TEMPLATE / original).read_bytes())
    struct.pack_into('<Q', header, 8, hash64(resource_name))
    header[38:68] = relative.encode().ljust(30, b'\0')
    primary = resource_name.rsplit('/', 1)[-1] + '.material'
    (folder / primary).write_bytes(header)
    return {'resource': {'type': 'material', 'name': resource_name}, 'primary': primary, 'stream': relative}


def patch_material_stream(template_material, replacements, stream_out):
    primary = TEMPLATE / template_material
    header = primary.read_bytes()
    stream_name = header[38:68].split(b"\0", 1)[0].decode("ascii")
    stream_path = TEMPLATE / pathlib.Path(stream_name)
    data = bytearray(stream_path.read_bytes())
    material_offset = struct.unpack_from("<I", data, 4)[0]
    offset = material_offset
    offset += 4  # local material name
    offset += 16  # two parent material ids
    unk_count = struct.unpack_from("<I", data, offset)[0]
    offset += 4 + unk_count * 4
    texture_count = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    replacement_hashes = {hash32(channel): name for channel, name in replacements.items()}
    patched = set()
    for _ in range(texture_count):
        channel = struct.unpack_from("<I", data, offset)[0]
        texture_offset = offset + 4
        if channel in replacement_hashes:
            struct.pack_into("<Q", data, texture_offset, hash64(replacement_hashes[channel]))
            patched.add(channel)
        offset += 12
    if patched != set(replacement_hashes):
        raise ValueError(f"Could not find all texture channels in {template_material}: {set(replacement_hashes) - patched}")
    stream_out.parent.mkdir(parents=True, exist_ok=True)
    stream_out.write_bytes(data)
    return data


def write_material(folder, resource_name, template_material, replacements):
    stream_key = f"{hash64(resource_name + '_stream'):016x}"
    stream_relative = f"data/am/{stream_key}"
    stream_path = folder / stream_relative
    patch_material_stream(template_material, replacements, stream_path)
    stream_name = stream_relative.encode("ascii")
    if len(stream_name) > 30:
        raise ValueError("Material stream path exceeds the native 30-byte field")
    primary = (
        u64(hash64("material")) + u64(hash64(resource_name))
        + u32(1) + u32(0) + u32(0) + b"\x01"
        + u32(30) + u32(1) + b"\x00"
        + stream_name.ljust(30, b"\x00")
    )
    if len(primary) != 68:
        raise ValueError("Incorrect native material header size")
    primary_path = folder / (resource_name.rsplit("/", 1)[-1] + ".material")
    primary_path.write_bytes(primary)
    return {
        "resource": {"type": "material", "name": resource_name},
        "primary": primary_path.name,
        "stream": stream_relative,
    }


def matrix_column_major(matrix):
    return [float(matrix[row][column]) for column in range(4) for row in range(4)]


def patch_dynamic_rig(raw, unit_info, delta, dynamic_rig):
    if not dynamic_rig:
        return
    rig_nodes = dict(dynamic_rig.get("node_transforms", {}))
    rig_nodes.update(dynamic_rig.get("hand_node_transforms", {}))
    scene_start = unit_info["scene_graph_start"] + delta
    graph = unit_info["scene_graph"]
    node_count = len(graph.nodes)
    local_start = scene_start + 4
    world_start = local_start + node_count * 60
    parent_start = world_start + node_count * 64
    name_start = parent_start + node_count * 4
    for node_index, alias in dynamic_rig.get('node_renames', {}).items():
        struct.pack_into('<I', raw, name_start + node_index * 4, IDString32.from_str(alias).ID)
    for node_index, record in rig_nodes.items():
        local = record["local"]
        rotation = local.to_3x3()
        # Stingray stores a parent-space position, not an inverse-rotated one.
        position = local.translation
        local_offset = local_start + node_index * 60
        rotation_values = [float(rotation[row][column])
                           for column in range(3) for row in range(3)]
        struct.pack_into("<9f", raw, local_offset, *rotation_values)
        struct.pack_into("<3f", raw, local_offset + 36, *position)
        struct.pack_into("<3f", raw, local_offset + 48, 1.0, 1.0, 1.0)
        struct.pack_into("<16f", raw, world_start + node_index * 64,
                         *matrix_column_major(record["world"]))
        struct.pack_into("<HH", raw, parent_start + node_index * 4,
                         int(ParentType.INTERNAL.value), record["parent_index"])

    skin_start = unit_info["skin_array_start"] + delta
    skin_count = struct.unpack_from("<I", raw, skin_start)[0]
    if skin_count != len(unit_info["skins"]):
        raise ValueError("Skin array count changed while serializing the unit")
    offset = skin_start + 4
    for skin in unit_info["skins"]:
        matrix_count = struct.unpack_from("<I", raw, offset)[0]
        offset += 4
        if matrix_count != len(skin.node_indices):
            raise ValueError("Skin inverse-bind matrix count does not match its joint palette")
        for palette_index, node_index in enumerate(skin.node_indices):
            record = rig_nodes.get(node_index)
            if record:
                inverse_bind = record["world"].inverted()
                struct.pack_into("<16f", raw, offset + palette_index * 64,
                                 *matrix_column_major(inverse_bind))
        offset += matrix_count * 64
        node_index_count = struct.unpack_from("<I", raw, offset)[0]
        offset += 4 + node_index_count * 4
        matrix_set_count = struct.unpack_from("<I", raw, offset)[0]
        offset += 4
        for _ in range(matrix_set_count):
            count = struct.unpack_from("<I", raw, offset)[0]
            offset += 4 + count * 4


def serialize_unit(unit_info, geometries, slot_ids, material_resource, bones_resource, mesh_bounds,
                   unit_resource, dynamic_rig=None):
    raw = unit_info["raw"]
    start = unit_info["geometry_start"]
    end = unit_info["geometry_end"]
    # The preserved prefix already contains the geometry-array count.
    geo_blob = b"".join(serialize_geometry(g) for g in geometries)
    delta = len(geo_blob) - (end - start)
    out = bytearray(raw[:start] + geo_blob + raw[end:])
    struct.pack_into("<Q", out, 8, hash64(unit_resource))
    struct.pack_into("<I", out, 29, len(out) - unit_dt.HEADER_SIZE)
    patch_dynamic_rig(out, unit_info, delta, dynamic_rig)

    default_material_offset = unit_info["default_material_offset"] + delta
    struct.pack_into("<Q", out, default_material_offset, 0)
    material_offset = unit_info["materials_offset"] + delta
    if unit_info["material_count"] != len(slot_ids):
        raise ValueError("Unit material map count does not match geometry count")
    material_map = []
    for geometry, slot_id in zip(geometries, slot_ids):
        resource = material_resource[geometry["material_index"]]
        material_map.append((slot_id, hash64(resource)))
    material_map.sort(key=lambda entry: entry[0])
    for i, (slot_id, resource_id) in enumerate(material_map):
        struct.pack_into("<IQ", out, material_offset + i * 12, slot_id, resource_id)
    skeleton_offset = unit_info["skeleton_offset"] + delta
    struct.pack_into("<Q", out, skeleton_offset, hash64(bones_resource))

    mesh_array_offset = unit_info["mesh_objects_array_offset"] + delta
    mesh_entry_start = mesh_array_offset + 4
    if len(mesh_bounds) != GEO_COUNT:
        raise ValueError("Mesh bound count mismatch")
    for i, bounds in enumerate(mesh_bounds):
        offset = mesh_entry_start + i * 72 + 28
        box = np.concatenate((bounds[0], bounds[1])).astype('<f4')
        out[offset:offset + 40] = box.tobytes() + bounds_sphere(box).tobytes()

    return bytes(out)


def load_target_unit():
    c = Cursor(str(TEMPLATE / "qianxia.unit"))
    unit = unit_dt.UnitResourceDT(c)
    return unit


def named_node_map(unit, bones_resource):
    names_by_hash = {
        bone_hash.ID: name
        for bone_hash, name in zip(bones_resource.bones_name_hashes, bones_resource.bone_names)
    }
    node_by_name = {}
    for index, node in enumerate(unit.scene_graph.nodes):
        name = names_by_hash.get(node.name.ID, node.name.lookup())
        if name in node_by_name:
            raise ValueError(f"Duplicate target skeleton node name: {name}")
        node_by_name[name] = index
    return node_by_name


def dynamic_rig_mapping(mesh, armature, unit, node_by_name):
    # Shoulder shawls are fixed attachments. Their source weights follow the
    # static arm bind and must not consume helper bones from the runtime jiggle
    # pool; the cloak/tail/hair chains remain the only dynamic attachments here.
    terms = ("clothes_cloak_", "tail_base_", "hair_side_", "hair_base_", "hat_move_", "ear_base_")
    fixed_attachment_prefixes = (
        "cape_base_L_", "cape_base_R_", "gs_base_Back_",
        "shawl_base_L_", "shawl_base_R_",
    )
    dynamic_names = {
        bone.name for bone in armature.data.bones
        if bone.name.casefold().startswith(tuple(term.casefold() for term in terms))
        and not bone.name.casefold().startswith(tuple(term.casefold() for term in fixed_attachment_prefixes))
        and not bone.name.endswith("錘")
    }
    depth_cache = {}

    def depth(bone):
        if bone.name not in depth_cache:
            depth_cache[bone.name] = 0 if bone.parent is None else depth(bone.parent) + 1
        return depth_cache[bone.name]

    bones = sorted((armature.data.bones[name] for name in dynamic_names),
                   key=lambda bone: (depth(bone), bone.name))
    bones_resource = BonesResourceDT(Cursor(str(TEMPLATE / "qianxia_bones.bones")))
    helpers = {
        "hair": [name for name in bones_resource.bone_names
                 if name.startswith("qianxia_hair_") and name in node_by_name],
            "cloth": [name for name in bones_resource.bone_names
                      if name.startswith("qianxia_cloth_") and name in node_by_name],
    }
    group_by_source = {}
    source_by_target = {}
    for bone in bones:
        lowered = bone.name.lower()
        kind = "hair" if "hair" in lowered or "髪" in bone.name or "髮" in bone.name else "cloth"
        pool = helpers[kind]
        used = sum(1 for value in group_by_source.values() if value == kind)
        if used >= len(pool):
            raise ValueError(f"Not enough {kind} helper nodes for {len(bones)} source dynamic bones")
        target_name = pool[used]
        group_by_source[bone.name] = kind
        source_by_target[bone.name] = target_name

    base_targets = source_bone_targets(armature, node_by_name, source_by_target)
    base_rig_nodes = {}
    base_bind_transforms = target_bind_transforms(
        armature, node_by_name, unit, translation_only=True,
        node_records=base_rig_nodes, mesh=mesh,
    )
    root_map = Matrix(base_bind_transforms["j_hips"].tolist())
    hand_rig = source_hand_bind_transforms(
        armature, base_targets, node_by_name, unit, root_map=root_map,
    )
    source_to_target = dict(base_targets)
    source_to_target.update(source_by_target)
    coordinate3 = source_coordinate3()
    armature_world = armature.matrix_world.copy()
    armature_world3 = armature_world.to_3x3()
    desired_world_by_name = {}
    parent_by_target = {}
    bind_transforms = {}
    records = []
    tail_bones = [bone for bone in bones
                  if bone.name.casefold().startswith("tail_base_")]
    tail_index = {bone.name: index for index, bone in enumerate(tail_bones)}
    tail_root_source = None
    if tail_bones:
        tail_root_source = coordinate3 @ (armature_world @ tail_bones[0].head_local)
    weighted_names = set()
    group_names = {group.index: group.name for group in mesh.vertex_groups}
    for vertex in mesh.data.vertices:
        for assignment in vertex.groups:
            name = group_names.get(assignment.group)
            if name in dynamic_names and assignment.weight > 0:
                weighted_names.add(name)

    for bone in bones:
        target_name = source_by_target[bone.name]
        target_index = node_by_name.get(target_name)
        if target_index is None:
            raise ValueError(f"Template unit is missing dynamic helper node {target_name}")
        source_parent = bone.parent
        while source_parent and source_parent.name in dynamic_names:
            source_parent = source_parent.parent
        anchor_target = base_targets.get(source_parent.name) if source_parent else None
        if not anchor_target or anchor_target not in node_by_name:
            anchor_target = base_targets.get(bone.name)
        if not anchor_target or anchor_target not in node_by_name:
            raise ValueError(f"Cannot find canonical anchor for source bone {bone.name}")
        if bone.parent and bone.parent.name in source_by_target:
            parent_target = source_by_target[bone.parent.name]
        else:
            parent_target = anchor_target
        parent_by_target[target_name] = parent_target

        z_axis = source_bone_direction(armature, bone)
        reference = Vector((1, 0, 0)) if abs(z_axis.x) < 0.9 else Vector((0, 1, 0))
        x_axis = (reference - z_axis * reference.dot(z_axis)).normalized()
        y_axis = z_axis.cross(x_axis).normalized()
        desired_world = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
        if (desired_world.to_3x3() @ Vector((0, 0, 1)) - z_axis).length > 1e-5:
            raise ValueError(f"Dynamic +Z axis mismatch: {bone.name}")
        source_head = coordinate3 @ (armature_world @ bone.head_local)
        if bone.name in tail_index and tail_root_source is not None:
            tail_t = tail_index[bone.name] / max(1, len(tail_bones) - 1)
            # Use the same centreline profile as roshia_tail_core.  This keeps
            # the serialized rest pivot, generated shell and runtime jiggle
            # chain coincident instead of animating from a detached anchor.
            source_head = (
                tail_root_source
                + (source_head - tail_root_source) * TAIL_CHAIN_SCALE
                + tail_target_offset(tail_t)
            )
        desired_world.translation = root_map @ source_head
        desired_world_by_name[target_name] = desired_world
        bind_transforms[target_name] = np.asarray(root_map, dtype=np.float32)

        source_segment = coordinate3 @ armature_world3 @ (bone.tail_local - bone.head_local)
        length = float(source_segment.length)
        runtime_parent = parent_target
        records.append({
            "source_bone": bone.name,
            "node": target_name,
            "parent": runtime_parent,
            "group": "hair" if group_by_source[bone.name] == "hair" else ("tail" if "tail" in bone.name.lower() else "cloth"),
            "length": round(max(length, 0.001), 6),
            "weighted": bone.name in weighted_names,
            "source_parent": bone.parent.name if bone.parent else None,
        })

    desired_worlds_by_index = {
        node_index: record["world"]
        for node_index, record in base_rig_nodes.items()
    }
    desired_worlds_by_index.update({
        node_index: record["world"]
        for node_index, record in hand_rig["node_transforms"].items()
    })
    desired_worlds_by_index.update({
        node_by_name[target_name]: desired_world
        for target_name, desired_world in desired_world_by_name.items()
    })
    parent_overrides = {
        node_by_name[target_name]: node_by_name[parent_name]
        for target_name, parent_name in parent_by_target.items()
    }
    node_transforms = scene_graph_transform_records(
        unit, desired_worlds_by_index, parent_overrides
    )
    hand_node_transforms = {
        node_index: node_transforms[node_index]
        for node_index in hand_rig["node_transforms"]
    }

    source_target_index = {
        source_name: node_by_name[target_name]
        for source_name, target_name in source_by_target.items()
    }
    result = {
        "dynamic_names": dynamic_names,
        "source_to_target": source_to_target,
        "source_by_target": source_by_target,
        "node_transforms": node_transforms,
        "hand_node_transforms": hand_node_transforms,
        "hand_rig": hand_rig,
        "bind_transforms": bind_transforms,
        "runtime_bones": records,
        "source_target_index": source_target_index,
    }
    if BINDING_MODE == "animation-compatible":
        adapt_animation_bind(unit, node_by_name, result, root_map)
    return result


def adapt_animation_bind(unit, node_by_name, rig, root_map):
    """Bake source-rest -> native animation-rest once, rather than at node linking.

    Named j_* nodes are driven by the game's skeleton. Their inverse binds must
    use that same reference frame. Helper nodes retain source shape/roll, carried
    by the identical compensation as their named anchor.
    """
    source_records = rig["node_transforms"]
    source_worlds = {index: record["world"].copy()
                     for index, record in source_records.items()}
    native_worlds = {index: node.world_transform.copy()
                     for index, node in enumerate(unit.scene_graph.nodes)}
    compensation = {}
    geometry_maps = {}
    for index, record in source_records.items():
        if record["name"].startswith("j_"):
            compensation[index] = native_worlds[index] @ source_worlds[index].inverted()
            geometry_maps[record["name"]] = np.asarray(compensation[index] @ root_map,
                                                       dtype=np.float32)
    # Runtime records are emitted in source parent-before-child order.
    for bone in rig["runtime_bones"]:
        index = node_by_name[bone["node"]]
        parent_index = node_by_name[bone["parent"]]
        if parent_index not in compensation:
            raise ValueError(f"Missing animation compensation for {bone['parent']}")
        compensation[index] = compensation[parent_index]
        native_worlds[index] = compensation[index] @ source_worlds[index]
        geometry_maps[bone["node"]] = np.asarray(compensation[index] @ root_map,
                                                  dtype=np.float32)
    desired = {index: native_worlds[index] for index in source_records}
    parents = {index: record["parent_index"] for index, record in source_records.items()}
    records = scene_graph_transform_records(unit, desired, parents)
    rig["node_transforms"] = records
    rig["hand_node_transforms"] = {index: records[index] for index in rig["hand_node_transforms"]}
    rig["geometry_bind_transforms"] = geometry_maps
    rig["bind_transforms"] = {name: geometry_maps[name] for name in rig["bind_transforms"]}
    # Source-specific hand overrides must not bypass the native bind bake.
    rig["hand_rig"]["source_transforms"] = {}
    rig["hand_rig"]["node_transforms"] = rig["hand_node_transforms"]
    rig["binding_mode"] = BINDING_MODE


def make_asset(asset_folder, asset_prefix, arm_only, template_unit, node_by_name,
               translation_only=False, matrix_targets=(), hand_retarget_mode="legacy",
               dynamic_rig=None, hide_cloak_blades=False):
    folder = OUTPUT / asset_folder
    folder.mkdir(parents=True, exist_ok=True)
    body_resource = f"{RESOURCE_ROOT}/{asset_prefix}"
    bones_resource = f"{RESOURCE_ROOT}/{asset_prefix}_bones"

    mesh = bpy.data.objects.get(MESH_OBJECT_NAME)
    armature = bpy.data.objects.get(ARMATURE_OBJECT_NAME)
    if mesh is None or armature is None:
        raise ValueError(
            f"The source Blender file is missing {MESH_OBJECT_NAME!r} or {ARMATURE_OBJECT_NAME!r}"
        )
    geometries, chunk_materials = build_geometry_chunks(
        mesh, armature, template_unit, node_by_name, arm_only, asset_prefix,
        [IDString32.from_str(f"{asset_prefix}_slot_{i:02d}").ID for i in range(GEO_COUNT)],
        translation_only=translation_only,
        matrix_targets=matrix_targets,
        hand_retarget_mode=hand_retarget_mode,
        dynamic_rig=dynamic_rig,
        hide_cloak_blades=hide_cloak_blades,
    )
    slot_ids = [IDString32.from_str(f"{asset_prefix}_slot_{i:02d}").ID for i in range(GEO_COUNT)]
    material_resources, material_infos, texture_infos = write_native_materials(folder, asset_prefix, mesh, geometries)

    info = read_unit_offsets(TEMPLATE / "qianxia.unit")
    mesh_bounds = [(geometry["bounds"][:3], geometry["bounds"][3:]) for geometry in geometries]
    output_unit = serialize_unit(
        info, geometries, slot_ids, material_resources, bones_resource, mesh_bounds, body_resource,
        dynamic_rig=dynamic_rig,
    )
    unit_file = folder / f"{asset_prefix}.unit"
    unit_file.write_bytes(output_unit)

    bones_file = TEMPLATE / "qianxia_bones.bones"
    bone_data = bytearray(bones_file.read_bytes())
    struct.pack_into("<Q", bone_data, 8, hash64(bones_resource))
    # Same-length private names keep all resource lengths/skin indices intact.
    for node_index, alias in (dynamic_rig or {}).get('node_renames', {}).items():
        old_hash = template_unit.scene_graph.nodes[node_index].name.ID
        old_name = next(n for n, i in node_by_name.items() if i == node_index)
        old_bytes, new_bytes = old_name.encode() + b'\0', alias.encode() + b'\0'
        if len(old_bytes) != len(new_bytes) or bone_data.count(old_bytes) != 1:
            raise ValueError('Private hand name must replace one equal-length bones entry')
        bone_data = bone_data.replace(old_bytes, new_bytes)
        # Hash table follows the 38-byte header and count/LOD-count fields.
        count = struct.unpack_from('<I', bone_data, 38)[0]
        matches = [46 + i * 4 for i in range(count)
                   if struct.unpack_from('<I', bone_data, 46 + i * 4)[0] == old_hash]
        if len(matches) != 1:
            raise ValueError('Private hand hash missing or duplicated')
        struct.pack_into('<I', bone_data, matches[0], IDString32.from_str(alias).ID)
    (folder / f"{asset_prefix}_bones.bones").write_bytes(bone_data)

    validate_output_unit(unit_file, folder, geometries, body_resource, bones_resource,
                         material_resources, dynamic_rig=dynamic_rig)
    return {
        "asset_folder": asset_folder,
        "asset_path": body_resource,
        "unit": unit_file.name,
        "bones": f"{asset_prefix}_bones.bones",
        "materials": material_infos,
        "textures": texture_infos,
        "triangle_count": sum(geometry["triangle_count"] for geometry in geometries),
        "vertex_count": sum(geometry["vertices"] for geometry in geometries),
        "arm_only": arm_only,
        "translation_only": translation_only,
        "hand_retarget_mode": hand_retarget_mode,
        "chunk_materials": chunk_materials,
        "chunk_triangles": [geometry["triangle_count"] for geometry in geometries],
    }


def matrix_max_error(left, right):
    return max(abs(float(left[row][column] - right[row][column]))
               for row in range(4) for column in range(4))


def audit_serialized_skin(unit_file, unit, geometries):
    """Independent raw TRS/FK check, without the addon's get_trs_matrix helper."""
    info = read_unit_offsets(unit_file)
    raw = info["raw"]
    nodes = unit.scene_graph.nodes
    local_start = info["scene_graph_start"] + 4
    parent_start = local_start + len(nodes) * (60 + 64)
    worlds, visiting = {}, set()

    def world(index):
        if index in worlds:
            return worlds[index]
        if index in visiting:
            raise ValueError("Serialized parent cycle")
        visiting.add(index)
        values = struct.unpack_from("<15f", raw, local_start + index * 60)
        local = np.eye(4, dtype=np.float64)
        local[:3, :3] = np.asarray(values[:9]).reshape((3, 3), order="F") @ np.diag(values[12:15])
        local[:3, 3] = values[9:12]
        kind, parent = struct.unpack_from("<HH", raw, parent_start + index * 4)
        result = world(parent) @ local if kind == ParentType.INTERNAL.value else local
        worlds[index] = result
        visiting.remove(index)
        return result

    active = set()
    for geometry in geometries:
        joints = np.frombuffer(geometry["streams"][5][0], dtype=np.uint8).reshape((-1, 4))
        weights = np.frombuffer(geometry["streams"][4][0], dtype="<f2").reshape((-1, 4))
        active.update(int(value) for value in joints[weights > 1e-5])
    skin = unit.skins[0]
    maximum = max(float(np.max(np.abs(world(skin.node_indices[palette]) @
                  np.asarray(skin.inv_bind_matrices[palette], dtype=np.float64) - np.eye(4))))
                  for palette in active)
    if maximum > 0.0002:
        raise ValueError(f"Raw serialized rest skin differs from Identity: {maximum}")
    report = {"method": "raw parent-space TRS -> recursive FK -> inverse bind",
              "weighted_palette_count": len(active), "max_skin_identity_error": maximum}
    (unit_file.parent / "rig_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("RAW_TRS_SKIN_VALIDATION " + json.dumps(report))
    face_dots = []
    for geo in unit.mesh_geometries:
        channels = {channel.component.name: channel for channel in geo.channels}
        pc, nc = channels["POSITION"], channels["NORMAL"]
        positions = geo.streams[pc.stream].get_positions(pc).astype(np.float32)
        normals = geo.streams[nc.stream].get_normals(nc).astype(np.float32)
        faces = geo.index_stream.get_indices().reshape((-1, 3))
        cross = np.cross(positions[faces[:, 1]] - positions[faces[:, 0]],
                         positions[faces[:, 2]] - positions[faces[:, 0]])
        valid = np.linalg.norm(cross, axis=1) > 1e-10
        dots = (cross * normals[faces].mean(axis=1)).sum(axis=1)
        face_dots.extend((dots[valid] > 0).tolist())
    outward_fraction = float(np.mean(face_dots))
    if outward_fraction < 0.95:
        raise ValueError(f"Winding disagrees with the working reference convention: {outward_fraction}")
    report["outward_winding_fraction"] = outward_fraction
    (unit_file.parent / "rig_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("WINDING_VALIDATION " + str(outward_fraction))


def validate_output_unit(unit_file, folder, geometries, body_resource, bones_resource,
                         material_resources, dynamic_rig=None):
    raw = unit_file.read_bytes()
    if struct.unpack_from("<Q", raw, 8)[0] != hash64(body_resource):
        raise ValueError("Generated unit resource identity is incorrect")
    c = Cursor(str(unit_file))
    unit = unit_dt.UnitResourceDT(c)
    audit_serialized_skin(unit_file, unit, geometries)
    if len(unit.mesh_geometries) != GEO_COUNT or len(unit.meshes) != GEO_COUNT:
        raise ValueError("Generated unit did not round-trip with 31 mesh objects")
    if unit.stream_name:
        raise ValueError("Generated geometry should remain inline in its unit resource")
    if unit.skeleton_name.ID != hash64(bones_resource):
        raise ValueError("Generated unit skeleton reference is incorrect")
    if dynamic_rig:
        binary_info = read_unit_offsets(unit_file)
        skin = unit.skins[0]
        palette_by_node = {node_index: palette for palette, node_index in enumerate(skin.node_indices)}
        expected_nodes = dict(dynamic_rig["node_transforms"])
        expected_nodes.update(dynamic_rig.get("hand_node_transforms", {}))
        for node_index, expected in expected_nodes.items():
            node = unit.scene_graph.nodes[node_index]
            if matrix_max_error(node.world_transform, expected["world"]) > 0.001:
                raise ValueError(f"Rig node world transform did not round-trip: {expected['name']}")
            if node.parent_type != ParentType.INTERNAL or node.parent_index != expected["parent_index"]:
                raise ValueError(f"Rig node parent did not round-trip: {expected['name']}")
            parent_world = unit.scene_graph.nodes[node.parent_index].world_transform
            raw_position = Vector(struct.unpack_from(
                "<3f", raw,
                binary_info["scene_graph_start"] + 4 + node_index * 60 + 36,
            ))
            expected_position = (parent_world.inverted() @ node.world_transform).translation
            if (raw_position - expected_position).length > 0.0001:
                raise ValueError(f"Serialized parent-space position is incorrect: {expected['name']}")
            hierarchy_error = matrix_max_error(
                parent_world @ node.local_transform, node.world_transform
            )
            if hierarchy_error > 0.002:
                raise ValueError(
                    f"Rig node local/world hierarchy is inconsistent: {expected['name']} "
                    f"(error {hierarchy_error:.6f})"
                )
            palette = palette_by_node.get(node_index)
            if palette is None:
                raise ValueError(f"Rig node is missing from the skin palette: {expected['name']}")
            expected_inverse = expected["world"].inverted()
            if matrix_max_error(skin.inv_bind_matrices[palette], expected_inverse) > 0.002:
                raise ValueError(f"Rig inverse bind matrix did not round-trip: {expected['name']}")
            if matrix_max_error(node.world_transform @ skin.inv_bind_matrices[palette], Matrix.Identity(4)) > 0.002:
                raise ValueError(f"Rig bind pose is not identity at {expected['name']}")
    if unit.default_material_resource.ID != 0:
        raise ValueError("Generated unit should not have a fallback material override")
    unit_slot_ids = [slot.ID for slot, _ in unit.materials]
    if unit_slot_ids != sorted(unit_slot_ids):
        raise ValueError("Unit material map must be sorted by slot ID for engine lookup")
    material_by_slot = {slot.ID: material.ID for slot, material in unit.materials}
    for index, (geo, expected) in enumerate(zip(unit.mesh_geometries, geometries)):
        if len(geo.streams) != len(expected["streams"]):
            raise ValueError(f"Geometry {index} stream count did not round-trip")
        for stream_index, (payload, stride) in enumerate(expected["streams"]):
            parsed_stream = geo.streams[stream_index]
            if parsed_stream.vertex_data != payload:
                raise ValueError(f"Geometry {index} stream {stream_index} bytes changed during serialization")
            if parsed_stream.vertex_stream.stride != stride:
                raise ValueError(f"Geometry {index} stream {stream_index} stride did not round-trip")
        if geo.index_stream.data != expected["index_data"]:
            raise ValueError(f"Geometry {index} index buffer changed during serialization")
        if len(geo.batch_ranges) != 1 or geo.batch_ranges[0].size != expected["triangle_count"]:
            raise ValueError(f"Geometry {index} batch range did not round-trip")
        if geo.streams[1].vertex_stream.vertices != expected["vertices"]:
            raise ValueError(f"Geometry {index} vertex count did not round-trip")
        if geo.index_stream.index_count != expected["indices"]:
            raise ValueError(f"Geometry {index} index count did not round-trip")
        if len(geo.index_stream.get_indices()) != expected["indices"]:
            raise ValueError(f"Geometry {index} index stream is malformed")
        if len(geo.materials) != 1 or geo.materials[0].ID not in material_by_slot:
            raise ValueError(f"Geometry {index} material slot is not mapped by the unit")
        channels = {channel.component.name: stream for channel, stream in zip(geo.channels, geo.streams)}
        position_channel = next(c for c in geo.channels if c.component.name == 'POSITION')
        positions = geo.streams[position_channel.stream].get_positions(position_channel)
        if not np.isfinite(positions).all():
            raise ValueError(f"Geometry {index} contains a non-finite retargeted position")
        if not np.allclose(positions.min(axis=0), expected["bounds"][:3], atol=0.005):
            raise ValueError(f"Geometry {index} minimum bounds do not match retargeted positions")
        if not np.allclose(positions.max(axis=0), expected["bounds"][3:], atol=0.005):
            raise ValueError(f"Geometry {index} maximum bounds do not match retargeted positions")
        weights = np.frombuffer(channels["BLENDWEIGHTS"].vertex_data, dtype="<f2").reshape((-1, 4))
        joints = np.frombuffer(channels["BLENDINDICES"].vertex_data, dtype=np.uint8).reshape((-1, 4))
        if joints.size and int(joints.max()) >= len(unit.skins[0].node_indices):
            raise ValueError(f"Geometry {index} uses a skin index outside the unit palette")
        if len(weights) and not np.allclose(weights.sum(axis=1), 1.0, atol=0.002):
            raise ValueError(f"Geometry {index} has non-normalized skin weights")
    material_module.load_stream_dt = lambda path: StreamReader(Cursor(str(folder / pathlib.Path(path))))
    for resource in material_resources.values():
        primary = folder / (resource.rsplit("/", 1)[-1] + ".material")
        MaterialResourceDT(Cursor(str(primary)))


def write_manifests(result):
    for asset in result["assets"]:
        folder = OUTPUT / asset["asset_folder"]
        artifacts = []
        resources = []

        def add(resource_type, resource_name, path, role):
            file_path = folder / path
            record = {
                "resource": {"type": resource_type, "name": resource_name},
                "role": role,
                "path": path,
                "size": file_path.stat().st_size,
            }
            artifacts.append(record)
            resources.append(path)

        add("unit", asset["asset_path"], asset["unit"], "primary")
        add("bones", asset["asset_path"].rsplit("/", 1)[0] + "/" + asset["bones"].replace(".bones", ""), asset["bones"], "primary")
        for material in asset["materials"]:
            add("material", material["resource"]["name"], material["primary"], "primary")
            add("material", material["resource"]["name"], material["stream"], "stream")
        for texture in asset["textures"]:
            add("texture", texture["resource"]["name"], texture["primary"], "primary")
            add("texture", texture["resource"]["name"], texture["stream"], "stream")

        build = {
            "schema": 1,
            "requested_output": "unit",
            "compiler": {"name": "roshia-native-resource-builder", "version": "1.0.0"},
            "target": {"id": "darktide", "unit_version": 115, "material_version": 61},
            "roots": [{"type": "unit", "name": asset["asset_path"]}],
            "artifacts": artifacts,
            "resources": resources,
            "external_resources": [
                {"key": {"type": "material", "name": "content/parent_materials/substance_basic"}, "package_member": False},
            ],
        }
        (folder / "build.json").write_text(json.dumps(build, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        compile_manifest = {
            "source": str(SOURCE_BLEND),
            "status": "native_resource_build",
            "asset_path": asset["asset_path"],
            "asset_scale": SCALE,
            "mesh_adapter": ("Roshia torso FK and source-width shoulder supports; first-person native hand contact rig with source-weight surface fitting and engine-linked fingers" if BINDING_MODE == 'proportion-fk' else (
                "Source joint/palm frames baked into the native animation bind; named joints retain template world frames and helpers follow anchor compensation"
                if BINDING_MODE == "animation-compatible" else
                "MMD source geometry preserved with one shared rigid bind translation; mapped joints are aligned in the target scene graph"
            )),
            "binding_mode": BINDING_MODE,
            "texture_adapter": "per-material BC1/BC3 sRGB diffuse and ORM; native v67 profile footers, inline low mips and Oodle tiled high mips; face and opaque eye overlays use standard diffuse materials; neutral BC5 normal; oct(T)/oct(-B) tangent stream",
            "uv_convention": "DDS top-left: exported V = 1 - Blender V",
            "geometry": {"count": GEO_COUNT, "triangles": asset["triangle_count"], "vertices": asset["vertex_count"]},
            "first_person_arms": asset["arm_only"],
            "dependencies": ["CustomAssets", "ModelReplacementRegistry", "QianxiaReplacement"],
            "materials": ["face skin, iris, sclera, highlights, and lashes use their own standard diffuse BC textures; solid tail core uses substance_basic", "self-contained alpha provider and parent only for authored alpha cards"],
            "notes": [
                "Built by serializing the existing Darktide unit layout; source game files were not modified.",
                "Alpha shader dependencies are packaged locally for authored alpha cards; diffuse, neutral normal and per-material ORM textures belong to Roshia. Face and eye overlays use standard opaque diffuse paths with a 1.0-1.8 mm depth bias so the iris, sclera, highlights, and lashes remain visible over the skin shell.",
                "Source scale is uniformly 1.30 (previously 1.14) to meet native upper-limb height while preserving torso ratios. Hand landmarks use a continuous RBF fit.",
                "Third-person shoulder mesh uses two childless sleeve supports anchored at source shoulder roots and ending at native elbows; native driver bones and first-person contacts are unchanged.",
        "Tail-weighted alpha fur cards are removed to avoid cloak-surface overlays; a closed opaque tail shell follows the authored source centreline with a shared smooth target-space tip drop and uses a sampled, strand-detailed texture.",
        "The authored skirt silhouette is preserved without radial contraction; native arm animation remains responsible for clearance.",
                "The first-person arms unit uses engine NODE_NAME linking for native arms, wrists, fingers and custom_fov. MMR calibrates the authored source joints to the common contact skeleton. Source topology, UVs, corner normals and authored weights are retained; no nearest-triangle weight override or wrist seam compensation is applied. No private finger FK/IK runs. Equipment is untouched. In-game action coverage remains required.",
                "MMD rigid-body physics are not imported; the generated helper rig is driven by the Roshia runtime jiggle configuration.",
                "Animation-compatible mode bakes source-to-template rest compensation into geometry and uses native named-node inverse binds; source-rigid mode is available for comparison.",
                "Serialized local position is parent-relative; local TRS uses T @ R @ S. Raw-field FK and inverse-bind checks run independently of the import helper.",
                "The first-person mesh is filtered from arm-weighted triangles and needs in-game visual review.",
            ],
        }
        (folder / "compile_manifest.json").write_text(json.dumps(compile_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result.get("dynamic_rig"):
        dynamic_report = {
            "schema": 1,
            "source_blend": str(SOURCE_BLEND),
            "helper_nodes": len(result["dynamic_rig"]["source_by_target"]),
            "runtime_bones": result["dynamic_rig"]["runtime_bones"],
        }
        (OUTPUT / "roshia_jiggle_bones.json").write_text(
            json.dumps(dynamic_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        runtime_config = result.get("runtime_config_output")
        if runtime_config:
            runtime_config = pathlib.Path(runtime_config).resolve()
            runtime_config.parent.mkdir(parents=True, exist_ok=True)
            lines = ["return {", "    schema = 1,", "    bones = {"]
            for record in result["dynamic_rig"]["runtime_bones"]:
                lines.append(
                    "        { %s, %s, %s, %.6f, %s }," % (
                        lua_string(record["node"]),
                        lua_string(record["parent"]),
                        lua_string(record["group"]),
                        record["length"],
                        'true' if record.get('collision') else 'false',
                    )
                )
            lines.append("    },")
            if globals().get('CLOTH_COLLIDERS'):
                lines.append('    colliders = {')
                for a,z,radius in CLOTH_COLLIDERS:
                    lines.append('        { %s, %s, %.6f },' % (lua_string(a),lua_string(z),radius))
                lines.append('    },')
            lines.extend(["}", ""])
            runtime_config.write_text("\n".join(lines), encoding="ascii")


def main():
    global OUTPUT, SOURCE_BLEND, TEMPLATE, RESOURCE_ROOT, MESH_OBJECT_NAME, ARMATURE_OBJECT_NAME, SCALE, BINDING_MODE
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-blend", type=pathlib.Path, default=SOURCE_BLEND)
    parser.add_argument("--template-dir", type=pathlib.Path, default=TEMPLATE)
    parser.add_argument("--resource-root", default=RESOURCE_ROOT)
    parser.add_argument("--asset-prefix", default="roshia")
    parser.add_argument("--mesh-object", default=MESH_OBJECT_NAME)
    parser.add_argument("--armature-object", default=ARMATURE_OBJECT_NAME)
    parser.add_argument("--scale", type=float, default=SCALE)
    parser.add_argument("--translation-only", action="store_true")
    parser.add_argument("--matrix-target", action="append", default=[])
    parser.add_argument("--hand-retarget-mode", choices=("rigid", "legacy", "coherent"), default="rigid")
    parser.add_argument("--runtime-config-output", type=pathlib.Path)
    parser.add_argument("--output-dir", type=pathlib.Path, default=OUTPUT)
    parser.add_argument('--arms-only', action='store_true',
                        help='Rebuild first-person resources while preserving an existing body candidate')
    parser.add_argument("--hide-cloak-blades", action="store_true")
    parser.add_argument("--binding-mode", choices=("animation-compatible", "source-rigid", "proportion-fk"), default=BINDING_MODE)
    script_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(script_args)
    args.hand_retarget_mode = "rigid"
    SOURCE_BLEND = args.source_blend.resolve()
    TEMPLATE = args.template_dir.resolve()
    OUTPUT = args.output_dir.resolve()
    RESOURCE_ROOT = args.resource_root.strip("/")
    MESH_OBJECT_NAME = args.mesh_object
    ARMATURE_OBJECT_NAME = args.armature_object
    SCALE = args.scale
    BINDING_MODE = args.binding_mode
    if not SOURCE_BLEND.is_file():
        raise FileNotFoundError(f"Source Blender file does not exist: {SOURCE_BLEND}")
    if not (TEMPLATE / "qianxia.unit").is_file():
        raise FileNotFoundError(f"Target unit template does not exist: {TEMPLATE / 'qianxia.unit'}")
    if not bpy.data.filepath or pathlib.Path(bpy.data.filepath) != SOURCE_BLEND:
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))
    template_info = read_unit_offsets(TEMPLATE / "qianxia.unit")
    unit = load_target_unit()
    template_bones = BonesResourceDT(Cursor(str(TEMPLATE / "qianxia_bones.bones")))
    node_by_name = named_node_map(unit, template_bones)
    mesh = bpy.data.objects.get(MESH_OBJECT_NAME)
    armature = bpy.data.objects.get(ARMATURE_OBJECT_NAME)
    if mesh is None or armature is None:
        raise ValueError("Source Blender file is missing its configured mesh or armature")
    prepare_source(mesh,armature)
    dynamic_rig = dynamic_rig_mapping(mesh, armature, unit, node_by_name)
    arms_rig = dynamic_rig
    if BINDING_MODE == 'proportion-fk':
        from roshia_proportion_rig import adapt, write_config
        arms_rig = adapt(sys.modules[__name__], unit, node_by_name, dynamic_rig, True)
        dynamic_rig = adapt(sys.modules[__name__], unit, node_by_name, dynamic_rig, False)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        write_config(OUTPUT / 'roshia_proportion_bones.lua', dynamic_rig, arms_rig)
    assets = []
    if not args.arms_only:
        assets.append(make_asset(args.asset_prefix, args.asset_prefix, False, unit, node_by_name,
                   args.translation_only, args.matrix_target, args.hand_retarget_mode,
                   dynamic_rig=dynamic_rig, hide_cloak_blades=args.hide_cloak_blades))
    else:
        assert (OUTPUT / args.asset_prefix / 'build.json').is_file(), 'Missing preserved body candidate'
    assets.append(make_asset(args.asset_prefix + "_arms", args.asset_prefix + "_arms", True, unit, node_by_name,
                   args.translation_only, args.matrix_target, args.hand_retarget_mode,
                   dynamic_rig=arms_rig, hide_cloak_blades=args.hide_cloak_blades))
    result = {
        "source": str(SOURCE_BLEND),
        "translation_only": args.translation_only,
        "hide_cloak_blades": args.hide_cloak_blades,
        "hand_retarget_mode": args.hand_retarget_mode,
        "matrix_targets": args.matrix_target,
        "output": str(OUTPUT),
        "runtime_config_output": str(args.runtime_config_output) if args.runtime_config_output else None,
        "assets": assets,
        "dynamic_rig": dynamic_rig,
    }
    write_manifests(result)
    print("ROSHIA_BUILD " + json.dumps({
        "source": str(SOURCE_BLEND), "output": str(OUTPUT),
        "assets": [{"asset_path": asset["asset_path"], "triangles": asset["triangle_count"]}
                   for asset in assets],
        "dynamic_source_bones": len(dynamic_rig["dynamic_names"]),
        "dynamic_helper_nodes": len(dynamic_rig["source_by_target"]),
        "weighted_dynamic_bones": sum(item["weighted"] for item in dynamic_rig["runtime_bones"]),
        "runtime_bones": len(dynamic_rig["runtime_bones"]),
        "hide_cloak_blades": args.hide_cloak_blades,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
