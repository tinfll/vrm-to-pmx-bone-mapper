"""Probe: does `bpy.ops.pose.armature_apply` bake bound meshes in Blender 4.5?

Poses an upper-arm bone -0.3 rad around X, applies the pose as rest pose,
then reports the new rest tail and the mesh vertex positions (authored vs
evaluated).
"""
import bpy
from mathutils import Quaternion, Vector

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)
for a in list(bpy.data.armatures):
    bpy.data.armatures.remove(a)

arm_data = bpy.data.armatures.new("A")
arm_obj = bpy.data.objects.new("A", arm_data)
bpy.context.scene.collection.objects.link(arm_obj)
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode='EDIT')
eb = arm_data.edit_bones.new("J_Bip_L_UpperArm")
eb.head = (0.0, 0.0, 0.0)
eb.tail = (0.0, 1.0, 0.0)
bpy.ops.object.mode_set(mode='OBJECT')

mesh = bpy.data.meshes.new("M")
mesh.from_pydata([(0, 0, 0), (0, 0.5, 0), (0, 1, 0)], [], [(0, 1, 2)])
obj = bpy.data.objects.new("M", mesh)
bpy.context.scene.collection.objects.link(obj)
obj.vertex_groups.new(name="J_Bip_L_UpperArm")
obj.vertex_groups["J_Bip_L_UpperArm"].add([0, 1, 2], 1.0, 'REPLACE')
mod = obj.modifiers.new("Arm", 'ARMATURE')
mod.object = arm_obj
bpy.context.view_layer.update()

bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode='POSE')
pb = arm_obj.pose.bones["J_Bip_L_UpperArm"]
pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0), -0.3)
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()

bone = arm_obj.pose.bones["J_Bip_L_UpperArm"]
rest_tail = bone.bone.matrix_local @ Vector((0.0, 1.0, 0.0))
print("rest tail:", tuple(round(v, 4) for v in rest_tail))
print("mesh v2 (data):", tuple(round(v, 4) for v in obj.data.vertices[2].co))
dg = bpy.context.evaluated_depsgraph_get()
ev = obj.evaluated_get(dg)
print("mesh v2 (eval):", tuple(round(v, 4) for v in ev.data.vertices[2].co))
print("PROBE DONE")
