"""Quick mapping script for the Blender Text Editor / Python console.

No add-on registration required.  Select the VRM mesh object(s), make
sure the PMX armature exists, set TARGET_NAME below, then run this
script inside Blender.

The selected mesh objects are remapped IN PLACE (vertex groups renamed,
Armature modifiers replaced, parented to the PMX armature).  Set
DUPLICATE_FIRST = True if you want to keep the originals.
"""

import os
import sys

try:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:  # running from the Python console (no __file__)
    BASE = r"c:\Users\tinf\Pictures\Eths\utils\bonemapping\bone"

if BASE not in sys.path:
    sys.path.insert(0, BASE)

import bpy
from vrm_to_pmx_mapper import (
    _bound_armature as bound_armature,
    align_mesh_to_pose, apply_mapping_to_object, auto_weight_bones,
    build_mapping, flip_facing, format_report, missing_group_bones)

TARGET_NAME = ""          # <-- PMX armature object name, e.g. "Cyan4_arm"
INCLUDE_SECONDARY = False  # map J_Sec_* skirt/sleeve bones onto 装飾_* bones
DUPLICATE_FIRST = True    # duplicate each mesh before modifying it
ALIGN_REST_POSE = False   # True: convert T-pose -> A-pose before mapping
ALIGN_BONES = ["J_Bip_L_UpperArm", "J_Bip_R_UpperArm"]
ALIGN_ANGLE = -0.3        # radians around local X (negative = arm down)
FLIP_FACING = False       # only if the mapped mesh faces backward (bakes 180° Z)
MATCH_HAIR = True         # map J_Sec_Hair* onto 髪_* by bone head proximity
MATCH_TOLERANCE = 0.05    # max distance (m) for position matching
AUTO_WEIGHT = False       # auto-weight new bones after mapping
AUTO_WEIGHT_BONES = []    # empty = all deform bones missing a group


def main():
    if not TARGET_NAME:
        print("Set TARGET_NAME to your PMX armature object name.")
        return
    arm = bpy.data.objects.get(TARGET_NAME)
    if arm is None or arm.type != 'ARMATURE':
        print("Armature object '%s' not found." % TARGET_NAME)
        return

    for src in [o for o in bpy.context.selected_objects if o.type == 'MESH']:
        if ALIGN_REST_POSE:
            applied = align_mesh_to_pose(
                src, ALIGN_BONES, ALIGN_ANGLE, apply_as_rest=True)
            if applied:
                print("Aligned rest pose:", ", ".join(applied))
            else:
                print("Rest pose alignment skipped for", src.name)

        if DUPLICATE_FIRST:
            # Blender >= 4.1: vertex groups live on the Object.
            obj = src.copy()
            obj.data = src.data.copy()
            obj.name = src.name + "_PMX"
            for coll in src.users_collection:
                coll.objects.link(obj)
        else:
            obj = src

        if FLIP_FACING:
            flip_facing(obj)

        mapping, skipped = build_mapping(
            [g.name for g in obj.vertex_groups], arm, INCLUDE_SECONDARY,
            source_armature=bound_armature(obj),
            match_hair_by_position=MATCH_HAIR,
            match_tolerance=MATCH_TOLERANCE)
        renamed, merged = apply_mapping_to_object(obj, arm, mapping)

        if AUTO_WEIGHT:
            names = AUTO_WEIGHT_BONES or missing_group_bones(obj, arm)
            if names:
                done = auto_weight_bones(obj, arm, names)
                print("Auto-weighted:", ", ".join(done))

        for line in format_report(obj.name, arm.name, renamed, merged, skipped):
            print(line)
        print()

    print("Done. Check the report above for skipped groups.")


if __name__ == "__main__" or __name__ == "__builtin__":
    main()
