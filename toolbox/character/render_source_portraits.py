"""Render portrait crops directly from the original character Blend scenes."""
import argparse
import json
import pathlib
import sys

import bpy
from mathutils import Vector


ROOT = pathlib.Path(r"<CHARACTER_WORKSPACE>")
SOURCE = pathlib.Path(r"<SOURCE_ROOT>\终末地")
OUTPUT = ROOT / "tools/model-work/distribution_fix/source_portraits"


def mesh_objects():
    return [obj for obj in bpy.data.objects if obj.type == "MESH"]


def material_images(material, depth=0, visited=None):
    if not material or not material.node_tree:
        return []
    visited = visited or set()
    found = []

    def visit(tree):
        if not tree or tree.as_pointer() in visited:
            return
        visited.add(tree.as_pointer())
        for node in tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                found.append(node.image)
            elif node.type == "GROUP":
                visit(node.node_tree)

    visit(material.node_tree)
    return found


def portrait_material(original):
    """Use the original model's color/alpha images without its game-preview shader."""
    images = material_images(original)
    name = original.name.lower()
    color_candidates = [im for im in images if "_d." in im.name.lower() or "_d_" in im.name.lower()]
    image = max(color_candidates, key=lambda im: im.size[0] * im.size[1]) if color_candidates else None
    material = bpy.data.materials.new("Portrait | " + original.name)
    material.use_nodes = True
    material.diffuse_color = original.diffuse_color
    if image:
        material["portrait_source_image"] = image.name
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (420, 0)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.location = (140, 0)
    shader.inputs["Roughness"].default_value = 0.78 if any(x in name for x in ("cloth", "hair")) else 0.62
    shader.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in shader.inputs:
        shader.inputs["Specular IOR Level"].default_value = 0.18
    if image:
        texture = nodes.new("ShaderNodeTexImage")
        texture.location = (-180, 0)
        texture.image = image
        texture.interpolation = "Linear"
        texture.image.colorspace_settings.name = "sRGB"
        material.node_tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
        if "Alpha" in shader.inputs:
            material.node_tree.links.new(texture.outputs["Alpha"], shader.inputs["Alpha"])
    else:
        shader.inputs["Base Color"].default_value = original.diffuse_color
        if "Alpha" in shader.inputs:
            shader.inputs["Alpha"].default_value = original.diffuse_color[3]
    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "DITHERED"
    return material


