import os
import json
from pathlib import Path
from typing import Dict, Any

def generate_bpy_script(params: Dict[str, Any], output_mp4: str, output_thumb: str) -> str:
    """
    Generates a high-end cinematic Blender Python script executed via `blender -b -P script.py`.
    Configured for:
    - Cycles OptiX GPU Hardware Raytracing (RTX 3060)
    - OptiX AI Denoising
    - Volumetric Atmosphere & Light Shafts (God Rays)
    - Cinematic Camera with Physical Depth of Field (Bokeh F1.8) & Motion Blur
    - Stylized Humanoid Character with Natural Pose
    - PBR Materials with Reflective Puddles & Architectural Lighting
    """
    params_json = json.dumps(params, ensure_ascii=False)
    mp4_escaped = output_mp4.replace("\\", "/")
    thumb_escaped = output_thumb.replace("\\", "/")

    script = f'''# High-End Cinematic Blender Script by Contentsmaker-3-Blender
import bpy
import math
import os
import json

PARAMS = json.loads({json.dumps(params_json)})
OUTPUT_MP4 = "{mp4_escaped}"
OUTPUT_THUMB = "{thumb_escaped}"

# 1. Reset Scene to clean state
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# Ensure world exists
if not scene.world:
    scene.world = bpy.data.worlds.new("World")
scene.world.use_nodes = True
world_nodes = scene.world.node_tree.nodes
world_links = scene.world.node_tree.links
bg_node = world_nodes.get("Background")
output_node = world_nodes.get("World Output")

# 2. Render Engine: Cycles OptiX Hardware Raytracing (High-End Default)
engine_type = PARAMS.get("engine", "CYCLES") # "CYCLES" or "EEVEE"

if engine_type == "CYCLES":
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU'
    try:
        cprefs = bpy.context.preferences.addons['cycles'].preferences
        cprefs.compute_device_type = 'OPTIX'
        cprefs.get_devices()
        for device in cprefs.devices:
            device.use = True
    except Exception as e:
        print(f"Cycles OptiX setup note: {{e}}")

    # High quality sampling & OptiX AI Denoiser
    scene.cycles.samples = PARAMS.get("samples", 128)
    scene.cycles.preview_samples = 32
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = 'OPTIX'
    except Exception:
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'

    # Light Bounces for realistic Global Illumination
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 6
    scene.cycles.volume_bounces = 2
else:
    for ee in ['BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE']:
        try:
            scene.render.engine = ee
            break
        except Exception:
            pass

# 3. Motion Blur
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.5

# 4. Format & Resolution
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

# 5. Volumetric Fog & Atmospheric Light Shafts (God Rays)
use_volumetrics = PARAMS.get("volumetric", True)
if use_volumetrics and output_node:
    vol_node = world_nodes.new(type="ShaderNodeVolumePrincipled")
    vol_node.inputs['Density'].default_value = 0.006 # Subtle cinematic haze
    vol_node.inputs['Anisotropy'].default_value = 0.65 # Forward light scatter (strong rays)
    vol_node.inputs['Color'].default_value = (0.7, 0.75, 0.85, 1.0)
    world_links.new(vol_node.outputs['Volume'], output_node.inputs['Volume'])

# 6. Advanced PBR Material Factory
def create_pbr_material(name, color=(0.8, 0.8, 0.8, 1.0), metallic=0.0, roughness=0.5, specular=0.5, ior=1.45, transmission=0.0, emission=0.0, emission_color=(1,1,1,1)):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        if 'Metallic' in bsdf.inputs: bsdf.inputs['Metallic'].default_value = metallic
        if 'Roughness' in bsdf.inputs: bsdf.inputs['Roughness'].default_value = roughness
        if 'IOR' in bsdf.inputs: bsdf.inputs['IOR'].default_value = ior
        if 'Transmission Weight' in bsdf.inputs:
            bsdf.inputs['Transmission Weight'].default_value = transmission
        elif 'Transmission' in bsdf.inputs:
            bsdf.inputs['Transmission'].default_value = transmission
        if emission > 0 and 'Emission Strength' in bsdf.inputs:
            bsdf.inputs['Emission Strength'].default_value = emission
            if 'Emission Color' in bsdf.inputs:
                bsdf.inputs['Emission Color'].default_value = emission_color
    return mat

# Base & PBR Materials
mat_ground = create_pbr_material("Mat_WetAsphalt", color=(0.04, 0.05, 0.07, 1.0), metallic=0.3, roughness=0.18, specular=0.9)
mat_dark_steel = create_pbr_material("Mat_DarkSteel", color=(0.12, 0.13, 0.16, 1.0), metallic=0.85, roughness=0.25)
mat_facade_panel = create_pbr_material("Mat_FacadePanel", color=(0.18, 0.20, 0.24, 1.0), metallic=0.4, roughness=0.4)
mat_glass = create_pbr_material("Mat_ReflectiveGlass", color=(0.08, 0.12, 0.18, 1.0), metallic=0.1, roughness=0.04, ior=1.52, transmission=0.85)
mat_char_suit = create_pbr_material("Mat_Suit", color=(0.08, 0.10, 0.14, 1.0), metallic=0.1, roughness=0.7)
mat_char_skin = create_pbr_material("Mat_Skin", color=(0.85, 0.65, 0.52, 1.0), roughness=0.55)

# Materials for Specific Architectural Photo (Urban Checker Tower)
mat_white_skin = create_pbr_material("Mat_WhiteSkin", color=(0.95, 0.95, 0.95, 1.0), roughness=0.28)
mat_punched_hole = create_pbr_material("Mat_PunchedHole", color=(0.04, 0.05, 0.08, 1.0), metallic=0.2, roughness=0.15)
mat_checker_dark = create_pbr_material("Mat_CheckerDark", color=(0.14, 0.16, 0.19, 1.0), metallic=0.3, roughness=0.35)
mat_accent_yellow = create_pbr_material("Mat_AccentYellow", color=(0.94, 0.74, 0.22, 1.0), roughness=0.4)
mat_accent_mint = create_pbr_material("Mat_AccentMint", color=(0.35, 0.78, 0.62, 1.0), roughness=0.4)
mat_red_awning = create_pbr_material("Mat_RedAwning", color=(0.88, 0.12, 0.15, 1.0), roughness=0.5)
mat_louver_fin = create_pbr_material("Mat_LouverFin", color=(0.20, 0.22, 0.26, 1.0), metallic=0.8, roughness=0.2)
mat_tree_leaves = create_pbr_material("Mat_TreeLeaves", color=(0.08, 0.35, 0.12, 1.0), roughness=0.6)

# 7. Ground Plane with Reflective Horizon & Sidewalk
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground_WetAsphalt"
ground.data.materials.append(mat_ground)

# Sidewalk (보도블럭)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, -6.0, 0.1))
sidewalk = bpy.context.active_object
sidewalk.scale = (40.0, 8.0, 0.2)
sidewalk.data.materials.append(mat_facade_panel)

# 8. Landmark Architecture (Urban Checker & Punched-Hole Tower)
building_style = PARAMS.get("building_style", "urban_checker_tower")
floors = PARAMS.get("floors", 16)
floor_height = 1.35
building_width = 8.8
building_depth = 6.8
roof_z = floors * floor_height

bldg_col = bpy.data.collections.new("HighRiseArchitecture")
scene.collection.children.link(bldg_col)

# --- Wing A: Left White Perforated Tower (원형 타공 스킨 타워) ---
wing_a_w = 4.2
wing_a_d = 6.8
wing_a_x = -2.2

# Main core slab
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wing_a_x, 0, roof_z / 2.0))
wing_a = bpy.context.active_object
wing_a.scale = (wing_a_w, wing_a_d, roof_z)
wing_a.data.materials.append(mat_white_skin)
bldg_col.objects.link(wing_a)
scene.collection.objects.unlink(wing_a)

# Array of Punched Circular Recesses (크고 작은 원형 타공 패턴)
import random
random.seed(42)
for f in range(floors):
    fz = (f + 0.5) * floor_height
    # Create 3-4 circular punched holes per floor on the front face
    hole_counts = 4
    for h in range(hole_counts):
        hx = wing_a_x - (wing_a_w * 0.38) + (h / (hole_counts - 1)) * (wing_a_w * 0.76)
        hy = -(wing_a_d / 2.0) - 0.02
        radius = random.choice([0.16, 0.24, 0.32, 0.20])
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=0.1, location=(hx, hy, fz + random.uniform(-0.15, 0.15)))
        hole = bpy.context.active_object
        hole.rotation_euler = (math.radians(90), 0, 0)
        hole.data.materials.append(mat_punched_hole)
        bldg_col.objects.link(hole)
        scene.collection.objects.unlink(hole)

# --- Wing B: Right Checkerboard Mosaic Tower (바둑판 커튼월 타워) ---
wing_b_w = 4.6
wing_b_d = 6.4
wing_b_x = 2.1

# Generate Checkerboard Grid Floor by Floor
for f in range(floors):
    fz = (f + 0.5) * floor_height
    # 4 Columns per floor
    cols = 4
    col_w = wing_b_w / cols
    for c in range(cols):
        cx = (wing_b_x - wing_b_w / 2.0) + (c + 0.5) * col_w
        cy = -(wing_b_d / 2.0)

        # Decide material pattern: Dark panel vs Mirror glass vs Color accent
        mod_idx = (f + c * 2) % 6
        if mod_idx in [0, 3]:
            mat_choice = mat_glass
        elif mod_idx in [1, 4]:
            mat_choice = mat_checker_dark
        elif mod_idx == 2:
            mat_choice = mat_accent_yellow
        else:
            mat_choice = mat_accent_mint

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, fz))
        panel = bpy.context.active_object
        panel.scale = (col_w * 0.94, 0.12, floor_height * 0.92)
        panel.data.materials.append(mat_choice)
        bldg_col.objects.link(panel)
        scene.collection.objects.unlink(panel)

# Main core mass behind Wing B
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(wing_b_x, 0.2, roof_z / 2.0))
wing_b_core = bpy.context.active_object
wing_b_core.scale = (wing_b_w, wing_b_d * 0.95, roof_z)
wing_b_core.data.materials.append(mat_checker_dark)
bldg_col.objects.link(wing_b_core)
scene.collection.objects.unlink(wing_b_core)

# --- Louver Side Fins on Right Edge (우측면 수평 루버) ---
louver_x = wing_b_x + (wing_b_w / 2.0) + 0.05
for f in range(int(floors * 1.8)):
    lz = f * (floor_height / 1.8) + 0.5
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(louver_x, 0.0, lz))
    fin = bpy.context.active_object
    fin.scale = (0.2, wing_b_d * 0.85, 0.04)
    fin.data.materials.append(mat_louver_fin)
    bldg_col.objects.link(fin)
    scene.collection.objects.unlink(fin)

# --- Ground Floor: Red Awning Canopy & Commercial Storefront (1층 레드 어닝) ---
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.5, -3.8, 1.6))
awning = bpy.context.active_object
awning.scale = (2.6, 1.2, 0.35)
awning.rotation_euler = (math.radians(15), 0, 0)
awning.data.materials.append(mat_red_awning)
bldg_col.objects.link(awning)
scene.collection.objects.unlink(awning)

# 1층 투명 블랙 로비 유리
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, -3.2, 1.2))
lobby = bpy.context.active_object
lobby.scale = (wing_a_w + wing_b_w, 0.2, 2.4)
lobby.data.materials.append(mat_glass)
bldg_col.objects.link(lobby)
scene.collection.objects.unlink(lobby)

# --- Street Trees (가로수 디테일) ---
for tx in [-6.5, 6.5]:
    # Trunk
    bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=3.0, location=(tx, -6.5, 1.5))
    trunk = bpy.context.active_object
    trunk.data.materials.append(mat_facade_panel)
    bldg_col.objects.link(trunk)
    scene.collection.objects.unlink(trunk)
    # Foliage Canopy
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.6, location=(tx, -6.5, 3.8))
    foliage = bpy.context.active_object
    foliage.scale = (1.2, 1.2, 1.8)
    foliage.data.materials.append(mat_tree_leaves)
    bldg_col.objects.link(foliage)
    scene.collection.objects.unlink(foliage)

# Surrounding City Skyline (Depth & Atmosphere)
import random
random.seed(101)
for i in range(22):
    angle = (i / 22.0) * math.pi * 2
    dist = random.uniform(22.0, 48.0)
    bx = math.cos(angle) * dist
    by = math.sin(angle) * dist
    bh = random.uniform(8.0, roof_z * 1.2)
    bw = random.uniform(4.0, 7.5)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, by, bh / 2.0))
    skyline = bpy.context.active_object
    skyline.scale = (bw, bw, bh)
    skyline.data.materials.append(mat_dark_steel if random.random() > 0.4 else mat_glass)
    bldg_col.objects.link(skyline)
    scene.collection.objects.unlink(skyline)

# 9. Stylized Humanoid 3D Character (Standing at Rooftop Balustrade)
char_col = bpy.data.collections.new("HeroCharacter")
scene.collection.children.link(char_col)

char_base_z = roof_z + 0.4
char_x = 0.0
char_y = -(building_width * 0.38) # Near railing looking outwards

# Legs
for lx in [-0.15, 0.15]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=0.85, location=(char_x + lx, char_y, char_base_z + 0.42))
    leg = bpy.context.active_object
    leg.data.materials.append(mat_char_suit)
    char_col.objects.link(leg)
    scene.collection.objects.unlink(leg)

# Torso (Suit Jacket)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(char_x, char_y, char_base_z + 1.15))
torso = bpy.context.active_object
torso.scale = (0.42, 0.28, 0.65)
torso.data.materials.append(mat_char_suit)
char_col.objects.link(torso)
scene.collection.objects.unlink(torso)

# Neck & Head
bpy.ops.mesh.primitive_cylinder_add(radius=0.07, depth=0.15, location=(char_x, char_y, char_base_z + 1.55))
neck = bpy.context.active_object
neck.data.materials.append(mat_char_skin)
char_col.objects.link(neck)
scene.collection.objects.unlink(neck)

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.18, location=(char_x, char_y, char_base_z + 1.74))
head = bpy.context.active_object
head.data.materials.append(mat_char_skin)
char_col.objects.link(head)
scene.collection.objects.unlink(head)

# Arms leaning forward towards railing
for ax, angle in [(-0.26, -0.2), (0.26, 0.2)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.065, depth=0.65, location=(char_x + ax, char_y - 0.1, char_base_z + 1.15))
    arm = bpy.context.active_object
    arm.rotation_euler = (math.radians(25), angle, 0)
    arm.data.materials.append(mat_char_suit)
    char_col.objects.link(arm)
    scene.collection.objects.unlink(arm)

# 10. Cinematic Lighting Master Setup (Volumetric God Rays)
lighting_preset = PARAMS.get("lighting", "cinematic_sunset")

if lighting_preset == "cyberpunk_neon":
    if bg_node:
        bg_node.inputs['Color'].default_value = (0.005, 0.006, 0.015, 1.0)
        bg_node.inputs['Strength'].default_value = 0.3

    # Key Cyan Spot (Forms strong volumetric beam through fog)
    bpy.ops.object.light_add(type='SPOT', location=(18, -22, roof_z + 14))
    l_key = bpy.context.active_object
    l_key.data.energy = 25000
    l_key.data.color = (0.0, 0.85, 1.0)
    l_key.data.spot_size = math.radians(45)
    l_key.data.shadow_soft_size = 0.5

    # Fill Magenta Rim
    bpy.ops.object.light_add(type='SPOT', location=(-20, 15, roof_z + 10))
    l_rim = bpy.context.active_object
    l_rim.data.energy = 18000
    l_rim.data.color = (1.0, 0.1, 0.6)
    l_rim.data.spot_size = math.radians(55)

    # Character Focus Glow
    bpy.ops.object.light_add(type='POINT', location=(char_x, char_y - 0.5, char_base_z + 2.2))
    l_char = bpy.context.active_object
    l_char.data.energy = 800
    l_char.data.color = (1.0, 0.9, 0.7)

else: # cinematic_sunset (Default Photorealistic)
    if bg_node:
        bg_node.inputs['Color'].default_value = (0.08, 0.03, 0.05, 1.0)
        bg_node.inputs['Strength'].default_value = 0.5

    # Low Golden Hour Sun (Creates long dramatic shadows and volumetric beam)
    bpy.ops.object.light_add(type='SUN', rotation=(math.radians(76), math.radians(8), math.radians(35)))
    sun = bpy.context.active_object
    sun.data.energy = 7.5
    sun.data.color = (1.0, 0.52, 0.18) # Warm golden amber
    sun.data.angle = math.radians(2.0) # Soft sun edges

    # Contrast Cool Blue Sky Fill
    bpy.ops.object.light_add(type='POINT', location=(-18, -15, roof_z + 12))
    sky_fill = bpy.context.active_object
    sky_fill.data.energy = 12000
    sky_fill.data.color = (0.15, 0.45, 0.95)

    # Character Silhouette Accent
    bpy.ops.object.light_add(type='SPOT', location=(char_x, char_y + 3.0, char_base_z + 2.5))
    rim = bpy.context.active_object
    rim.data.energy = 1200
    rim.data.color = (1.0, 0.75, 0.4)

# 11. Hollywood Physical Camera & Bokeh (DoF)
camera_shot = PARAMS.get("camera_shot", "orbit_360")
cam_data = bpy.data.cameras.new("CinemaCamera")
cam_obj = bpy.data.objects.new("CinemaCamera", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# Cinematic 50mm Prime Lens
cam_data.lens = PARAMS.get("focal_length", 50)

# Physical Depth of Field & Bokeh
cam_data.dof.use_dof = True
cam_data.dof.aperture_fstop = PARAMS.get("fstop", 1.8) # Shallow depth of field
cam_data.dof.aperture_blades = 7 # 7-blade cinematic iris bokeh

# Focus Target: Track hero character
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(char_x, char_y, char_base_z + 1.4))
focus_target = bpy.context.active_object
focus_target.name = "FocusTarget"
cam_data.dof.focus_object = focus_target

# Camera Track Constraint
track = cam_obj.constraints.new(type='TRACK_TO')
track.target = focus_target
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'

# Animate Camera Path
frames = scene.frame_end
if camera_shot == "tilt_up":
    # Cinematic Vertical Climb (Ideal for Shorts / Reels)
    cam_obj.location = (char_x + 9.0, char_y - 12.0, 3.0)
    cam_obj.keyframe_insert(data_path="location", frame=1)
    cam_obj.location = (char_x + 6.0, char_y - 7.0, char_base_z + 1.8)
    cam_obj.keyframe_insert(data_path="location", frame=frames)

elif camera_shot == "push_in":
    # Dramatic Push-In to Hero
    cam_obj.location = (char_x + 12.0, char_y - 15.0, char_base_z + 4.5)
    cam_obj.keyframe_insert(data_path="location", frame=1)
    cam_obj.location = (char_x + 2.8, char_y - 3.8, char_base_z + 1.6)
    cam_obj.keyframe_insert(data_path="location", frame=frames)

elif camera_shot == "pan_lateral":
    cam_obj.location = (char_x - 10.0, char_y - 8.0, char_base_z + 1.8)
    cam_obj.keyframe_insert(data_path="location", frame=1)
    cam_obj.location = (char_x + 10.0, char_y - 8.0, char_base_z + 1.8)
    cam_obj.keyframe_insert(data_path="location", frame=frames)

else: # orbit_360 Cinematic Arc
    radius = PARAMS.get("orbit_radius", 14.0)
    steps = 4
    for s in range(steps + 1):
        f = int(1 + (s / steps) * (frames - 1))
        angle = (s / steps) * math.pi * 0.75 - math.pi * 0.35
        cx = char_x + math.sin(angle) * radius
        cy = char_y - math.cos(angle) * radius
        cz = char_base_z + 1.8 + math.sin(s) * 0.8
        cam_obj.location = (cx, cy, cz)
        cam_obj.keyframe_insert(data_path="location", frame=f)

# 12. Render Still Thumbnail First (Frame halfway)
mid_frame = int(frames / 2)
scene.frame_set(mid_frame)
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUTPUT_THUMB
bpy.ops.render.render(write_still=True)
print(f"THUMBNAIL_DONE: {{OUTPUT_THUMB}}")

# 13. Render Video Clip (MP4 via FFMPEG)
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'HIGH'
scene.render.ffmpeg.ffmpeg_preset = 'GOOD'

base_video_path = OUTPUT_MP4.rsplit('.', 1)[0]
scene.render.filepath = base_video_path + "_"

# Execute Animation Render
bpy.ops.render.render(animation=True)

# Locate and rename the generated video to exact OUTPUT_MP4
import glob
matches = glob.glob(base_video_path + "_*.mp4")
if matches:
    latest = max(matches, key=os.path.getmtime)
    if os.path.exists(OUTPUT_MP4):
        try:
            os.remove(OUTPUT_MP4)
        except Exception:
            pass
    try:
        os.rename(latest, OUTPUT_MP4)
    except Exception as e:
        print(f"Rename note: {{e}}")

print(f"VIDEO_DONE: {{OUTPUT_MP4}}")
'''
    return script
