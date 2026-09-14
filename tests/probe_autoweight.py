"""Probe: auto-weight only NEW bones without touching existing groups.

Strategy: temporarily set use_deform=False on all bones except the new
ones, run bpy.ops.paint.weight_from_bones(type='AUTOMATIC'), restore.
Check that (a) the new bone gets a group, (b) existing group weights are
bit-identical afterwards, (c) deform flags are restored.
"""
import bpy
from mathutils import Vector

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)
for a in list(bpy.data.armatures):
    bpy.data.armatures.remove(a)

# --- armature: two-bone chain ---
arm_data = bpy.data.armatures.new("A")
arm_obj = bpy.data.objects.new("A", arm_data)
bpy.context.scene.collection.objects.link(arm_obj)
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode='EDIT')
b1 = arm_data.edit_bones.new("Bone1")
b1.head = (0.0, 0.0, 0.0)
b1.tail = (0.0, 0.0, 1.0)
b2 = arm_data.edit_bones.new("Bone2")
b2.head = (0.0, 0.0, 1.0)
b2.tail = (0.0, 0.0, 2.0)
b2.parent = b1
b2.use_connect = True
bpy.ops.object.mode_set(mode='OBJECT')

# --- mesh: subdivided cube spanning z 0..2 ---
bpy.ops.mesh.primitive_cube_add(size=1)
mesh_obj = bpy.context.view_layer.objects.active
mesh_obj.name = "Mesh"
mesh_obj.location.z = 1.0
mesh_obj.scale.z = 2.0
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=2)
bpy.ops.object.mode_set(mode='OBJECT')
mod = mesh_obj.modifiers.new("Arm", 'ARMATURE')
mod.object = arm_obj

# --- initial automatic weights for the two original bones ---
bpy.context.view_layer.objects.active = mesh_obj
bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
try:
    bpy.ops.paint.weight_from_bones(type='AUTOMATIC')
finally:
    bpy.ops.object.mode_set(mode='OBJECT')

print("groups after first auto-weight:", [g.name for g in mesh_obj.vertex_groups])

before = {}
for gname in ("Bone1", "Bone2"):
    g = mesh_obj.vertex_groups.get(gname)
    before[gname] = {i: g.weight(i) for i in range(len(mesh_obj.data.vertices))}
print("Bone1 nonzero weights before:", sum(1 for w in before["Bone1"].values() if w > 0))

# --- add a NEW bone ---
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode='EDIT')
b3 = arm_data.edit_bones.new("Bone3")
b3.head = (0.0, 0.0, 2.0)
b3.tail = (0.0, 0.0, 2.5)
bpy.ops.object.mode_set(mode='OBJECT')

# --- auto-weight ONLY Bone3 (deform off for the others) ---
saved = {}
for bone in arm_data.bones:
    if bone.name != "Bone3":
        saved[bone.name] = bone.use_deform
        bone.use_deform = False

bpy.context.view_layer.objects.active = mesh_obj
bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
try:
    bpy.ops.paint.weight_from_bones(type='AUTOMATIC')
finally:
    bpy.ops.object.mode_set(mode='OBJECT')

for name, flag in saved.items():
    arm_data.bones[name].use_deform = flag

print("groups after new-bone auto-weight:", [g.name for g in mesh_obj.vertex_groups])
g3 = mesh_obj.vertex_groups.get("Bone3")
print("Bone3 group exists:", g3 is not None)
if g3:
    nz = {i: g3.weight(i) for i in range(len(mesh_obj.data.vertices))}
    print("Bone3 nonzero weights:", sum(1 for w in nz.values() if w > 0))

# --- verify existing weights unchanged ---
ok = True
for gname in ("Bone1", "Bone2"):
    g = mesh_obj.vertex_groups.get(gname)
    for i, w in before[gname].items():
        if abs(g.weight(i) - w) > 1e-6:
            ok = False
            print("CHANGED:", gname, i, w, g.weight(i))
print("existing weights unchanged:", ok)
print("deform flags restored:", all(arm_data.bones[n].use_deform == f
                                    for n, f in saved.items()))
print("PROBE DONE")
