"""Probe relative shape key semantics in Blender 4.5:
does ShapeKeyPoint.co set/get work in absolute coordinates or raw offsets?
"""
import bpy

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)

mesh = bpy.data.meshes.new("M")
mesh.from_pydata([(1, 0, 0)], [], [])
obj = bpy.data.objects.new("O", mesh)
bpy.context.scene.collection.objects.link(obj)

obj.shape_key_add(name="Basis", from_mix=False)
obj.shape_key_add(name="TPose", from_mix=False)
tp_kb = obj.data.shape_keys.key_blocks["TPose"]

print("basis:", tuple(obj.data.vertices[0].co))
print("tp before set:", tuple(tp_kb.data[0].co))

# pretend basis was moved to A-pose (1,0,0) and we want TPose to hold (2,0,0)
tp_kb.data[0].co = (2, 0, 0)
print("tp after set:", tuple(tp_kb.data[0].co))

tp_kb.value = 1.0
dg = bpy.context.evaluated_depsgraph_get()
ev = obj.evaluated_get(dg)
print("eval at TPose=1:", tuple(ev.data.vertices[0].co))
print("PROBE DONE")
