"""Probe Object.matrix_world set/get behavior for flip_facing."""
import bpy
import math
from mathutils import Matrix

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)

mesh = bpy.data.meshes.new("Cube")
mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
obj = bpy.data.objects.new("Cube", mesh)
bpy.context.scene.collection.objects.link(obj)
obj.location = (2.0, 3.0, 4.0)
print("after location set:")
print("  location:", tuple(obj.location))
print("  matrix_world translation:", tuple(obj.matrix_world.translation))

obj.matrix_world = Matrix.Rotation(math.pi, 4, 'Z') @ obj.matrix_world
print("after flip:")
print("  location:", tuple(obj.location))
print("  matrix_world translation:", tuple(obj.matrix_world.translation))

obj2 = bpy.data.objects.new("Cube2", mesh)
bpy.context.scene.collection.objects.link(obj2)
obj2.location = (2.0, 3.0, 4.0)
bpy.context.view_layer.update()
print("after view_layer.update:")
print("  obj2 matrix_world translation:", tuple(obj2.matrix_world.translation))
print("PROBE DONE")
