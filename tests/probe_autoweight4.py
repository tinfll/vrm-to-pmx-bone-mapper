"""Debug 3: does bone selection (without pose mode) make weight_from_bones
create groups? Try object-mode select, pose-mode select, and both."""
import bpy

def clean():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for a in list(bpy.data.armatures):
        bpy.data.armatures.remove(a)

def setup():
    clean()
    arm_data = bpy.data.armatures.new("A")
    arm_obj = bpy.data.objects.new("A", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    for name, h in [("Bone1", (0.0, 0.0, 0.0)), ("Bone2", (0.0, 0.0, 1.0))]:
        eb = arm_data.edit_bones.new(name)
        eb.head = h
        eb.tail = (h[0], h[1], h[2] + 1.0)
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
    return arm_obj, mesh_obj

def run_weight(mesh_obj, label):
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    try:
        r = bpy.ops.paint.weight_from_bones(type='AUTOMATIC')
        print(label, "result:", r, "groups:", [g.name for g in mesh_obj.vertex_groups])
    except RuntimeError as e:
        print(label, "error:", e)

# A: select in object mode
arm_obj, mesh_obj = setup()
arm_obj.data.bones["Bone1"].select = True
print("A select flags:", [(b.name, b.select) for b in arm_obj.data.bones])
run_weight(mesh_obj, "A (object-mode select)")

# B: select inside pose mode
arm_obj, mesh_obj = setup()
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode='POSE')
arm_obj.data.bones["Bone1"].select = True
bpy.ops.object.mode_set(mode='OBJECT')
print("B select flags:", [(b.name, b.select) for b in arm_obj.data.bones])
run_weight(mesh_obj, "B (pose-mode select)")

print("PROBE DONE")
