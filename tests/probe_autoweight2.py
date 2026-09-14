"""Debug: context requirements for bpy.ops.paint.weight_from_bones headless."""
import bpy

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
b1 = arm_data.edit_bones.new("Bone1")
b1.head = (0.0, 0.0, 0.0)
b1.tail = (0.0, 0.0, 1.0)
bpy.ops.object.mode_set(mode='OBJECT')

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

bpy.context.view_layer.objects.active = mesh_obj
print("mode before:", bpy.context.mode)
bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
print("mode after mode_set:", bpy.context.mode)
print("poll:", bpy.ops.paint.weight_from_bones.poll())
print("armature found:", mod.object.name if mod.object else None)

# variant 1: as-is (no vertex groups)
try:
    r = bpy.ops.paint.weight_from_bones(type='AUTOMATIC')
    print("op result 1:", r, "groups:", [g.name for g in mesh_obj.vertex_groups])
except RuntimeError as e:
    print("op error 1:", e)

# variant 2: after creating one empty vertex group
mesh_obj.vertex_groups.new(name="__dummy__")
try:
    r = bpy.ops.paint.weight_from_bones(type='AUTOMATIC')
    print("op result 2:", r, "groups:", [g.name for g in mesh_obj.vertex_groups])
except RuntimeError as e:
    print("op error 2:", e)

bpy.ops.object.mode_set(mode='OBJECT')
print("PROBE DONE")
