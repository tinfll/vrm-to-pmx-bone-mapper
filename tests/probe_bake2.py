"""Probe: correct way to capture evaluated mesh geometry in Blender 4.5."""
import bpy
from mathutils import Quaternion

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
bpy.ops.object.mode_set(mode='POSE')
arm_obj.pose.bones["J_Bip_L_UpperArm"].rotation_quaternion = \
    Quaternion((1.0, 0.0, 0.0), -0.3)
bpy.ops.object.mode_set(mode='OBJECT')

mesh = bpy.data.meshes.new("M")
mesh.from_pydata([(0, 0, 0), (0, 0.5, 0), (0, 1, 0)], [], [(0, 1, 2)])
obj = bpy.data.objects.new("M", mesh)
bpy.context.scene.collection.objects.link(obj)
obj.vertex_groups.new(name="J_Bip_L_UpperArm")
obj.vertex_groups["J_Bip_L_UpperArm"].add([0, 1, 2], 1.0, 'REPLACE')
mod = obj.modifiers.new("Arm", 'ARMATURE')
mod.object = arm_obj

tmp = obj.copy()
tmp.data = obj.data.copy()
bpy.context.scene.collection.objects.link(tmp)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()

print("doc:", str(bpy.data.meshes.new_from_object.__doc__).replace("\n", " ")[:220])
ev = tmp.evaluated_get(dg)
print("has to_mesh:", hasattr(ev, "to_mesh"))

try:
    m1 = bpy.data.meshes.new_from_object(tmp, depsgraph=dg)
    print("new_from_object(tmp, dg):", tuple(round(v, 4) for v in m1.vertices[2].co))
    bpy.data.meshes.remove(m1)
except Exception as e:
    print("variant1 failed:", e)

try:
    m2 = bpy.data.meshes.new_from_object(tmp)
    print("new_from_object(tmp):", tuple(round(v, 4) for v in m2.vertices[2].co))
    bpy.data.meshes.remove(m2)
except Exception as e:
    print("variant2 failed:", e)

try:
    m3 = bpy.data.meshes.new_from_object(ev, depsgraph=dg)
    print("new_from_object(ev, dg):", tuple(round(v, 4) for v in m3.vertices[2].co))
    bpy.data.meshes.remove(m3)
except Exception as e:
    print("variant3 failed:", e)

try:
    m4 = bpy.data.meshes.new_from_object(tmp, preserve_all_data_layers=True, depsgraph=dg)
    print("new_from_object(tmp, preserve_all, dg):",
          tuple(round(v, 4) for v in m4.vertices[2].co))
    bpy.data.meshes.remove(m4)
except Exception as e:
    print("variant4 failed:", e)

try:
    m5 = ev.to_mesh()
    print("ev.to_mesh():", tuple(round(v, 4) for v in m5.vertices[2].co))
    bpy.data.meshes.remove(m5)
except Exception as e:
    print("variant5 failed:", e)

print("PROBE DONE")
