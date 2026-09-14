"""Debug 2: how to make weight_from_bones see the armature pose headless."""
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
    mesh_obj.vertex_groups.new(name="__dummy__")
    return arm_obj, mesh_obj

def run_weight(mesh_obj, label):
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    try:
        bpy.ops.paint.weight_from_bones(type='AUTOMATIC')
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    print(label, "groups:", [g.name for g in mesh_obj.vertex_groups])

# A: depsgraph update before
arm_obj, mesh_obj = setup()
bpy.context.view_layer.update()
run_weight(mesh_obj, "A (view_layer.update)")

# B: pose-mode toggle before
arm_obj, mesh_obj = setup()
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode='POSE')
print("B pose bones:", [p.name for p in arm_obj.pose.bones])
bpy.ops.object.mode_set(mode='OBJECT')
print("B pose bones after exit:", [p.name for p in arm_obj.pose.bones])
run_weight(mesh_obj, "B (pose toggle)")

# C: touch pose.bones property (triggers pose build?)
arm_obj, mesh_obj = setup()
print("C pose bones raw:", [p.name for p in arm_obj.pose.bones])
run_weight(mesh_obj, "C (touch pose.bones)")

print("PROBE DONE")