def render_portrait(name, debug=False, original_materials=False, source_dir=SOURCE, output_dir=OUTPUT, framing="portrait"):
    blend = source_dir / (name + ".blend")
    if not blend.is_file():
        raise FileNotFoundError(blend)
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene = bpy.context.scene
    original_camera = scene.camera.name if scene.camera else None
    original_engine = scene.render.engine

    candidates = []
    for obj in mesh_objects():
        parent_name = obj.parent.name.lower() if obj.parent else ""
        is_proxy = "_mesh__" in obj.name
        helper = parent_name.startswith("rigidbodies") or "outline" in obj.name.lower() or "shadow" in obj.name.lower()
        expression = obj.name.endswith(".001") and "_mesh" in obj.name
        obj.hide_render = helper or expression or not is_proxy
        if not obj.hide_render:
            candidates.append(obj)
    if not candidates:
        main_mesh = bpy.data.objects.get(name + "_mesh")
        if main_mesh and main_mesh.type == "MESH":
            main_mesh.hide_render = False
            candidates = [main_mesh]
            for obj in mesh_objects():
                if obj is not main_mesh:
                    obj.hide_render = True
    if not original_materials:
        for obj in candidates:
            for slot in obj.material_slots:
                if slot.material:
                    slot.material = portrait_material(slot.material)
    if not candidates:
        raise RuntimeError(f"No original render proxy meshes found for {name}")

    points = [obj.matrix_world @ vertex.co for obj in candidates for vertex in obj.data.vertices]
    bounds = [
        [min(point[axis] for point in points), max(point[axis] for point in points)]
        for axis in range(3)
    ]
    height = bounds[2][1] - bounds[2][0]
    crown_z = bounds[2][1]
    head_points = [point for point in points if point.z >= crown_z - height * 0.27]
    head_min_x = min(point.x for point in head_points)
    head_max_x = max(point.x for point in head_points)
    center_x = (head_min_x + head_max_x) * 0.5
    portrait_height = max(height * 0.27 * 1.12, (head_max_x - head_min_x) / 0.84)
    portrait_height = min(portrait_height, height * 0.38)
    center_z = crown_z + portrait_height * 0.025 - portrait_height * 0.5
    center_y = 0.0
    if framing == "full-body":
        center_x = (bounds[0][0] + bounds[0][1]) * 0.5
        center_y = (bounds[1][0] + bounds[1][1]) * 0.5
        center_z = (bounds[2][0] + bounds[2][1]) * 0.5
        width = bounds[0][1] - bounds[0][0]
        portrait_height = max(height * 0.9, width * 1.05)

    camera_data = bpy.data.cameras.new("Original portrait camera")
    camera = bpy.data.objects.new("Original portrait camera", camera_data)
    scene.collection.objects.link(camera)
    target = Vector((center_x, center_y, center_z))
    camera.location = target + Vector((0.0, -4.0, 0.0))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = portrait_height
    scene.camera = camera

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 512 if framing == "portrait" else 768
    scene.render.resolution_y = 512 if framing == "portrait" else 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    scene.render.filepath = str(output_dir / (name + ".png"))
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.15
    scene.view_settings.gamma = 1.0
    scene.render.resolution_percentage = 100

    # Original CMB materials carry the character's authored face and eye shading.
    for obj in bpy.data.objects:
        if obj.type == "LIGHT":
            obj.hide_render = True
    light_data = bpy.data.lights.new("Portrait soft key", "AREA")
    light_data.energy = 60.0
    light_data.shape = "DISK"
    light_data.size = 1.6
    light = bpy.data.objects.new("Portrait soft key", light_data)
    scene.collection.objects.link(light)
    light.location = (center_x - 0.35, -1.8, center_z + 0.55)
    light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
    fill_data = bpy.data.lights.new("Portrait fill", "AREA")
    fill_data.energy = 28.0
    fill_data.shape = "DISK"
    fill_data.size = 2.2
    fill = bpy.data.objects.new("Portrait fill", fill_data)
    scene.collection.objects.link(fill)
    fill.location = (center_x + 0.7, -1.5, center_z - 0.25)
    fill.rotation_euler = (target - fill.location).to_track_quat("-Z", "Y").to_euler()

    output_dir.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output_dir / (name + ".png"))
    if debug:
        diagnostic = {
            "name": name,
            "source": str(blend),
            "framing": framing,
            "render_meshes": [obj.name for obj in candidates],
            "bounds": bounds,
            "portrait_height": portrait_height,
            "center": [center_x, center_z],
            "engine": scene.render.engine,
            "view_transform": scene.view_settings.view_transform,
            "lights": [obj.name for obj in bpy.data.objects if obj.type == "LIGHT" and not obj.hide_render],
            "camera_original": original_camera,
            "engine_original": original_engine,
            "materials": sorted({slot.material.name for obj in candidates for slot in obj.material_slots if slot.material}),
            "source_images": sorted({image.name for obj in candidates for slot in obj.material_slots if slot.material for image in material_images(slot.material)}),
        }
        (output_dir / (name + "_diagnostic.json")).write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8")
        print("PORTRAIT_DIAGNOSTIC", json.dumps(diagnostic, ensure_ascii=False), flush=True)
    bpy.ops.render.render(write_still=True)
    print("PORTRAIT_RENDERED", name, scene.render.filepath, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="+")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--original-materials", action="store_true")
    parser.add_argument("--source-dir", type=pathlib.Path, default=SOURCE)
    parser.add_argument("--output-dir", type=pathlib.Path, default=OUTPUT)
    parser.add_argument("--framing", choices=("portrait", "full-body"), default="portrait")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    for name in args.names:
        render_portrait(name, args.debug, args.original_materials, args.source_dir, args.output_dir, args.framing)


if __name__ == "__main__":
    main()
