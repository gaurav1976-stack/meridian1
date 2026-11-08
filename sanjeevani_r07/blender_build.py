#!/usr/bin/env python3
"""Build Sanjeevani Vann R07 as a coordinated LOD300-equivalent concept model.

The model preserves the traced two-parcel geometry and road logic from R02,
while developing roads, dual pedestrian walks, drainage, landscape, villas,
wellness buildings, Van Nivas, clubhouse, waterfront terraces, sports, farms,
parking, lighting and camera views. It is a concept/co-ordination model, not a
surveyed BIM deliverable or construction model.
"""
from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

OUT = Path(os.environ.get("SV_OUTPUT", "outputs")).resolve()
OUT.mkdir(parents=True, exist_ok=True)
RENDERS = OUT / "renders"
RENDERS.mkdir(parents=True, exist_ok=True)
random.seed(1976)

# -----------------------------------------------------------------------------
# Source geometry: scaled re-trace of the supplied concept raster, in metres.
# -----------------------------------------------------------------------------
S = 100.0 / 162.0

def xy(p: Tuple[float, float]) -> Tuple[float, float]:
    return ((p[0] - 670.0) * S, (925.0 - p[1]) * S)

UP_PX = [(714,211),(866,149),(875,287),(885,379),(901,525),(879,590),(891,627),(894,660),(908,708),(864,739),(864,796),(811,837),(782,777),(747,762),(674,753),(601,739),(557,738),(434,728),(437,671),(677,711),(728,661)]
LO_PX = [(489,788),(594,767),(655,781),(678,780),(748,782),(795,876),(755,896),(690,878),(670,925),(622,895),(479,835)]
WATER_PX = [(429,737),(487,740),(542,736),(593,744),(639,750),(656,756),(653,773),(607,761),(575,766),(536,778),(470,795),(450,789),(441,768)]
MAIN_PX = [(652,921),(628,906),(637,884),(648,850),(661,810),(673,773),(681,736),(696,704),(721,674),(746,650),(743,605),(741,565),(753,551),(803,539),(870,523),(887,515),(887,491),(874,423),(867,417),(855,415),(810,428),(750,442),(735,437),(734,407),(733,352),(742,344),(787,333),(835,321),(862,308),(871,293),(870,266),(866,242),(855,239),(819,249),(779,256),(749,262)]
LOOP_PX = [(661,810),(621,781),(580,783),(536,802),(501,812),(489,830),(550,861),(607,893),(628,906)]
SPUR_PX = [(721,674),(758,692),(789,690),(835,677),(878,665)]
SPA_PX = [(681,736),(651,724),(627,712),(590,702),(547,695),(527,688),(491,686)]

UPPER = [xy(p) for p in UP_PX]
LOWER = [xy(p) for p in LO_PX]
WATER = [xy(p) for p in WATER_PX]
MAIN = [xy(p) for p in MAIN_PX]
LOOP = [xy(p) for p in LOOP_PX]
SPUR = [xy(p) for p in SPUR_PX]
SPA_ROAD = [xy(p) for p in SPA_PX]
ROADS = [(MAIN, 6.0, "Primary serpentine road"), (LOOP, 5.5, "Lower field loop"), (SPUR, 5.5, "Wellness and long-stay spur"), (SPA_ROAD, 4.5, "Clubhouse service road")]

VILLA_PX = [(740,231),(786,218),(824,203),(738,302),(778,296),(820,286),(790,359),(857,350),(771,409),(820,396),(753,469),(806,464),(850,459),(756,519),(801,513),(776,570),(827,566),(869,556)]
VILLAS = [xy(p) for p in VILLA_PX]
FACILITIES = {
    "consultation": (*xy((714,809)), 22.0, 18.0),
    "physio": (*xy((810,626)), 32.0, 20.0),
    "longstay": (*xy((807,716)), 36.0, 20.0),
    "parking": (*xy((694,853)), 36.0, 26.0),
    "clubhouse": (-82.0, 137.0, 52.0, 18.0),
    "gate": (*xy((640,891)), 12.0, 6.0),
}
TENNIS = (*xy((811,773)), 18.3, 36.6)
BASKETBALL = (*xy((848,766)), 19.0, 32.0)
MINIGOLF = (*xy((766,617)), 22.0, 28.0)
FARMS = [
    [xy(p) for p in [(506,819),(582,799),(625,810),(606,876),(554,852)]],
    [xy(p) for p in [(738,834),(764,830),(783,868),(751,882),(729,870)]],
]
PED_LINKS = [
    [xy(p) for p in q] for q in [
        [(673,773),(700,793),(714,796)], [(673,773),(699,824),(694,840)],
        [(758,692),(777,705),(807,700)], [(800,677),(805,647)],
        [(835,677),(853,710),(845,740)], [(777,705),(780,738),(804,743)],
        [(746,650),(765,628)], [(635,727),(620,742),(594,745)],
    ]
]

# -----------------------------------------------------------------------------
# Math and mesh helpers
# -----------------------------------------------------------------------------

def zfun(x: float, y: float) -> float:
    """Assumed stepped terrain: lower field plus gently rising upper parcel."""
    base = 0.3 + max(0.0, y - 90.0) * 0.055
    undulation = 0.35 * math.sin(x * 0.035) * math.cos(y * 0.027)
    return base + undulation


