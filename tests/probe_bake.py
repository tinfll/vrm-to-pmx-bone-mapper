"""Debug probe: where does the deformation get lost in bake_pose_into_mesh?"""
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

bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode='POSE')
pb = arm_obj.pose.bones["J_Bip_L_UpperArm"]
pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0), -0.3)
print("pose set:", tuple(round(v, 4) for v in pb.rotation_quaternion))
bpy.ops.object.mode_set(mode='OBJECT')
print("pose after mode switch:", tuple(round(v, 4) for v in arm_obj.pose.bones["J_Bip_L_UpperArm"].rotation_quaternion))

# direct eval of the original object
dg1 = bpy.context.evaluated_depsgraph_get()
ev1 = obj.evaluated_get(dg1)
print("orig eval v2:", tuple(round(v, 4) for v in ev1.data.vertices[2].co))

# temp copy
tmp = obj.copy()
tmp.data = obj.data.copy()
bpy.context.scene.collection.objects.link(tmp)
for mod in list(tmp.modifiers):
    if mod.type != 'ARMATURE':
        tmp.modifiers.remove(mod)

bpy.context.view_layer.update()
dg2 = bpy.context.evaluated_depsgraph_get()
print("tmp in dg:", any(o.name == tmp.name for o in dg2.objects))
ev2 = tmp.evaluated_get(dg2)
print("tmp eval v2:", tuple(round(v, 4) for v in ev2.data.vertices[2].co))
baked = bpy.data.meshes.new_from_object(tmp, depsgraph=dg2)
print("baked v2:", tuple(round(v, 4) for v in baked.vertices[2].co))
print("PROBE DONE")
