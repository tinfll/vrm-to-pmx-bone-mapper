"""Headless test for vrm_to_pmx_mapper.

Run with:
    blender -b --factory-startup -P tests/test_headless.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bpy
import math
from mathutils import Matrix, Quaternion, Vector

import vrm_to_pmx_mapper as vpm


def group_weights(group, vert_count):
    """{vertex_index: weight}, 0.0 for vertices not in the group."""
    out = {}
    for i in range(vert_count):
        try:
            out[i] = group.weight(i)
        except RuntimeError:
            out[i] = 0.0
    return out


def clean_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for a in list(bpy.data.armatures):
        bpy.data.armatures.remove(a)
    for t in list(bpy.data.texts):
        bpy.data.texts.remove(t)


def make_pmx_armature(names):
    arm_data = bpy.data.armatures.new("PMX")
    arm_obj = bpy.data.objects.new("PMX", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    for i, name in enumerate(names):
        eb = arm_data.edit_bones.new(name)
        eb.head = Vector((0.0, 0.0, i * 0.1))
        eb.tail = eb.head + Vector((0.0, 0.0, 0.05))
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj


def main():
    clean_scene()

    pmx_names = [
        "センター", "腰", "上半身", "上半身2", "上半身3", "首", "頭",
        "肩.L", "腕.L", "ひじ.L", "手首.L",
        "親指０.L", "親指１.L", "親指２.L",
        "人指１.L", "人指２.L", "人指３.L",
        "中指１.L", "中指２.L", "中指３.L",
        "薬指１.L", "薬指２.L", "薬指３.L",
        "小指１.L", "小指２.L", "小指３.L",
        "足.L", "ひざ.L", "足首.L", "つま先.L",
        "肩.R", "腕.R", "ひじ.R", "手首.R",
        "足.R", "ひざ.R", "足首.R", "つま先.R",
        "目.L", "目.R", "胸.L", "胸先.L", "胸.R", "胸先.R",
        "装飾_11-01_Sec_L_CoatSkirtBack_01",
        "装飾_11-02_Sec_L_CoatSkirtBack_end_01",
        "髪_01-01",
    ]
    arm = make_pmx_armature(pmx_names)

    # --- VRM mesh with J_Bip_* vertex groups ---
    mesh = bpy.data.meshes.new("VRM")
    verts = [(0, 0, 0), (0, 0, 1), (1, 0, 0), (0, 1, 0)]
    mesh.from_pydata(verts, [], [(0, 1, 2), (0, 2, 3)])
    obj = bpy.data.objects.new("VRM", mesh)
    bpy.context.scene.collection.objects.link(obj)

    groups = [
        "J_Bip_C_Hips", "J_Bip_L_UpperArm", "J_Bip_L_Index1",
        "J_Bip_L_Thumb1", "J_Bip_L_UpperLeg", "J_Bip_R_Hand",
        "J_Sec_L_CoatSkirtBack_01", "J_Sec_Hair1_01",
        "J_Bip_C_Spine.001", "SomeUnknownGroup",
    ]
    for g in groups:
        obj.vertex_groups.new(name=g)
    obj.vertex_groups["J_Bip_C_Hips"].add([0, 1, 2, 3], 0.5, 'REPLACE')
    obj.vertex_groups["J_Bip_L_UpperLeg"].add([0], 1.0, 'REPLACE')

    names = [g.name for g in obj.vertex_groups]
    mapping, skipped = vpm.build_mapping(names, arm, include_secondary=True)

    assert mapping["J_Bip_C_Hips"] == "腰", mapping
    assert mapping["J_Bip_L_UpperArm"] == "腕.L", mapping
    assert mapping["J_Bip_L_Index1"] == "人指１.L", mapping
    assert mapping["J_Bip_L_Thumb1"] == "親指０.L", mapping
    assert mapping["J_Bip_L_UpperLeg"] == "足.L", mapping
    assert mapping["J_Bip_R_Hand"] == "手首.R", mapping
    assert mapping["J_Sec_L_CoatSkirtBack_01"] == "装飾_11-01_Sec_L_CoatSkirtBack_01", mapping
    assert mapping["J_Bip_C_Spine.001"] == "上半身", mapping  # dedup suffix fallback

    skipped_names = [s[0] for s in skipped]
    assert "J_Sec_Hair1_01" in skipped_names, skipped
    assert "SomeUnknownGroup" in skipped_names, skipped

    # --- apply ---
    renamed, merged = vpm.apply_mapping_to_object(obj, arm, mapping, parent=True)

    assert "腰" in obj.vertex_groups
    assert "J_Bip_C_Hips" not in obj.vertex_groups
    assert obj.vertex_groups["腰"].weight(0) > 0.0  # weights survived the rename
    assert obj.parent == arm
    arm_mods = [m for m in obj.modifiers if m.type == 'ARMATURE']
    assert len(arm_mods) == 1 and arm_mods[0].object == arm
    assert len(obj.vertex_groups) == len(groups) - len(merged)  # only merges shrink the list

    # --- duplicate path: object copy must carry the vertex groups ---
    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = obj.name + "_dup"
    bpy.context.scene.collection.objects.link(dup)
    assert [g.name for g in dup.vertex_groups] == [g.name for g in obj.vertex_groups]

    # --- rest pose alignment: T-pose -> A-pose ---
    vrm_arm_data = bpy.data.armatures.new("VRMarm")
    vrm_arm = bpy.data.objects.new("VRMarm", vrm_arm_data)
    bpy.context.scene.collection.objects.link(vrm_arm)
    bpy.context.view_layer.objects.active = vrm_arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = vrm_arm_data.edit_bones.new("J_Bip_L_UpperArm")
    eb.head = Vector((0.0, 0.0, 0.0))
    eb.tail = Vector((0.0, 1.0, 0.0))
    bpy.ops.object.mode_set(mode='OBJECT')

    mesh2 = bpy.data.meshes.new("VRM2")
    mesh2.from_pydata([(0, 0, 0), (0, 0.5, 0), (0, 1, 0)], [], [(0, 1, 2)])
    obj2 = bpy.data.objects.new("VRM2", mesh2)
    bpy.context.scene.collection.objects.link(obj2)
    obj2.vertex_groups.new(name="J_Bip_L_UpperArm")
    obj2.vertex_groups["J_Bip_L_UpperArm"].add([0, 1, 2], 1.0, 'REPLACE')
    mod2 = obj2.modifiers.new("Arm", 'ARMATURE')
    mod2.object = vrm_arm

    applied = vpm.align_mesh_to_pose(
        obj2, ["J_Bip_L_UpperArm"], -0.3, apply_as_rest=True)
    assert applied == ["J_Bip_L_UpperArm"], applied

    v2 = obj2.data.vertices[2].co
    assert abs(v2.x) < 1e-4 and abs(v2.y - 0.9553) < 1e-3 and \
        abs(v2.z + 0.2955) < 1e-3, tuple(v2)
    rest_tail = vrm_arm.pose.bones["J_Bip_L_UpperArm"].bone.matrix_local \
        @ Vector((0.0, 1.0, 0.0))
    assert abs(rest_tail.y - 0.9553) < 1e-3 and \
        abs(rest_tail.z + 0.2955) < 1e-3, tuple(rest_tail)
    q = vrm_arm.pose.bones["J_Bip_L_UpperArm"].rotation_quaternion
    assert abs(q.angle) < 1e-4, q

    sk = obj2.data.shape_keys
    assert sk is not None, "TPose shape key backup missing"
    tp = sk.key_blocks.get("TPose")
    assert tp is not None
    tp.value = 1.0
    dg = bpy.context.evaluated_depsgraph_get()
    ev2 = obj2.evaluated_get(dg)
    assert abs(ev2.data.vertices[2].co.y - 1.0) < 1e-3, \
        tuple(ev2.data.vertices[2].co)

    # --- bake current pose + reset (manual A-pose workflow) ---
    vrm_arm2_data = bpy.data.armatures.new("VRMarm2")
    vrm_arm2 = bpy.data.objects.new("VRMarm2", vrm_arm2_data)
    bpy.context.scene.collection.objects.link(vrm_arm2)
    bpy.context.view_layer.objects.active = vrm_arm2
    bpy.ops.object.mode_set(mode='EDIT')
    eb = vrm_arm2_data.edit_bones.new("J_Bip_L_UpperArm")
    eb.head = Vector((0.0, 0.0, 0.0))
    eb.tail = Vector((0.0, 1.0, 0.0))
    bpy.ops.object.mode_set(mode='POSE')
    vrm_arm2.pose.bones["J_Bip_L_UpperArm"].rotation_quaternion = \
        Quaternion((1.0, 0.0, 0.0), -0.3)
    bpy.ops.object.mode_set(mode='OBJECT')

    mesh3 = bpy.data.meshes.new("VRM3")
    mesh3.from_pydata([(0, 0, 0), (0, 0.5, 0), (0, 1, 0)], [], [(0, 1, 2)])
    obj3 = bpy.data.objects.new("VRM3", mesh3)
    bpy.context.scene.collection.objects.link(obj3)
    obj3.vertex_groups.new(name="J_Bip_L_UpperArm")
    obj3.vertex_groups["J_Bip_L_UpperArm"].add([0, 1, 2], 1.0, 'REPLACE')
    mod3 = obj3.modifiers.new("Arm", 'ARMATURE')
    mod3.object = vrm_arm2

    n = vpm.bake_pose_and_reset(obj3)
    assert n == 3, n
    v2b = obj3.data.vertices[2].co
    assert abs(v2b.y - 0.9553) < 1e-3 and abs(v2b.z + 0.2955) < 1e-3, \
        tuple(v2b)
    q = vrm_arm2.pose.bones["J_Bip_L_UpperArm"].rotation_quaternion
    assert abs(q.angle) < 1e-4, q

    # --- align fallback: mesh not bound to any armature ---
    vrm_arm3_data = bpy.data.armatures.new("VRMarm3")
    vrm_arm3 = bpy.data.objects.new("VRMarm3", vrm_arm3_data)
    bpy.context.scene.collection.objects.link(vrm_arm3)
    bpy.context.view_layer.objects.active = vrm_arm3
    bpy.ops.object.mode_set(mode='EDIT')
    eb = vrm_arm3_data.edit_bones.new("FallbackArmBone")
    eb.head = Vector((0.0, 0.0, 0.0))
    eb.tail = Vector((0.0, 1.0, 0.0))
    bpy.ops.object.mode_set(mode='OBJECT')

    mesh4 = bpy.data.meshes.new("VRM4")
    mesh4.from_pydata([(0, 0, 0), (0, 0.5, 0), (0, 1, 0)], [], [(0, 1, 2)])
    obj4 = bpy.data.objects.new("VRM4", mesh4)
    bpy.context.scene.collection.objects.link(obj4)
    obj4.vertex_groups.new(name="FallbackArmBone")
    obj4.vertex_groups["FallbackArmBone"].add([0, 1, 2], 1.0, 'REPLACE')
    # NOTE: no Armature modifier on obj4

    applied = vpm.align_mesh_to_pose(obj4, ["FallbackArmBone"], -0.3,
                                     apply_as_rest=True)
    assert applied == ["FallbackArmBone"], applied
    v4 = obj4.data.vertices[2].co
    assert abs(v4.y - 0.9553) < 1e-3 and abs(v4.z + 0.2955) < 1e-3, tuple(v4)

    # --- flip facing: bakes 180° about world Z into the mesh data ---
    cube = bpy.data.meshes.new("Cube")
    cube.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    cube_obj = bpy.data.objects.new("Cube", cube)
    bpy.context.scene.collection.objects.link(cube_obj)
    cube_obj.location = (2.0, 3.0, 4.0)
    bpy.context.view_layer.update()
    world_before = cube_obj.matrix_world.copy()
    vpm.flip_facing(cube_obj)
    bpy.context.view_layer.update()
    # object transform untouched
    delta = cube_obj.matrix_world.translation - world_before.translation
    assert delta.length < 1e-4, tuple(cube_obj.matrix_world.translation)
    # vertex world position rotated 180° around world Z
    v_world = cube_obj.matrix_world @ cube_obj.data.vertices[1].co
    expected = Matrix.Rotation(math.pi, 4, 'Z') @ \
        (world_before @ Vector((1.0, 0.0, 0.0)))
    assert (v_world - expected).length < 1e-4, tuple(v_world)

    # --- hair position matching ---
    src_arm_data = bpy.data.armatures.new("VRMhair")
    src_arm = bpy.data.objects.new("VRMhair", src_arm_data)
    bpy.context.scene.collection.objects.link(src_arm)
    bpy.context.view_layer.objects.active = src_arm
    bpy.ops.object.mode_set(mode='EDIT')
    for name, h in [("J_Sec_Hair1_01", (1.0, 1.0, 1.0)),
                    ("J_Sec_Hair2_01", (1.5, 1.0, 1.0)),
                    ("J_Sec_Hair3_01", (5.0, 5.0, 5.0))]:
        eb = src_arm_data.edit_bones.new(name)
        eb.head = Vector(h)
        eb.tail = Vector(h) + Vector((0.0, 0.0, 0.2))
    bpy.ops.object.mode_set(mode='OBJECT')

    pmx2_data = bpy.data.armatures.new("PMX2")
    pmx2 = bpy.data.objects.new("PMX2", pmx2_data)
    bpy.context.scene.collection.objects.link(pmx2)
    bpy.context.view_layer.objects.active = pmx2
    bpy.ops.object.mode_set(mode='EDIT')
    for name, h in [("髪_01-01", (1.0, 1.0, 1.0)),
                    ("髪_02-01", (1.5, 1.0, 1.0)),
                    ("髪_03-01", (1.0, 1.0, 1.0)),  # coincident decoy
                    ("腰", (0.0, 0.0, 0.0))]:
        eb = pmx2_data.edit_bones.new(name)
        eb.head = Vector(h)
        eb.tail = Vector(h) + Vector((0.0, 0.0, 0.2))
    bpy.ops.object.mode_set(mode='OBJECT')

    hair_map, hair_skipped = vpm.build_mapping(
        ["J_Sec_Hair1_01", "J_Sec_Hair2_01", "J_Sec_Hair3_01"], pmx2,
        source_armature=src_arm, match_hair_by_position=True,
        match_tolerance=0.05)
    # Hair1 has two coincident candidates -> ambiguous, skipped.
    # Hair2 has a unique nearest -> matched.  Hair3 too far -> skipped.
    assert hair_map.get("J_Sec_Hair2_01") == "髪_02-01", hair_map
    assert "J_Sec_Hair1_01" not in hair_map, hair_map
    assert "J_Sec_Hair3_01" not in hair_map, hair_map
    assert any(s[0] == "J_Sec_Hair1_01" for s in hair_skipped), hair_skipped

    # --- auto-weight only new bones (selection-scoped) ---
    aw_data = bpy.data.armatures.new("AW")
    aw_arm = bpy.data.objects.new("AW", aw_data)
    bpy.context.scene.collection.objects.link(aw_arm)
    bpy.context.view_layer.objects.active = aw_arm
    bpy.ops.object.mode_set(mode='EDIT')
    for name, h in [("Bone1", (0.0, 0.0, 0.0)), ("Bone2", (0.0, 0.0, 1.0))]:
        eb = aw_data.edit_bones.new(name)
        eb.head = Vector(h)
        eb.tail = Vector(h) + Vector((0.0, 0.0, 1.0))
    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.mesh.primitive_cube_add(size=1)
    aw_mesh_obj = bpy.context.view_layer.objects.active
    aw_mesh_obj.name = "AWmesh"
    aw_mesh_obj.location.z = 1.0
    aw_mesh_obj.scale.z = 2.0
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=2)
    bpy.ops.object.mode_set(mode='OBJECT')
    aw_mod = aw_mesh_obj.modifiers.new("Arm", 'ARMATURE')
    aw_mod.object = aw_arm

    done = vpm.auto_weight_bones(aw_mesh_obj, aw_arm, ["Bone1"])
    assert done == ["Bone1"], done
    assert "Bone1" in aw_mesh_obj.vertex_groups
    assert "Bone2" not in aw_mesh_obj.vertex_groups  # not selected -> untouched

    before = group_weights(aw_mesh_obj.vertex_groups["Bone1"],
                           len(aw_mesh_obj.data.vertices))

    # add a NEW bone and weight only it
    bpy.context.view_layer.objects.active = aw_arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = aw_data.edit_bones.new("Bone3")
    eb.head = Vector((0.0, 0.0, 2.0))
    eb.tail = Vector((0.0, 0.0, 3.0))
    bpy.ops.object.mode_set(mode='OBJECT')

    done = vpm.auto_weight_bones(aw_mesh_obj, aw_arm, ["Bone3"])
    assert done == ["Bone3"], done
    assert "Bone3" in aw_mesh_obj.vertex_groups
    after = group_weights(aw_mesh_obj.vertex_groups["Bone1"],
                          len(aw_mesh_obj.data.vertices))
    for i, w in before.items():
        assert abs(after[i] - w) < 1e-6, (i, w, after[i])

    # selection restored; missing-bone detection works
    assert all(b.select is False for b in aw_data.bones), \
        "bone selection must be restored"
    missing = vpm.missing_group_bones(aw_mesh_obj, aw_arm)
    assert missing == ["Bone2"], missing

    # --- report helpers ---
    lines = vpm.format_report(obj.name, arm.name, renamed, merged, skipped)
    vpm.write_text_block("vrm2pmx_report", "\n".join(lines))
    assert "vrm2pmx_report" in bpy.data.texts

    print("ALL TESTS PASSED")
    print("renamed:", renamed)
    print("skipped:", skipped)


if __name__ == "__main__":
    main()