def point_in_poly(x: float, y: float, poly: Sequence[Tuple[float, float]]) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def dist2(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def catmull_rom(points: Sequence[Tuple[float, float]], samples_per_seg: int = 7) -> List[Tuple[float, float]]:
    if len(points) < 3:
        return list(points)
    p = [points[0]] + list(points) + [points[-1]]
    out: List[Tuple[float, float]] = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for j in range(samples_per_seg):
            t = j / float(samples_per_seg)
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2*p1[0]) + (-p0[0]+p2[0])*t + (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2 + (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
            y = 0.5 * ((2*p1[1]) + (-p0[1]+p2[1])*t + (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2 + (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
            out.append((x, y))
    out.append(points[-1])
    return out


def offset_polyline(points: Sequence[Tuple[float, float]], distance: float) -> List[Tuple[float, float]]:
    out = []
    for i, p in enumerate(points):
        prev = points[max(0, i - 1)]
        nxt = points[min(len(points) - 1, i + 1)]
        dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        out.append((p[0] + nx * distance, p[1] + ny * distance))
    return out


def nearest_road_angle(x: float, y: float) -> float:
    pts = catmull_rom(MAIN, 6)
    best = (1e18, 0.0)
    for i in range(len(pts) - 1):
        mx = (pts[i][0] + pts[i + 1][0]) * 0.5
        my = (pts[i][1] + pts[i + 1][1]) * 0.5
        d = (mx - x) ** 2 + (my - y) ** 2
        if d < best[0]:
            best = (d, math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0]))
    return best[1]


def polygon_centroid(poly: Sequence[Tuple[float, float]]) -> Tuple[float, float]:
    a = 0.0
    cx = cy = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    a *= 0.5
    if abs(a) < 1e-9:
        return poly[0]
    return cx / (6 * a), cy / (6 * a)

# -----------------------------------------------------------------------------
# Scene and materials
# -----------------------------------------------------------------------------

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.render.use_file_extension = True
try:
    scene.eevee.taa_render_samples = 64
    scene.eevee.use_gtao = True
    scene.eevee.gtao_distance = 4
    scene.eevee.gtao_factor = 1.25
    scene.eevee.use_bloom = True
except Exception:
    pass
try:
    scene.view_settings.look = "Medium High Contrast"
except Exception:
    pass
scene.render.image_settings.color_mode = "RGBA"
scene.render.fps = 30

# World: Nishita sky when available.
world = bpy.data.worlds.new("SV_World")
scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
wn.clear()
out = wn.new("ShaderNodeOutputWorld")
bg = wn.new("ShaderNodeBackground")
try:
    sky = wn.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(48)
    sky.sun_rotation = math.radians(130)
    sky.altitude = 0.4
    wl.new(sky.outputs["Color"], bg.inputs["Color"])
except Exception:
    bg.inputs["Color"].default_value = (0.55, 0.68, 0.82, 1)
bg.inputs["Strength"].default_value = 0.45
wl.new(bg.outputs["Background"], out.inputs["Surface"])


def collection(name: str, parent=None):
    col = bpy.data.collections.new(name)
    (parent or scene.collection).children.link(col)
    return col

COL = {
    "terrain": collection("SV_01_Terrain"),
    "roads": collection("SV_02_Roads_Walks_Drainage"),
    "landscape": collection("SV_03_Landscape"),
    "villas": collection("SV_04_Wellness_Villas"),
    "wellness": collection("SV_05_Wellness_ActiveLiving"),
    "longstay": collection("SV_06_Van_Nivas"),
    "clubhouse": collection("SV_07_Clubhouse_Waterfront"),
    "sports": collection("SV_08_Sports_Farms"),
    "parking": collection("SV_09_Arrival_Parking_Utilities"),
    "lighting": collection("SV_10_Lighting_People_Vehicles"),
    "fireflies": collection("SV_11_Fireflies_Night"),
    "cameras": collection("SV_12_Cameras"),
}


def mat(name: str, colour, roughness=0.55, metallic=0.0, transmission=0.0, alpha=1.0, emission=None, emission_strength=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        for key in ("Base Color",):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = (*colour[:3], colour[3] if len(colour) > 3 else 1.0)
        if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs: bsdf.inputs["Metallic"].default_value = metallic
        if "Transmission" in bsdf.inputs: bsdf.inputs["Transmission"].default_value = transmission
        if "Transmission Weight" in bsdf.inputs: bsdf.inputs["Transmission Weight"].default_value = transmission
        if "Alpha" in bsdf.inputs: bsdf.inputs["Alpha"].default_value = alpha
        if emission is not None:
            if "Emission" in bsdf.inputs: bsdf.inputs["Emission"].default_value = (*emission, 1.0)
            if "Emission Color" in bsdf.inputs: bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
            if "Emission Strength" in bsdf.inputs: bsdf.inputs["Emission Strength"].default_value = emission_strength
    m.diffuse_color = (*colour[:3], alpha)
    if alpha < 1.0:
        m.blend_method = "BLEND"
        m.use_screen_refraction = True
        m.show_transparent_back = False
    return m

MATS = {
    "terrain": mat("M_Terrain_Moss", (0.19, 0.31, 0.16, 1), 0.9),
    "site": mat("M_Site_Grass", (0.28, 0.43, 0.22, 1), 0.95),
    "asphalt": mat("M_Road_Asphalt", (0.075, 0.085, 0.082, 1), 0.78),
    "walk": mat("M_Walkway_WarmStone", (0.58, 0.50, 0.36, 1), 0.75),
    "curb": mat("M_Curb_LightStone", (0.62, 0.61, 0.55, 1), 0.85),
    "swale": mat("M_Swale_Planting", (0.13, 0.31, 0.15, 1), 1.0),
    "stone": mat("M_Local_Stone", (0.34, 0.28, 0.21, 1), 0.78),
    "plaster": mat("M_Earth_Plasters", (0.72, 0.66, 0.53, 1), 0.72),
    "timber": mat("M_Teak_Tone", (0.23, 0.10, 0.045, 1), 0.48),
    "roof": mat("M_Roof_Bronze", (0.16, 0.11, 0.07, 1), 0.48, 0.35),
    "glass": mat("M_Glass_Warm", (0.12, 0.25, 0.23, 1), 0.12, 0.05, 0.75, 0.42),
    "water": mat("M_Lake_Water", (0.045, 0.20, 0.23, 1), 0.12, 0.05, 0.82, 0.72),
    "deck": mat("M_Deck_Timber", (0.26, 0.12, 0.055, 1), 0.58),
    "court": mat("M_Sports_Court", (0.17, 0.36, 0.28, 1), 0.65),
    "court2": mat("M_Sports_Accent", (0.46, 0.23, 0.11, 1), 0.68),
    "white": mat("M_Line_White", (0.9, 0.9, 0.82, 1), 0.5),
    "soil": mat("M_Farm_Soil", (0.27, 0.16, 0.08, 1), 1.0),
    "leaf1": mat("M_Leaf_Teak_A", (0.12, 0.31, 0.10, 1), 0.95),
    "leaf2": mat("M_Leaf_Teak_B", (0.20, 0.42, 0.15, 1), 0.95),
    "leaf3": mat("M_Leaf_Teak_C", (0.32, 0.49, 0.20, 1), 0.95),
    "trunk": mat("M_Tree_Trunk", (0.22, 0.11, 0.045, 1), 0.95),
    "metal": mat("M_Dark_Metal", (0.055, 0.065, 0.06, 1), 0.35, 0.65),
    "light": mat("M_Warm_Light", (1.0, 0.52, 0.16, 1), 0.4, emission=(1.0, 0.38, 0.08), emission_strength=8.0),
    "firefly": mat("M_Firefly", (1.0, 0.78, 0.16, 1), 0.2, emission=(1.0, 0.65, 0.08), emission_strength=18.0),
}


def link_object(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def tag(obj, category: str, description: str = ""):
    obj["SV_LOD"] = "LOD300-equivalent concept"
    obj["SV_Category"] = category
    obj["SV_Status"] = "Proposed / subject to survey and approvals"
    if description:
        obj["SV_Description"] = description


def create_mesh(name: str, verts, faces, material=None, col=None):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    (col or scene.collection).objects.link(obj)
    if material:
        obj.data.materials.append(material)
    return obj


def create_polygon(name: str, pts2d, z=0.0, material=None, col=None):
    loop = [Vector((x, y, z)) for x, y in pts2d]
    tris = tessellate_polygon([loop])
    verts = [(v.x, v.y, v.z) for v in loop]
    index = {id(v): i for i, v in enumerate(loop)}
    faces = [tuple(index[id(v)] for v in tri) for tri in tris]
    return create_mesh(name, verts, faces, material, col)


def add_box(name: str, location, dimensions, material=None, col=None, bevel=0.08, rotation=(0,0,0), parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    if bevel > 0:
        mod = obj.modifiers.new("LOD300_Edge_Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    if parent:
        obj.parent = parent
    link_object(obj, col or scene.collection)
    return obj


def add_cylinder(name, location, radius, depth, material, col, vertices=12, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    if parent: obj.parent = parent
    link_object(obj, col)
    return obj


def create_ribbon(name: str, points: Sequence[Tuple[float,float]], width: float, z_offset: float, material, col):
    p = catmull_rom(points, 6)
    left, right = [], []
    for i, (x, y) in enumerate(p):
        p0 = p[max(0, i - 1)]
        p1 = p[min(len(p) - 1, i + 1)]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        left.append((x + nx * width * 0.5, y + ny * width * 0.5, zfun(x, y) + z_offset))
        right.append((x - nx * width * 0.5, y - ny * width * 0.5, zfun(x, y) + z_offset))
    verts = []
    for a, b in zip(left, right):
        verts.extend([a, b])
    faces = [(2*i, 2*i+1, 2*i+3, 2*i+2) for i in range(len(p)-1)]
    obj = create_mesh(name, verts, faces, material, col)
    tag(obj, "Road / pedestrian / landscape infrastructure", f"{width:.1f} m coordinated ribbon")
    return obj


def create_curve_tube(name, points, radius, material, col, z_offset=0.0, resolution=2):
    curve = bpy.data.curves.new(name + "_Curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = resolution
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for i, (x, y) in enumerate(points):
        spline.points[i].co = (x, y, zfun(x, y) + z_offset, 1)
    obj = bpy.data.objects.new(name, curve)
    col.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def create_empty(name, location, rotation_z, col, category, description=""):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "CUBE"
    obj.empty_display_size = 1.0
    obj.location = location
    obj.rotation_euler[2] = rotation_z
    col.objects.link(obj)
    tag(obj, category, description)
    return obj

# -----------------------------------------------------------------------------
# Terrain, water and circulation
# -----------------------------------------------------------------------------

all_pts = UPPER + LOWER
minx = min(x for x, _ in all_pts) - 65
maxx = max(x for x, _ in all_pts) + 65
miny = min(y for _, y in all_pts) - 55
maxy = max(y for _, y in all_pts) + 65
step = 6.0
xs = [minx + i * step for i in range(int((maxx - minx) / step) + 1)]
ys = [miny + i * step for i in range(int((maxy - miny) / step) + 1)]
verts = []
for y in ys:
    for x in xs:
        z = zfun(x, y) - 0.55
        verts.append((x, y, z))
faces = []
nx = len(xs)
for j in range(len(ys) - 1):
    for i in range(nx - 1):
        n = j * nx + i
        faces.append((n, n+1, n+nx+1, n+nx))
terrain = create_mesh("SV_Terrain_Assumed", verts, faces, MATS["terrain"], COL["terrain"])
tag(terrain, "Terrain", "Assumed contour model; replace with certified topographic survey")

upper_ground = create_polygon("SV_Upper_Parcel", UPPER, 0.0, MATS["site"], COL["terrain"])
lower_ground = create_polygon("SV_Lower_Parcel", LOWER, 0.0, MATS["site"], COL["terrain"])
for obj in (upper_ground, lower_ground):
    # Lift each vertex to terrain.
    for v in obj.data.vertices:
        v.co.z = zfun(v.co.x, v.co.y) - 0.18
    tag(obj, "Land parcel", "Scaled concept trace, not cadastral")

water_z = 0.10
lake = create_polygon("SV_Lake_And_Weir_Pool", WATER, water_z, MATS["water"], COL["terrain"])
tag(lake, "Water body", "Existing/proposed water edge subject to hydrology and ownership verification")

# Roads, dual walkways, buffers and swales.
for idx, (road, width, label) in enumerate(ROADS, start=1):
    smooth = catmull_rom(road, 7)
    create_ribbon(f"SV_Road_{idx:02}", road, width, 0.10, MATS["asphalt"], COL["roads"])
    for side in (-1, 1):
        walkway_center = offset_polyline(smooth, side * (width * 0.5 + 2.05))
        create_ribbon(f"SV_Walk_{idx:02}_{'L' if side>0 else 'R'}", walkway_center, 1.8, 0.16, MATS["walk"], COL["roads"])
        curb_center = offset_polyline(smooth, side * (width * 0.5 + 0.18))
        create_ribbon(f"SV_Curb_{idx:02}_{side}", curb_center, 0.28, 0.20, MATS["curb"], COL["roads"])
        swale_center = offset_polyline(smooth, side * (width * 0.5 + 3.55))
        create_ribbon(f"SV_Swale_{idx:02}_{side}", swale_center, 1.25, 0.02, MATS["swale"], COL["roads"])
    # Dashed centre markings.
    for i in range(4, len(smooth)-2, 16):
        p0, p1 = smooth[i], smooth[min(i+4, len(smooth)-1)]
        create_ribbon(f"SV_RoadMark_{idx:02}_{i:03}", [p0, p1], 0.10, 0.18, MATS["white"], COL["roads"])

for i, link in enumerate(PED_LINKS, 1):
    create_ribbon(f"SV_Ped_Link_{i:02}", link, 2.0, 0.17, MATS["walk"], COL["roads"])

# Cul-de-sac at the road end.
cx, cy = MAIN[-1]
for radius, material, zoff, name in [(13.2, MATS["walk"], 0.12, "OuterWalk"), (10.5, MATS["asphalt"], 0.15, "Road"), (4.2, MATS["site"], 0.20, "Island")]:
    pts = [(cx + math.cos(a)*radius, cy + math.sin(a)*radius) for a in np_angles := [2*math.pi*i/64 for i in range(64)]]
    obj = create_polygon(f"SV_CulDeSac_{name}", pts, 0, material, COL["roads"])
    for v in obj.data.vertices: v.co.z = zfun(v.co.x, v.co.y) + zoff
    tag(obj, "Cul-de-sac", "Terminal turning head and landscaped island")

# Boundary fence / survey line.
for name, poly in [("Upper", UPPER), ("Lower", LOWER)]:
    create_curve_tube(f"SV_{name}_Boundary", list(poly)+[poly[0]], 0.08, MATS["curb"], COL["terrain"], z_offset=0.35)

# -----------------------------------------------------------------------------
# Efficient tree and shrub instances
# -----------------------------------------------------------------------------

def make_tree_asset(name: str, height: float, canopy_scale: Tuple[float,float,float], leaf_mat):
    asset = collection(name)
    add_cylinder(name+"_Trunk", (0,0,height*0.36), 0.22, height*0.72, MATS["trunk"], asset, vertices=10)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1, location=(0,0,height*0.76))
    canopy = bpy.context.object
    canopy.name = name+"_Canopy"
    canopy.scale = canopy_scale
    canopy.data.materials.append(leaf_mat)
    link_object(canopy, asset)
    asset.hide_render = False
    return asset

TREE_ASSETS = [
    make_tree_asset("TreeAsset_Teak_A", 8.0, (2.8, 2.4, 3.0), MATS["leaf1"]),
    make_tree_asset("TreeAsset_Teak_B", 10.0, (3.2, 2.8, 3.8), MATS["leaf2"]),
    make_tree_asset("TreeAsset_Teak_C", 6.5, (2.2, 2.0, 2.4), MATS["leaf3"]),
]
for c in TREE_ASSETS:
    scene.collection.children.unlink(c)  # Keep as data-block, instantiate only.


def add_tree_instance(name: str, x: float, y: float, scale: float = 1.0, rotation: float = 0.0):
    obj = bpy.data.objects.new(name, None)
    obj.instance_type = "COLLECTION"
    obj.instance_collection = random.choice(TREE_ASSETS)
    obj.location = (x, y, zfun(x, y))
    obj.rotation_euler[2] = rotation
    obj.scale = (scale, scale, scale)
    COL["landscape"].objects.link(obj)
    tag(obj, "Existing/proposed tree", "Concept tree instance; arboricultural survey required")
    return obj

# Exclusion zones for roads/facilities/villas.
exclusions = [(x, y, 10.5) for x, y in VILLAS]
for x, y, w, d in FACILITIES.values(): exclusions.append((x, y, max(w,d)*0.65))
for _ in range(900):
    x = random.uniform(minx+15, maxx-15)
    y = random.uniform(miny+15, maxy-15)
    in_site = point_in_poly(x, y, UPPER) or point_in_poly(x, y, LOWER)
    if not in_site or point_in_poly(x, y, WATER):
        continue
    if any((x-ex)**2 + (y-ey)**2 < r*r for ex,ey,r in exclusions):
        continue
    # Keep road corridor reasonably clear.
    road_near = False
    for road, width, _ in ROADS:
        for p in catmull_rom(road, 4)[::5]:
            if dist2((x,y), p) < (width*0.5+5.0)**2:
                road_near = True; break
        if road_near: break
    if road_near:
        continue
    add_tree_instance(f"SV_Tree_{len(COL['landscape'].objects):04}", x, y, random.uniform(0.65, 1.25), random.random()*math.tau)
    if len(COL["landscape"].objects) >= 340:
        break

# -----------------------------------------------------------------------------
# Architectural components
# -----------------------------------------------------------------------------

def add_local_box(parent, name, loc, dims, material, col, bevel=0.06, rot=(0,0,0)):
    obj = add_box(name, loc, dims, material, col, bevel=bevel, rotation=rot, parent=parent)
    return obj


def add_screen(parent, prefix, x0, y, z0, count, span, height, depth, col):
    for i in range(count):
        x = x0 - span*0.5 + (i+0.5)*span/count
        add_local_box(parent, f"{prefix}_Slat_{i+1:02}", (x,y,z0), (0.09,depth,height), MATS["timber"], col, bevel=0.015)


def create_villa(index: int, x: float, y: float):
    angle = nearest_road_angle(x, y) + math.pi * 0.5
    z = zfun(x,y)
    p = create_empty(f"SV_Villa_{index:02}", (x,y,z), angle, COL["villas"], "Wellness villa", "168 m² enclosed plus deep verandah; adaptable single-level pavilion")
    add_local_box(p, f"V{index:02}_Foundation", (0,0,0.05), (15.2,13.2,0.35), MATS["stone"], COL["villas"], 0.04)
    add_local_box(p, f"V{index:02}_Floor", (0,-0.2,0.28), (14.0,11.8,0.25), MATS["plaster"], COL["villas"], 0.03)
    # Stone thermal core and plaster service wall.
    add_local_box(p, f"V{index:02}_StoneCore", (-5.2,1.0,1.85), (2.5,8.2,3.25), MATS["stone"], COL["villas"], 0.12)
    add_local_box(p, f"V{index:02}_RearWall", (0,5.72,1.75), (13.8,0.28,3.0), MATS["plaster"], COL["villas"], 0.04)
    add_local_box(p, f"V{index:02}_SideWallL", (-6.85,1.5,1.75), (0.28,8.4,3.0), MATS["plaster"], COL["villas"], 0.04)
    add_local_box(p, f"V{index:02}_SideWallR", (6.85,1.7,1.75), (0.28,8.0,3.0), MATS["plaster"], COL["villas"], 0.04)
    # Front glass, entry door and timber screen.
    add_local_box(p, f"V{index:02}_GlassFront", (1.0,-4.78,1.72), (8.8,0.10,2.75), MATS["glass"], COL["villas"], 0.01)
    add_local_box(p, f"V{index:02}_EntryDoor", (5.55,-4.75,1.55), (1.45,0.16,2.45), MATS["timber"], COL["villas"], 0.03)
    add_screen(p, f"V{index:02}_Screen", -3.4, -4.98, 1.7, 9, 4.0, 3.0, 0.12, COL["villas"])
    # Internal partitions, kitchen and wardrobes.
    add_local_box(p, f"V{index:02}_PartitionA", (1.8,1.5,1.55), (0.18,7.0,2.7), MATS["plaster"], COL["villas"], 0.02)
    add_local_box(p, f"V{index:02}_PartitionB", (4.3,1.2,1.55), (4.8,0.18,2.7), MATS["plaster"], COL["villas"], 0.02)
    add_local_box(p, f"V{index:02}_Kitchen", (-1.8,3.8,0.78), (4.4,0.7,1.0), MATS["timber"], COL["villas"], 0.04)
    add_local_box(p, f"V{index:02}_Bed", (4.3,3.2,0.62), (3.2,2.1,0.65), MATS["plaster"], COL["villas"], 0.15)
    add_local_box(p, f"V{index:02}_Sofa", (-1.5,-1.2,0.72), (3.5,1.2,0.85), MATS["plaster"], COL["villas"], 0.15)
    # Verandah and roof.
    add_local_box(p, f"V{index:02}_Verandah", (0,-6.2,0.35), (14.2,3.1,0.22), MATS["deck"], COL["villas"], 0.03)
    for colx in (-6.3, -2.1, 2.1, 6.3):
        add_local_box(p, f"V{index:02}_VerandahColumn_{colx}", (colx,-7.1,1.85), (0.16,0.16,3.05), MATS["timber"], COL["villas"], 0.02)
    add_local_box(p, f"V{index:02}_Roof", (0,0.0,3.62), (16.4,14.8,0.34), MATS["roof"], COL["villas"], 0.12, rot=(0,math.radians(2.2),0))
    add_local_box(p, f"V{index:02}_Clerestory", (0,4.75,3.05), (6.5,0.10,0.55), MATS["glass"], COL["villas"], 0.01)
    # Garden court and stepping path.
    add_local_box(p, f"V{index:02}_Planter", (-5.4,-6.3,0.55), (2.0,0.75,0.45), MATS["stone"], COL["villas"], 0.06)
    for j in range(5):
        add_local_box(p, f"V{index:02}_Step_{j}", (5.5,-8.5-j*0.75,0.16), (1.2,0.55,0.10), MATS["walk"], COL["villas"], 0.03)
    return p

for i, (vx,vy) in enumerate(VILLAS, 1):
    create_villa(i, vx, vy)


def create_consultation():
    x,y,w,d = FACILITIES["consultation"]
    z = zfun(x,y)
    p = create_empty("SV_Wellness_Consultation_Centre", (x,y,z), math.radians(-12), COL["wellness"], "Wellness consultation and therapy", "GP, nutrition, first aid and private therapy rooms")
    add_local_box(p, "WC_Base", (0,0,0.1), (24,20,0.3), MATS["stone"], COL["wellness"], 0.05)
    # U-shaped wings around healing courtyard.
    add_local_box(p, "WC_WestWing", (-7.0,1.2,1.9), (7.0,15.0,3.4), MATS["plaster"], COL["wellness"], 0.12)
    add_local_box(p, "WC_EastWing", (7.0,1.2,1.9), (7.0,15.0,3.4), MATS["plaster"], COL["wellness"], 0.12)
    add_local_box(p, "WC_BackWing", (0,7.1,1.9), (21.0,3.2,3.4), MATS["stone"], COL["wellness"], 0.12)
    add_local_box(p, "WC_GlassLobby", (0,-6.6,1.75), (7.0,0.12,2.8), MATS["glass"], COL["wellness"], 0.01)
    add_local_box(p, "WC_Courtyard", (0,1.2,0.28), (6.0,8.5,0.18), MATS["walk"], COL["wellness"], 0.03)
    add_local_box(p, "WC_RoofWest", (-7.0,1.2,3.8), (8.0,17.0,0.35), MATS["roof"], COL["wellness"], 0.10)
    add_local_box(p, "WC_RoofEast", (7.0,1.2,3.8), (8.0,17.0,0.35), MATS["roof"], COL["wellness"], 0.10)
    add_local_box(p, "WC_RoofBack", (0,7.1,3.8), (22.5,4.2,0.35), MATS["roof"], COL["wellness"], 0.10)
    for sx in (-9.5,9.5):
        for sy in (-4.5,-1.5,1.5,4.5):
            add_local_box(p, f"WC_Window_{sx}_{sy}", (sx,sy,1.9), (0.12,2.1,1.6), MATS["glass"], COL["wellness"], 0.01)
    add_screen(p, "WC_EntryScreen", 0, -8.0, 1.8, 12, 9.0, 3.1, 0.12, COL["wellness"])
    return p


def create_physio():
    x,y,w,d = FACILITIES["physio"]
    z = zfun(x,y)
    p = create_empty("SV_Physio_Gym_ActiveLiving", (x,y,z), math.radians(7), COL["wellness"], "Physio, gym and active living", "Movement gym, mobility studio, therapy rooms and outdoor movement garden")
    add_local_box(p, "PG_Base", (0,0,0.1), (34,22,0.35), MATS["stone"], COL["wellness"], 0.05)
    add_local_box(p, "PG_MainHall", (2.5,0,2.6), (25.0,18.0,4.8), MATS["plaster"], COL["wellness"], 0.12)
    add_local_box(p, "PG_TherapyWing", (-13.0,0,2.0), (8.0,18.0,3.6), MATS["stone"], COL["wellness"], 0.12)
    add_local_box(p, "PG_GlassSouth", (2.5,-9.0,2.5), (22.0,0.12,3.8), MATS["glass"], COL["wellness"], 0.01)
    add_local_box(p, "PG_Roof", (0,0,5.15), (36,24,0.42), MATS["roof"], COL["wellness"], 0.12, rot=(0,math.radians(-2.0),0))
    add_screen(p, "PG_SunScreen", 2.5,-9.4,2.5,24,25,4.1,0.10,COL["wellness"])
    # Gait lane and outdoor circuit.
    add_local_box(p, "PG_GaitLane", (3.0,-12.0,0.18), (28.0,1.6,0.12), MATS["walk"], COL["wellness"], 0.03)
    for i in range(8):
        add_local_box(p, f"PG_OutdoorStation_{i:02}", (-13+i*4.0,-14.2,0.65), (0.35,0.35,1.1), MATS["metal"], COL["wellness"], 0.04)
    return p


def create_longstay():
    x,y,w,d = FACILITIES["longstay"]
    z = zfun(x,y)
    p = create_empty("SV_Van_Nivas_LongStay", (x,y,z), math.radians(-4), COL["longstay"], "Long-stay residences", "24 studios over three levels with shaded balconies and separate staff access")
    add_local_box(p, "VN_Base", (0,0,0.10), (38,22,0.35), MATS["stone"], COL["longstay"], 0.05)
    for floor in range(3):
        fz = 1.9 + floor*3.35
        add_local_box(p, f"VN_Floor_{floor+1}", (0,0,fz), (34.0,17.0,3.15), MATS["plaster"], COL["longstay"], 0.10)
        add_local_box(p, f"VN_Balcony_{floor+1}", (0,-9.2,fz-1.25), (35.5,2.1,0.22), MATS["deck"], COL["longstay"], 0.03)
        for i in range(8):
            wx = -14.0 + i*4.0
            add_local_box(p, f"VN_Glass_{floor+1}_{i+1}", (wx,-8.53,fz), (2.7,0.10,2.1), MATS["glass"], COL["longstay"], 0.01)
            add_local_box(p, f"VN_Screen_{floor+1}_{i+1}", (wx+1.45,-9.5,fz), (0.10,0.25,2.55), MATS["timber"], COL["longstay"], 0.02)
    add_local_box(p, "VN_Core", (0,1.5,5.0), (5.0,12.0,10.0), MATS["stone"], COL["longstay"], 0.15)
    add_local_box(p, "VN_Roof", (0,0,10.6), (39.0,23.0,0.42), MATS["roof"], COL["longstay"], 0.12)
    # Separate staff wing.
    add_local_box(p, "VN_StaffWing", (23,4.0,3.4), (10.0,13.0,6.4), MATS["plaster"], COL["longstay"], 0.10)
    add_local_box(p, "VN_StaffRoof", (23,4.0,6.7), (11.5,14.5,0.35), MATS["roof"], COL["longstay"], 0.08)
    return p


def create_clubhouse():
    x,y,w,d = FACILITIES["clubhouse"]
    z = zfun(x,y)
    p = create_empty("SV_Lakeside_Clubhouse", (x,y,z), math.radians(-3), COL["clubhouse"], "Clubhouse and waterfront", "Reception, dining, wellness lounge, flexible gathering and layered lake terraces")
    add_local_box(p, "CH_Base", (0,0,0.12), (54,20,0.38), MATS["stone"], COL["clubhouse"], 0.06)
    add_local_box(p, "CH_StoneCoreWest", (-21,2.0,2.25), (8.0,14.0,4.2), MATS["stone"], COL["clubhouse"], 0.14)
    add_local_box(p, "CH_StoneCoreEast", (21,2.0,2.25), (8.0,14.0,4.2), MATS["stone"], COL["clubhouse"], 0.14)
    add_local_box(p, "CH_GlassHall", (0,1.0,2.2), (34.0,13.0,4.0), MATS["glass"], COL["clubhouse"], 0.02)
    add_local_box(p, "CH_BackWall", (0,7.4,2.3), (50.0,0.35,4.1), MATS["plaster"], COL["clubhouse"], 0.05)
    add_local_box(p, "CH_Roof", (0,0,4.55), (58.0,23.0,0.48), MATS["roof"], COL["clubhouse"], 0.14, rot=(0,math.radians(1.5),0))
    for cx in range(-24,25,6):
        add_local_box(p, f"CH_Column_{cx}", (cx,-8.2,2.2), (0.18,0.18,4.0), MATS["timber"], COL["clubhouse"], 0.02)
    add_local_box(p, "CH_Verandah", (0,-9.5,0.38), (54.0,5.0,0.25), MATS["deck"], COL["clubhouse"], 0.03)
    # Three waterfront terraces stepping towards water.
    for level, (yy, depth, drop) in enumerate([(-13.2,5.0,0.0),(-17.3,4.2,-0.38),(-20.9,3.3,-0.74)],1):
        add_local_box(p, f"CH_Terrace_{level}", (0,yy,0.26+drop), (48.0-level*3.0,depth,0.24), MATS["walk"] if level<3 else MATS["deck"], COL["clubhouse"], 0.04)
        for sx in (-20,-10,0,10,20):
            add_local_box(p, f"CH_Seat_{level}_{sx}", (sx,yy-0.3,0.62+drop), (2.2,0.65,0.42), MATS["stone"], COL["clubhouse"], 0.06)
    # Accessible ramp and restrained cascade channels.
    add_local_box(p, "CH_AccessibleRamp", (22,-17.0,-0.05), (2.2,16.0,0.18), MATS["walk"], COL["clubhouse"], 0.03, rot=(math.radians(2.8),0,0))
    for channel_x in (-8,0,8):
        add_local_box(p, f"CH_Cascade_{channel_x}", (channel_x,-22.3,-0.45), (4.0,8.0,0.12), MATS["water"], COL["clubhouse"], 0.02, rot=(math.radians(3.0),0,0))
    return p

CONSULT = create_consultation()
PHYSIO = create_physio()
LONGSTAY = create_longstay()
CLUBHOUSE = create_clubhouse()

# Gate and arrival canopy.
gx,gy,gw,gd = FACILITIES["gate"]
gz = zfun(gx,gy)
gate = create_empty("SV_Lower_Field_Entrance", (gx,gy,gz), math.radians(-12), COL["parking"], "Arrival gate", "Lower-field entrance, security, drop-off and wayfinding")
add_local_box(gate,"GateStonePierL",(-5,0,1.9),(1.2,1.2,3.8),MATS["stone"],COL["parking"],0.10)
add_local_box(gate,"GateStonePierR",(5,0,1.9),(1.2,1.2,3.8),MATS["stone"],COL["parking"],0.10)
add_local_box(gate,"GateCanopy",(0,0,4.0),(13.5,5.5,0.35),MATS["roof"],COL["parking"],0.10)
add_local_box(gate,"GateHouse",(-7.5,3.0,1.6),(4.2,5.0,3.0),MATS["plaster"],COL["parking"],0.08)

# Surface parking, bays, EV and solar pergola.
px,py,pw,pd = FACILITIES["parking"]
pz = zfun(px,py)
park = create_empty("SV_Surface_Parking", (px,py,pz), math.radians(-6), COL["parking"], "Surface parking", "Landscaped Phase 1 parking with accessible and EV bays")
add_local_box(park,"ParkingSurface",(0,0,0.08),(38,28,0.18),MATS["asphalt"],COL["parking"],0.03)
for row_y in (-8,8):
    for i in range(8):
        bx = -15.5 + i*4.4
        add_local_box(park,f"ParkingBayLine_{row_y}_{i}",(bx,row_y,0.20),(0.08,5.0,0.04),MATS["white"],COL["parking"],0.0)
        if i in (1,3,5,7):
            # Simple parked car.
            body = add_local_box(park,f"Car_{row_y}_{i}",(bx+1.7,row_y,0.75),(1.8,4.2,1.05),MATS["metal"],COL["lighting"],0.18)
for sx in (-12,0,12):
    add_local_box(park,f"SolarPergolaRoof_{sx}",(sx,0,3.4),(10.0,8.0,0.22),MATS["roof"],COL["parking"],0.05,rot=(0,math.radians(8),0))
    for sy in (-3,3): add_local_box(park,f"SolarPergolaColumn_{sx}_{sy}",(sx,sy,1.7),(0.18,0.18,3.4),MATS["metal"],COL["parking"],0.02)

# -----------------------------------------------------------------------------
# Sports, farms and landscape detail
# -----------------------------------------------------------------------------

def create_court(name, data, material, accent, is_tennis=False):
    x,y,w,d = data
    z = zfun(x,y)
    p = create_empty(name,(x,y,z),0,COL["sports"],"Sports facility","Outdoor movement and coaching")
    add_local_box(p,name+"_Slab",(0,0,0.10),(w,d,0.20),material,COL["sports"],0.03)
    # Perimeter and centre lines.
    for sx in (-w/2+0.15,w/2-0.15): add_local_box(p,name+f"_LineX{sx}",(sx,0,0.22),(0.08,d-0.4,0.035),MATS["white"],COL["sports"],0)
    for sy in (-d/2+0.15,d/2-0.15): add_local_box(p,name+f"_LineY{sy}",(0,sy,0.22),(w-0.4,0.08,0.035),MATS["white"],COL["sports"],0)
    add_local_box(p,name+"_CentreLine",(0,0,0.22),(w-0.4,0.08,0.035),MATS["white"],COL["sports"],0)
    if is_tennis:
        add_local_box(p,name+"_Net",(0,0,0.85),(w,0.05,1.25),MATS["metal"],COL["sports"],0)
    else:
        for sy in (-d/2+2.0,d/2-2.0):
            add_local_box(p,name+f"_HoopPost{sy}",(0,sy,1.6),(0.12,0.12,3.2),MATS["metal"],COL["sports"],0.02)
    return p

create_court("SV_Tennis_Court", TENNIS, MATS["court"], MATS["court2"], True)
create_court("SV_Basketball_Court", BASKETBALL, MATS["court2"], MATS["court"], False)

mx,my,mw,md = MINIGOLF
mg = create_empty("SV_MiniGolf_6Hole",(mx,my,zfun(mx,my)),math.radians(7),COL["sports"],"Mini golf","Six-hole family recreation garden")
for i in range(6):
    xx = -8 + (i%3)*8
    yy = -9 + (i//3)*12
    add_local_box(mg,f"MG_Green_{i+1}",(xx,yy,0.10),(6.2,8.0,0.16),MATS["site"],COL["sports"],0.8)
    add_cylinder(f"MG_Flag_{i+1}",(mx+xx,my+yy,zfun(mx+xx,my+yy)+1.0),0.04,1.8,MATS["metal"],COL["sports"],8)

for fi, farm_poly in enumerate(FARMS,1):
    cx_f,cy_f = polygon_centroid(farm_poly)
    farm = create_empty(f"SV_Herb_Farm_{fi}",(cx_f,cy_f,zfun(cx_f,cy_f)),0,COL["sports"],"Herb and food garden","Medicinal, culinary and seasonal organic cultivation")
    xs_f=[p[0] for p in farm_poly]; ys_f=[p[1] for p in farm_poly]
    spanx=max(xs_f)-min(xs_f); spany=max(ys_f)-min(ys_f)
    for r in range(7):
        yy=-spany*0.35+r*(spany*0.7/6)
        add_local_box(farm,f"Farm{fi}_Bed_{r}",(0,yy,0.22),(spanx*0.72,1.1,0.32),MATS["soil"],COL["sports"],0.12)
        for c in range(12):
            xx=-spanx*0.32+c*(spanx*0.64/11)
            add_local_box(farm,f"Farm{fi}_Plant_{r}_{c}",(xx,yy,0.55),(0.22,0.22,0.45),random.choice([MATS["leaf1"],MATS["leaf2"],MATS["leaf3"]]),COL["sports"],0.08)
    if fi==1:
        add_local_box(farm,"FarmGreenhouse",(spanx*0.18,spany*0.22,1.6),(12.0,6.0,3.0),MATS["glass"],COL["sports"],0.10)
        add_local_box(farm,"FarmGreenhouseRoof",(spanx*0.18,spany*0.22,3.3),(13.0,7.0,0.18),MATS["glass"],COL["sports"],0.03,rot=(0,math.radians(12),0))

# -----------------------------------------------------------------------------
# Road furniture, people, lighting and fireflies
# -----------------------------------------------------------------------------

def sample_polyline(points, spacing=30.0):
    smooth = catmull_rom(points, 7)
    out = []
    acc = 0.0
    last = smooth[0]
    for p in smooth[1:]:
        seg = math.hypot(p[0]-last[0],p[1]-last[1])
        acc += seg
        if acc >= spacing:
            out.append(p); acc=0.0
        last=p
    return out

for ri,(road,width,label) in enumerate(ROADS,1):
    pts=catmull_rom(road,7)
    for side in (-1,1):
        furniture=offset_polyline(pts,side*(width*0.5+2.9))
        for j,pnt in enumerate(furniture[::42]):
            x,y=pnt; z=zfun(x,y)
            add_cylinder(f"SV_LightPole_{ri}_{side}_{j}",(x,y,z+1.8),0.06,3.6,MATS["metal"],COL["lighting"],10)
            add_cylinder(f"SV_Lamp_{ri}_{side}_{j}",(x,y,z+3.65),0.16,0.18,MATS["light"],COL["lighting"],12)
        for j,pnt in enumerate(furniture[20::80]):
            x,y=pnt; z=zfun(x,y)
            add_box(f"SV_Bench_{ri}_{side}_{j}",(x,y,z+0.35),(1.8,0.55,0.18),MATS["timber"],COL["lighting"],0.08)

# Simple people for scale near key precincts.
for i,(x,y) in enumerate([(20,65),(25,70),(35,76),(78,175),(92,182),(75,130),(92,128),(-78,122),(-88,118),(-70,115),(85,95),(110,98)]):
    z=zfun(x,y)
    add_cylinder(f"PersonBody_{i}",(x,y,z+0.85),0.18,1.35,MATS["plaster"],COL["lighting"],12)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.19, location=(x,y,z+1.68))
    head=bpy.context.object;head.name=f"PersonHead_{i}";head.data.materials.append(MATS["stone"]);link_object(head,COL["lighting"])

# Fireflies: visible primarily in night render.
for i in range(140):
    x=random.uniform(15,145);y=random.uniform(220,420)
    if not point_in_poly(x,y,UPPER): continue
    z=zfun(x,y)+random.uniform(0.8,4.5)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=random.uniform(0.025,0.06),location=(x,y,z))
    f=bpy.context.object;f.name=f"SV_Firefly_{i:03}";f.data.materials.append(MATS["firefly"]);link_object(f,COL["fireflies"])

# -----------------------------------------------------------------------------
# Lighting, cameras and render views
# -----------------------------------------------------------------------------

bpy.ops.object.light_add(type="SUN", location=(0,0,140))
sun=bpy.context.object;sun.name="SV_Sun";sun.data.energy=3.0;sun.data.angle=math.radians(4.0);sun.rotation_euler=(math.radians(28),math.radians(-18),math.radians(125));link_object(sun,COL["lighting"])

bpy.ops.object.light_add(type="AREA", location=(-80,70,80))
fill=bpy.context.object;fill.name="SV_Sky_Fill";fill.data.energy=950;fill.data.shape="DISK";fill.data.size=90;fill.rotation_euler=(0,0,0);link_object(fill,COL["lighting"])

def track_to(obj, target):
    direction=Vector(target)-obj.location
    obj.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()


def add_camera(name, location, target, lens=45, ortho=None):
    data=bpy.data.cameras.new(name+"_Data")
    cam=bpy.data.objects.new(name,data)
    COL["cameras"].objects.link(cam)
    cam.location=location
    data.lens=lens
    if ortho is not None:
        data.type="ORTHO";data.ortho_scale=ortho
    track_to(cam,target)
    return cam

CAMERAS = {
    "01_master_aerial_south": add_camera("C01_Master_Aerial_South",(155,-105,185),(20,195,6),52),
    "02_master_aerial_reverse": add_camera("C02_Master_Aerial_Reverse",(-215,430,175),(5,190,8),55),
    "03_lower_field_arrival": add_camera("C03_Lower_Field_Arrival",(-62,-12,15),(-5,55,4),38),
    "04_serpentine_road_walk": add_camera("C04_Serpentine_Road_Walk",(0,52,5.5),(55,125,4.5),32),
    "05_villa_cluster": add_camera("C05_Villa_Cluster",(162,335,38),(75,335,8),48),
    "06_villa_close": add_camera("C06_Villa_Close",(122,290,9),(88,310,5),40),
    "07_wellness_consultation": add_camera("C07_Wellness_Consultation",(-24,38,14),(27,72,4),42),
    "08_physio_active_living": add_camera("C08_Physio_ActiveLiving",(145,142,17),(86,185,5),43),
    "09_van_nivas": add_camera("C09_Van_Nivas",(150,82,25),(84,130,8),48),
    "10_clubhouse_arrival": add_camera("C10_Clubhouse_Arrival",(-160,150,16),(-82,137,5),42),
    "11_waterfront_terraces": add_camera("C11_Waterfront_Terraces",(-132,74,10),(-82,125,2.5),38),
    "12_sports_farms": add_camera("C12_Sports_Farms",(175,25,80),(60,100,4),50),
    "13_herb_gardens": add_camera("C13_Herb_Gardens",(-5,35,8),(-35,72,2),38),
    "14_plan_orthographic": add_camera("C14_Plan_Orthographic",(0,205,520),(0,205,0),50,460),
    "15_golden_hour_aerial": add_camera("C15_Golden_Hour_Aerial",(165,-85,150),(10,190,5),54),
    "16_clubhouse_night": add_camera("C16_Clubhouse_Night",(-145,82,12),(-82,127,3),38),
}


def set_daylight(mode="day"):
    if mode=="day":
        sun.data.energy=3.0;sun.rotation_euler=(math.radians(28),math.radians(-18),math.radians(125));bg.inputs["Strength"].default_value=0.45;fill.data.energy=950
        COL["fireflies"].hide_render=True
    elif mode=="golden":
        sun.data.energy=2.2;sun.rotation_euler=(math.radians(66),math.radians(-8),math.radians(112));bg.inputs["Strength"].default_value=0.25;fill.data.energy=500
        COL["fireflies"].hide_render=True
    else:
        sun.data.energy=0.02;bg.inputs["Strength"].default_value=0.018;fill.data.energy=25
        COL["fireflies"].hide_render=False


def render_view(name, cam, mode="day"):
    scene.camera=cam
    set_daylight(mode)
    scene.render.filepath=str(RENDERS/(name+".png"))
    bpy.ops.render.render(write_still=True)

# Save model before rendering.
scene["SV_Project"]="Sanjeevani Vann"
scene["SV_Revision"]="R07"
scene["SV_Model_Status"]="LOD300-equivalent concept; not for construction"
scene["SV_Terrain_Status"]="Assumed; topographic survey required"
scene["SV_Design_Credit"]="Aeronova Consultants · Architect Gaurav Vatsa"

blend_path=OUT/"Sanjeevani_Vann_LOD300_R07.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

# GLB export with materials and custom properties.
try:
    bpy.ops.export_scene.gltf(filepath=str(OUT/"Sanjeevani_Vann_LOD300_R07.glb"),export_format="GLB",export_apply=True,export_yup=True,export_extras=True,export_cameras=True,export_lights=True)
except TypeError:
    bpy.ops.export_scene.gltf(filepath=str(OUT/"Sanjeevani_Vann_LOD300_R07.glb"),export_format="GLB",export_apply=True,export_extras=True)

for name,cam in CAMERAS.items():
    mode="golden" if name=="15_golden_hour_aerial" else "night" if name=="16_clubhouse_night" else "day"
    render_view(name,cam,mode)

# Restore day and save final state.
set_daylight("day")
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

# Model statistics.
triangles=0
mesh_objects=0
for obj in bpy.data.objects:
    if obj.type=="MESH":
        mesh_objects+=1
        depsgraph=bpy.context.evaluated_depsgraph_get()
        evaluated=obj.evaluated_get(depsgraph)
        mesh=evaluated.to_mesh()
        mesh.calc_loop_triangles();triangles+=len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
stats={
    "project":"Sanjeevani Vann",
    "revision":"R07",
    "status":"LOD300-equivalent concept model",
    "objects":len(bpy.data.objects),
    "mesh_objects":mesh_objects,
    "triangles":triangles,
    "villas":18,
    "render_count":len(CAMERAS),
    "coordinate_basis":"scaled concept trace, not cadastral",
    "terrain_basis":"assumed stepped grade, not surveyed",
    "design_credit":"Aeronova Consultants led by Architect Gaurav Vatsa",
}
(OUT/"model_statistics.json").write_text(json.dumps(stats,indent=2),encoding="utf-8")
print(json.dumps(stats,indent=2))
