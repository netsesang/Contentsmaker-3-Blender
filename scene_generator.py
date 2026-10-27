import os
import json
from pathlib import Path
from typing import Dict, Any

def generate_bpy_script(params: Dict[str, Any], output_mp4: str, output_thumb: str) -> str:
    """
    Generates a standalone Python script to be executed inside Blender via `blender -b -P script.py`.
    Builds procedural 3D buildings, dynamic lighting, characters, animated cameras, and renders MP4 + Thumbnail.
    """
    params_json = json.dumps(params, ensure_ascii=False)
    mp4_escaped = output_mp4.replace("\\", "/")
    thumb_escaped = output_thumb.replace("\\", "/")

    script = f'''# Auto-generated Blender Python Script by Contentsmaker-3-Blender
import bpy
import math
import os
import json

PARAMS = json.loads({json.dumps(params_json)})
OUTPUT_MP4 = "{mp4_escaped}"
OUTPUT_THUMB = "{thumb_escaped}"

# 1. Reset Scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# Ensure world exists
if not scene.world:
    scene.world = bpy.data.worlds.new("World")
scene.world.use_nodes = True
bg_node = scene.world.node_tree.nodes.get("Background")

# Render Engine setup (EEVEE / CYCLES with GPU)
engine_type = PARAMS.get("engine", "EEVEE") # "EEVEE" or "CYCLES"
if engine_type == "CYCLES":
    scene.render.engine = 'CYCLES'
    try:
        cprefs = bpy.context.preferences.addons['cycles'].preferences
        cprefs.compute_device_type = 'OPTIX'
        for device in cprefs.devices:
            device.use = True
        scene.cycles.device = 'GPU'
        scene.cycles.samples = PARAMS.get("samples", 64)
    except Exception as e:
        print(f"GPU Setup note: {{e}}")
else:
    # Blender 4.2+ uses BLENDER_EEVEE_NEXT, fallback to BLENDER_EEVEE
    for ee in ['BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE']:
        if ee in bpy.types.RenderEngine.bl_rna.properties['engine'].enum_items:
            scene.render.engine = ee
            break

# Format & Resolution
aspect_ratio = PARAMS.get("aspect_ratio", "16:9")
if aspect_ratio == "9:16":
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
else:
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080

scene.render.resolution_percentage = 100
fps = PARAMS.get("fps", 30)
duration_sec = PARAMS.get("duration", 4.0)
scene.render.fps = fps
scene.frame_start = 1
scene.frame_end = int(fps * duration_sec)

# 2. Materials Factory
def create_material(name, color=(0.8, 0.8, 0.8, 1.0), metallic=0.0, roughness=0.5, emission=0.0, emission_color=(1,1,1,1)):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        if 'Metallic' in bsdf.inputs:
            bsdf.inputs['Metallic'].default_value = metallic
        if 'Roughness' in bsdf.inputs:
            bsdf.inputs['Roughness'].default_value = roughness
        if emission > 0 and 'Emission Strength' in bsdf.inputs:
            bsdf.inputs['Emission Strength'].default_value = emission
            if 'Emission Color' in bsdf.inputs:
                bsdf.inputs['Emission Color'].default_value = emission_color
    return mat

mat_ground = create_material("Mat_Ground", color=(0.08, 0.09, 0.12, 1.0), metallic=0.2, roughness=0.8)
mat_concrete = create_material("Mat_Concrete", color=(0.2, 0.22, 0.25, 1.0), metallic=0.1, roughness=0.7)
mat_glass = create_material("Mat_Glass", color=(0.1, 0.2, 0.35, 1.0), metallic=0.9, roughness=0.1)
mat_window_glow = create_material("Mat_WindowGlow", color=(1.0, 0.85, 0.5, 1.0), emission=4.0, emission_color=(1.0, 0.85, 0.4, 1.0))
mat_neon_cyan = create_material("Mat_NeonCyan", color=(0.0, 0.8, 1.0, 1.0), emission=6.0, emission_color=(0.0, 0.9, 1.0, 1.0))
mat_neon_magenta = create_material("Mat_NeonMagenta", color=(1.0, 0.1, 0.6, 1.0), emission=6.0, emission_color=(1.0, 0.1, 0.6, 1.0))
mat_character = create_material("Mat_Character", color=(0.9, 0.75, 0.3, 1.0), metallic=0.4, roughness=0.3)

# 3. Ground Plane
bpy.ops.mesh.primitive_plane_add(size=120, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground"
ground.data.materials.append(mat_ground)

# 4. Building Generator
building_style = PARAMS.get("building_style", "modern_tower")
floors = PARAMS.get("floors", 12)
floor_height = 1.2
building_width = PARAMS.get("building_width", 6.0)
building_depth = PARAMS.get("building_depth", 6.0)

# Main Tower Structure
building_collection = bpy.data.collections.new("Building")
scene.collection.children.link(building_collection)

for f in range(floors):
    z = (f + 0.5) * floor_height
    # Alternate scaling or taper for modern architecture
    taper = 1.0 - (f / floors) * 0.25 if building_style == "modern_tower" else 1.0
    w = building_width * taper
    d = building_depth * taper

    # Core concrete slab
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, z))
    slab = bpy.context.active_object
    slab.scale = (w, d, floor_height * 0.92)
    slab.data.materials.append(mat_glass if f % 2 == 0 else mat_concrete)
    building_collection.objects.link(slab)
    scene.collection.objects.unlink(slab)

    # Window lights/strips
    if f % 2 == 1:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, z))
        win = bpy.context.active_object
        win.scale = (w * 1.01, d * 0.8, floor_height * 0.35)
        neon_choice = mat_neon_cyan if f % 4 == 1 else mat_window_glow
        win.data.materials.append(neon_choice)
        building_collection.objects.link(win)
        scene.collection.objects.unlink(win)

# Rooftop architectural accent / Antenna / Heli-pad
roof_z = floors * floor_height
bpy.ops.mesh.primitive_cylinder_add(radius=building_width * 0.35, depth=0.4, location=(0, 0, roof_z + 0.2))
roof_pad = bpy.context.active_object
roof_pad.data.materials.append(mat_concrete)
building_collection.objects.link(roof_pad)
scene.collection.objects.unlink(roof_pad)

# Rooftop Spire / Light beacon
bpy.ops.mesh.primitive_cone_add(radius1=0.2, depth=3.0, location=(0, 0, roof_z + 1.8))
spire = bpy.context.active_object
spire.data.materials.append(mat_neon_magenta)
building_collection.objects.link(spire)
scene.collection.objects.unlink(spire)

# Surrounding City Blocks (background ambiance)
import random
random.seed(42)
for i in range(16):
    angle = (i / 16.0) * math.pi * 2
    dist = random.uniform(18.0, 35.0)
    bx = math.cos(angle) * dist
    by = math.sin(angle) * dist
    bh = random.uniform(6.0, 18.0)
    bw = random.uniform(3.0, 5.5)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, by, bh / 2.0))
    bg_bldg = bpy.context.active_object
    bg_bldg.scale = (bw, bw, bh)
    bg_bldg.data.materials.append(mat_concrete)
    building_collection.objects.link(bg_bldg)
    scene.collection.objects.unlink(bg_bldg)

# 5. 3D Character Placement
char_collection = bpy.data.collections.new("Characters")
scene.collection.children.link(char_collection)

# Spawn stylized hero character on rooftop or balcony
char_loc = (0.5, 0.5, roof_z + 0.4)
# Character Body (torso)
bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=0.7, location=(char_loc[0], char_loc[1], char_loc[2] + 0.75))
char_torso = bpy.context.active_object
char_torso.data.materials.append(mat_character)
char_collection.objects.link(char_torso)
scene.collection.objects.unlink(char_torso)

# Character Head
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.2, location=(char_loc[0], char_loc[1], char_loc[2] + 1.3))
char_head = bpy.context.active_object
char_head.data.materials.append(mat_character)
char_collection.objects.link(char_head)
scene.collection.objects.unlink(char_head)

# 6. Lighting Atmosphere
lighting_preset = PARAMS.get("lighting", "cinematic_sunset") # "cinematic_sunset", "cyberpunk_neon", "studio_clean"

if lighting_preset == "cyberpunk_neon":
    if bg_node:
        bg_node.inputs['Color'].default_value = (0.01, 0.01, 0.03, 1.0)
        bg_node.inputs['Strength'].default_value = 0.5

    # Key Cyan Rim Light
    bpy.ops.object.light_add(type='SPOT', location=(12, -15, 20))
    l1 = bpy.context.active_object
    l1.data.energy = 5000
    l1.data.color = (0.0, 0.8, 1.0)
    l1.data.spot_size = math.radians(65)

    # Fill Magenta Light
    bpy.ops.object.light_add(type='POINT', location=(-15, 10, 15))
    l2 = bpy.context.active_object
    l2.data.energy = 4000
    l2.data.color = (1.0, 0.1, 0.7)

    # Top Hero Light
    bpy.ops.object.light_add(type='POINT', location=(char_loc[0], char_loc[1], char_loc[2] + 3.0))
    l3 = bpy.context.active_object
    l3.data.energy = 800
    l3.data.color = (1.0, 0.9, 0.6)

elif lighting_preset == "studio_clean":
    if bg_node:
        bg_node.inputs['Color'].default_value = (0.8, 0.85, 0.9, 1.0)
        bg_node.inputs['Strength'].default_value = 1.2
    bpy.ops.object.light_add(type='SUN', location=(10, -10, 25))
    sun = bpy.context.active_object
    sun.data.energy = 4.0
    sun.data.color = (1.0, 0.98, 0.95)

else: # cinematic_sunset (default)
    if bg_node:
        bg_node.inputs['Color'].default_value = (0.1, 0.04, 0.08, 1.0)
        bg_node.inputs['Strength'].default_value = 0.8
    # Low golden sun
    bpy.ops.object.light_add(type='SUN', rotation=(math.radians(72), math.radians(10), math.radians(45)))
    sun = bpy.context.active_object
    sun.data.energy = 6.0
    sun.data.color = (1.0, 0.55, 0.2) # Deep warm golden hour

    # Fill cool rim light
    bpy.ops.object.light_add(type='POINT', location=(-12, -10, roof_z + 8))
    rim = bpy.context.active_object
    rim.data.energy = 2500
    rim.data.color = (0.2, 0.5, 1.0)

# 7. Animated Camera Work
camera_shot = PARAMS.get("camera_shot", "orbit_360") # "orbit_360", "tilt_up", "push_in", "pan_lateral"
cam_data = bpy.data.cameras.new("MainCamera")
cam_obj = bpy.data.objects.new("MainCamera", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj
cam_data.lens = PARAMS.get("focal_length", 35)

# Target empty to track
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, roof_z * 0.6))
target = bpy.context.active_object
track = cam_obj.constraints.new(type='TRACK_TO')
track.target = target
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'

# Animate Camera Path
frames = scene.frame_end
if camera_shot == "tilt_up":
    # Start ground level, ascend to roof
    cam_obj.location = (16, -16, 2.0)
    cam_obj.keyframe_insert(data_path="location", frame=1)
    cam_obj.location = (12, -12, roof_z + 4.0)
    cam_obj.keyframe_insert(data_path="location", frame=frames)
    target.location = (0, 0, 3.0)
    target.keyframe_insert(data_path="location", frame=1)
    target.location = (char_loc[0], char_loc[1], char_loc[2] + 1.0)
    target.keyframe_insert(data_path="location", frame=frames)

elif camera_shot == "push_in":
    # Push in to character
    cam_obj.location = (char_loc[0] + 10, char_loc[1] - 12, char_loc[2] + 4.0)
    cam_obj.keyframe_insert(data_path="location", frame=1)
    cam_obj.location = (char_loc[0] + 3.0, char_loc[1] - 3.5, char_loc[2] + 1.2)
    cam_obj.keyframe_insert(data_path="location", frame=frames)
    target.location = (char_loc[0], char_loc[1], char_loc[2] + 1.0)

elif camera_shot == "pan_lateral":
    cam_obj.location = (-15, -18, roof_z * 0.7)
    cam_obj.keyframe_insert(data_path="location", frame=1)
    cam_obj.location = (15, -18, roof_z * 0.7)
    cam_obj.keyframe_insert(data_path="location", frame=frames)

else: # orbit_360
    radius = PARAMS.get("orbit_radius", 22.0)
    height = roof_z * 0.8
    # 4 Keyframes for smooth full circle orbit
    steps = 4
    for s in range(steps + 1):
        f = int(1 + (s / steps) * (frames - 1))
        theta = (s / steps) * math.pi * 0.9 # Arc shot
        x = math.cos(theta) * radius
        y = math.sin(theta) * radius
        cam_obj.location = (x, y, height)
        cam_obj.keyframe_insert(data_path="location", frame=f)

# 8. Render Still Thumbnail First (Frame halfway)
mid_frame = int(frames / 2)
scene.frame_set(mid_frame)
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUTPUT_THUMB
bpy.ops.render.render(write_still=True)
print(f"THUMBNAIL_DONE: {{OUTPUT_THUMB}}")

# 9. Render Video Clip (MP4 via FFMPEG)
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'HIGH'
scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
scene.render.filepath = OUTPUT_MP4

# Execute Animation Render
bpy.ops.render.render(animation=True)
print(f"VIDEO_DONE: {{OUTPUT_MP4}}")
'''
    return script
