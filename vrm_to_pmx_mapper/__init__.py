"""VRM → PMX Bone Mapper (Blender add-on).

Retargets a mesh that is rigged to a VRM skeleton ("J_Bip_*" naming)
onto a PMX armature (MMD Japanese bone names) by:

  1. Renaming / merging the mesh's vertex groups from VRM bone names
     to the PMX bone names,
  2. Removing old Armature modifiers and adding one that targets the
     PMX armature,
  3. (optionally) parenting the mesh object to the PMX armature.

Mapping is name-based:
  * primary humanoid table:  J_Bip_*  ->  腰 / 上半身 / 腕.L / 足.L ...
  * optional secondary pass: J_Sec_*  ->  PMX "装飾_*" bones that embed
    the same suffix (e.g. J_Sec_L_CoatSkirtBack_01 ->
    装飾_11-01_Sec_L_CoatSkirtBack_01).  Hair (J_Sec_Hair*) is NOT
    mappable this way because PMX hair bones (髪_*) do not embed the
    VRM names, so those groups are skipped.

Caveats:
  * Rest poses must match (both T-pose or both A-pose) and the mesh
    must be aligned to the PMX armature, otherwise deformation is off.
  * PMX twist bones (腕捩 / 手捩) and IK bones receive no weights from a
    VRM mesh (VRM has no equivalents) — expect minor twisting loss on
    forearms.
  * The pelvis mapping ("J_Bip_C_Hips" -> "腰") can be switched to
    "下半身" via the OVERRIDES table below if your PMX model puts the
    pelvis skinning on the lower-body bone.
"""

import bpy
import math
from mathutils import Matrix, Quaternion

bl_info = {
    "name": "VRM to PMX Bone Mapper",
    "author": "Copilot",
    "version": (1, 4, 1),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > VRM→PMX",
    "description": (
        "Remap a VRM-rigged mesh's vertex groups onto a PMX armature "
        "(J_Bip_* -> Japanese PMX bone names)"
    ),
    "category": "Rigging",
}


# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------

# Manual overrides: {"VRM group name": "PMX bone name"}.
# Add or replace entries here if the defaults don't fit your model.
OVERRIDES = {
    # "J_Bip_C_Hips": "下半身",   # alternative pelvis target
}

# Center / face / bust mappings (no left-right side).
_CENTER_MAP = {
    "Root": "センター",
    "J_Bip_C_Hips": "腰",
    "J_Bip_C_Spine": "上半身",
    "J_Bip_C_Chest": "上半身2",
    "J_Bip_C_UpperChest": "上半身3",
    "J_Bip_C_Neck": "首",
    "J_Bip_C_Head": "頭",
    "J_Adj_L_FaceEye": "目.L",
    "J_Adj_R_FaceEye": "目.R",
    "J_Sec_L_Bust1": "胸.L",
    "J_Sec_L_Bust2": "胸先.L",
    "J_Sec_R_Bust1": "胸.R",
    "J_Sec_R_Bust2": "胸先.R",
    # VRM 1.x humanoid names (fallback for modern VRM exporters)
    "hips": "腰",
    "spine": "上半身",
    "chest": "上半身2",
    "upperChest": "上半身3",
    "neck": "首",
    "head": "頭",
}

# Side rows: (VRM part after "J_Bip_L|R_", PMX base name without side).
# PMX finger digits are full-width characters (０１２３).
_SIDE_ROWS = [
    ("Shoulder", "肩"),
    ("UpperArm", "腕"),
    ("LowerArm", "ひじ"),
    ("Hand", "手首"),
    ("Thumb1", "親指０"), ("Thumb2", "親指１"), ("Thumb3", "親指２"),
    ("Index1", "人指１"), ("Index2", "人指２"), ("Index3", "人指３"),
    ("Middle1", "中指１"), ("Middle2", "中指２"), ("Middle3", "中指３"),
    ("Ring1", "薬指１"), ("Ring2", "薬指２"), ("Ring3", "薬指３"),
    ("Little1", "小指１"), ("Little2", "小指２"), ("Little3", "小指３"),
    ("UpperLeg", "足"),
    ("LowerLeg", "ひざ"),
    ("Foot", "足首"),
    ("ToeBase", "つま先"),
]

# VRM 1.x humanoid side names: {"vrm name": ("pmx base", side)}
_VRM1_SIDE_MAP = {
    "leftShoulder": ("肩", "L"),
    "rightShoulder": ("肩", "R"),
    "leftUpperArm": ("腕", "L"),
    "rightUpperArm": ("腕", "R"),
    "leftLowerArm": ("ひじ", "L"),
    "rightLowerArm": ("ひじ", "R"),
    "leftHand": ("手首", "L"),
    "rightHand": ("手首", "R"),
    "leftUpperLeg": ("足", "L"),
    "rightUpperLeg": ("足", "R"),
    "leftLowerLeg": ("ひざ", "L"),
    "rightLowerLeg": ("ひざ", "R"),
    "leftFoot": ("足首", "L"),
    "rightFoot": ("足首", "R"),
    "leftToes": ("つま先", "L"),
    "rightToes": ("つま先", "R"),
}

_VRM1_FINGER_ROWS = [
    ("ThumbProximal", "親指０"), ("ThumbIntermediate", "親指１"),
    ("ThumbDistal", "親指２"),
    ("IndexProximal", "人指１"), ("IndexIntermediate", "人指２"),
    ("IndexDistal", "人指３"),
    ("MiddleProximal", "中指１"), ("MiddleIntermediate", "中指２"),
    ("MiddleDistal", "中指３"),
    ("RingProximal", "薬指１"), ("RingIntermediate", "薬指２"),
    ("RingDistal", "薬指３"),
    ("LittleProximal", "小指１"), ("LittleIntermediate", "小指２"),
    ("LittleDistal", "小指３"),
]


def _build_primary_map():
    m = dict(_CENTER_MAP)
    for side in ("L", "R"):
        for vrm_part, pmx_base in _SIDE_ROWS:
            m["J_Bip_%s_%s" % (side, vrm_part)] = "%s.%s" % (pmx_base, side)
    for vrm_name, (pmx_base, side) in _VRM1_SIDE_MAP.items():
        m[vrm_name] = "%s.%s" % (pmx_base, side)
    for vrm_part, pmx_base in _VRM1_FINGER_ROWS:
        m["left" + vrm_part] = "%s.L" % pmx_base
        m["right" + vrm_part] = "%s.R" % pmx_base
    m.update(OVERRIDES)
    return m


PRIMARY_MAP = _build_primary_map()


# ---------------------------------------------------------------------------
# Core logic (also usable from scripts / the Blender Python console)
# ---------------------------------------------------------------------------

def resolve_secondary(vrm_name, pmx_bone_names):
    """Map a "J_Sec_*" name onto a PMX bone whose name embeds the suffix.

    PMX decoration bones were generated with the original VRM name inside:
      "J_Sec_L_CoatSkirtBack_01" -> "装飾_11-01_Sec_L_CoatSkirtBack_01"
    Returns None if there is not exactly one candidate.
    """
    if not vrm_name.startswith("J_Sec_"):
        return None
    key = vrm_name[2:]  # drop "J_" -> "Sec_L_CoatSkirtBack_01"
    if not key:
        return None
    exact = [n for n in pmx_bone_names if n.endswith(key)]
    if len(exact) == 1:
        return exact[0]
    contains = [n for n in pmx_bone_names if key in n]
    if len(contains) == 1:
        return contains[0]
    return None


def _match_hair_by_position(group_name, target_arm, source_arm, tol):
    """Map a J_Sec_Hair* group to a 髪_* bone by head proximity.

    PMX hair bones (髪_01-01 .. 髪_22-04) are re-split chains of the VRM
    strands (J_Sec_Hair1..4_01..22), so there is no name-based rule — any
    mapping by suffix number is wrong.  The rigs come from the same source
    model, so bone heads coincide in world space (both armatures must be
    aligned and at the same scale).
    """
    if source_arm is None:
        return None
    bpy.context.view_layer.update()  # refresh lazily-computed matrix_world
    src_bone = source_arm.data.bones.get(group_name)
    if src_bone is None:
        return None
    p = source_arm.matrix_world @ src_bone.head_local
    candidates = []
    for tb in target_arm.data.bones:
        if not tb.name.startswith("髪_"):
            continue
        d = ((target_arm.matrix_world @ tb.head_local) - p).length
        candidates.append((d, tb.name))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    d1, name1 = candidates[0]
    if d1 > tol:
        return None
    if len(candidates) > 1 and candidates[1][0] - d1 < 1e-6:
        return None  # ambiguous: coincident heads (e.g. chain roots)
    return name1


def build_mapping(group_names, armature_obj, include_secondary=False,
                  source_armature=None, match_hair_by_position=False,
                  match_tolerance=0.05):
    """Return (mapping, skipped) for the given vertex group names.

    mapping: {"vrmsourcegroupname": "pmxbonename"}
    skipped: [(group_name, reason)]

    match_hair_by_position: map J_Sec_Hair* groups onto 髪_* bones by
        bone head proximity (needs both armatures aligned in the scene).
    """
    pmx_bones = [b.name for b in armature_obj.data.bones]
    pmx_set = set(pmx_bones)
    mapping, skipped = {}, []

    for name in group_names:
        target = PRIMARY_MAP.get(name)
        if target is None and "." in name:
            # strip Blender's ".001" dedup suffix and retry
            target = PRIMARY_MAP.get(name.rsplit(".", 1)[0])
        if target is None and include_secondary:
            target = resolve_secondary(name, pmx_bones)
        if target is None and match_hair_by_position \
                and name.startswith("J_Sec_Hair"):
            target = _match_hair_by_position(
                name, armature_obj, source_armature, match_tolerance)
        if target is not None and target not in pmx_set:
            skipped.append((name, "target bone '%s' missing" % target))
            target = None
        if target is None:
            if name.startswith("J_Sec_Hair"):
                skipped.append(
                    (name, "hair unmatched (enable position matching)"))
            elif name.startswith("J_Sec_"):
                skipped.append((name, "no matching 装飾_* bone (enable J_Sec)"))
            else:
                skipped.append((name, "no mapping rule"))
            continue
        mapping[name] = target

    return mapping, skipped


def _merge_group(obj, src_group, dst_group):
    """Sum weights of src_group into dst_group."""
    for vert in obj.data.vertices:
        w = src_group.weight(vert.index)
        if w > 0.0:
            dst_group.add([vert.index], w, 'ADD')


def apply_mapping_to_object(obj, armature_obj, mapping, parent=True):
    """Rename/merge vertex groups of obj per mapping and attach obj to
    the PMX armature.  Returns (renamed, merged) lists of
    (old_name, new_name) pairs.  Modifies the object in place.
    """
    renamed, merged = [], []

    for group in list(obj.vertex_groups):
        src_name = group.name
        target = mapping.get(src_name)
        if target is None:
            continue
        dst = obj.vertex_groups.get(target)
        if dst is None:
            group.name = target
            renamed.append((src_name, target))
        else:
            _merge_group(obj, group, dst)
            obj.vertex_groups.remove(group)
            merged.append((src_name, target))

    # Replace every Armature modifier with a single PMX one.
    for mod in list(obj.modifiers):
        if mod.type == 'ARMATURE':
            obj.modifiers.remove(mod)
    mod = obj.modifiers.new("PMX", 'ARMATURE')
    mod.object = armature_obj

    if parent and obj.parent != armature_obj:
        bpy.context.view_layer.update()  # refresh lazily-computed matrix_world
        world = obj.matrix_world.copy()
        obj.parent = armature_obj
        # keep the object's current world transform
        obj.matrix_parent_inverse = (
            armature_obj.matrix_world.inverted_safe() @ world)

    return renamed, merged


def _bound_armature(obj):
    """Armature object currently deforming obj via an Armature modifier."""
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object and mod.object.type == 'ARMATURE':
            return mod.object
    return None


def _split_bone_list(text):
    return [s.strip() for s in text.split(",") if s.strip()]


_ARM_ALIASES = {
    "J_Bip_L_UpperArm": ("leftUpperArm",),
    "J_Bip_R_UpperArm": ("rightUpperArm",),
    "J_Bip_L_Shoulder": ("leftShoulder",),
    "J_Bip_R_Shoulder": ("rightShoulder",),
}


def missing_group_bones(mesh_obj, armature_obj):
    """Deform bones of the armature that have no vertex group on the mesh."""
    existing = set(g.name for g in mesh_obj.vertex_groups)
    return [b.name for b in armature_obj.data.bones
            if b.use_deform and b.name not in existing]


def auto_weight_bones(mesh_obj, armature_obj, bone_names):
    """Create vertex groups with Blender's automatic weights for the given
    bones ONLY — existing groups and weights stay untouched.

    paint.weight_from_bones in weight-paint mode only processes SELECTED
    pose bones (verified against Blender 4.5 source and behaviour), so we
    temporarily select only the target bones, run the operator, and restore
    the previous selection.  Returns the names of bones that got weights.
    """
    bone_names = [n for n in bone_names
                  if armature_obj.data.bones.get(n) is not None]
    if not bone_names or _bound_armature(mesh_obj) != armature_obj:
        return []

    ctx = bpy.context
    old_active = ctx.view_layer.objects.active
    arm_data = armature_obj.data
    target = set(bone_names)
    saved = {b.name: b.select for b in arm_data.bones}

    try:
        for bone in arm_data.bones:
            bone.select = bone.name in target

        ctx.view_layer.objects.active = mesh_obj
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        try:
            bpy.ops.paint.weight_from_bones(type='AUTOMATIC')
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
    finally:
        ctx.view_layer.objects.active = old_active
        for name, flag in saved.items():
            arm_data.bones[name].select = flag

    return [n for n in target if n in mesh_obj.vertex_groups]


def find_armature_with_bones(bone_names):
    """First object in the scene whose armature contains one of the bones."""
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' and obj.data is not None:
            if any(obj.data.bones.get(n) for n in bone_names):
                return obj
    return None


def bake_pose_into_mesh(obj, keep_shape_key=True, armature_obj=None):
    """Bake the current armature deformation of obj into its mesh vertices.

    Blender 4.5's "Apply Pose as Rest Pose" does NOT update bound meshes
    (verified empirically), so the deformed shape is captured from the
    evaluated mesh and written into the vertex positions here.  The
    original shape is kept as a relative 'TPose' shape key.

    armature_obj: the armature whose pose deforms the mesh.  Defaults to
    the mesh's bound armature; a temporary modifier is added if the mesh
    is not bound to it.
    """
    if armature_obj is None:
        armature_obj = _bound_armature(obj)
    if armature_obj is None:
        return None

    orig_co = [v.co.copy() for v in obj.data.vertices]

    # Evaluate a temp copy that only keeps Armature modifiers, so the
    # vertex count and order match the original mesh exactly.
    tmp = obj.copy()
    tmp.data = obj.data.copy()
    for coll in obj.users_collection:
        coll.objects.link(tmp)
    for mod in list(tmp.modifiers):
        if mod.type != 'ARMATURE':
            tmp.modifiers.remove(mod)
    if _bound_armature(tmp) != armature_obj:
        mod = tmp.modifiers.new("AlignTemp", 'ARMATURE')
        mod.object = armature_obj
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    # new_from_object returns undeformed geometry for the ORIGINAL object;
    # pass the evaluated object to get the final deformed geometry.
    ev = tmp.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev, depsgraph=dg)
    new_co = [v.co.copy() for v in baked.vertices]
    bpy.data.meshes.remove(baked)
    tmp_mesh = tmp.data
    bpy.data.objects.remove(tmp, do_unlink=True)
    if tmp_mesh.users == 0:
        bpy.data.meshes.remove(tmp_mesh)

    # Backup the pre-bake shape as a relative shape key.
    if keep_shape_key and obj.data.shape_keys is None:
        obj.shape_key_add(name="TPose", from_mix=False)

    for i, vert in enumerate(obj.data.vertices):
        vert.co = new_co[i]

    if keep_shape_key:
        key = obj.data.shape_keys.key_blocks.get("TPose")
        if key is not None:
            # ShapeKeyPoint.co is absolute for relative keys (verified 4.5).
            for i, kv in enumerate(key.data):
                kv.co = orig_co[i]

    return len(new_co)


def align_mesh_to_pose(obj, bone_names, angle, apply_as_rest=True):
    """Rotate the given pose bones by `angle` (radians) around their local X
    on obj's bound armature, bake the deformed shape into the mesh, then
    either apply the pose as the armature's new rest pose (recommended) or
    restore the original pose.

    Returns the list of rotated bone names, [] if none were found, or None
    if no armature could be found (mesh not bound and no armature in the
    scene contains the bones).
    """
    arm = _bound_armature(obj)
    if arm is None:
        arm = find_armature_with_bones(bone_names)
    if arm is None:
        print("VRM→PMX align: no armature found for bones %s"
              % ", ".join(bone_names))
        return None

    ctx = bpy.context
    old_active = ctx.view_layer.objects.active
    ctx.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')

    state, applied = {}, []
    rot = Quaternion((1.0, 0.0, 0.0), angle)
    for name in bone_names:
        pb = arm.pose.bones.get(name)
        if pb is None:
            for alias in _ARM_ALIASES.get(name, ()):
                pb = arm.pose.bones.get(alias)
                if pb is not None:
                    break
        if pb is None:
            continue
        state[name] = {
            'mode': pb.rotation_mode,
            'quat': pb.rotation_quaternion.copy(),
            'euler': pb.rotation_euler.copy(),
        }
        pb.rotation_quaternion = rot @ pb.rotation_quaternion
        applied.append(name)
        print("VRM→PMX align: rotated %s by %.4f rad around local X"
              % (name, angle))

    if not applied:
        print("VRM→PMX align: none of the bones %s were found on %s"
              % (", ".join(bone_names), arm.name))
        bpy.ops.object.mode_set(mode='OBJECT')
        ctx.view_layer.objects.active = old_active
        return []

    bpy.ops.object.mode_set(mode='OBJECT')
    n = bake_pose_into_mesh(obj, keep_shape_key=True, armature_obj=arm)
    print("VRM→PMX align: baked %s vertices" % n)

    if apply_as_rest:
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.armature_apply(selected=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    else:
        for name, st in state.items():
            pb = arm.pose.bones.get(name)
            if pb is None:
                continue
            pb.rotation_mode = st['mode']
            if st['mode'] == 'QUATERNION':
                pb.rotation_quaternion = st['quat']
            else:
                pb.rotation_euler = st['euler']

    ctx.view_layer.objects.active = old_active
    return applied


def flip_facing(obj):
    """Bake a 180° rotation around the world Z axis into the mesh data.

    VRM avatars face +Z in Blender while MMD/PMX models face the
    opposite direction.  The rotation is applied to the vertex
    coordinates only; the object transform stays unchanged, so no manual
    "Apply Rotation" (Ctrl+A) is needed afterwards.
    """
    # matrix_world is lazily computed; refresh it before reading.
    bpy.context.view_layer.update()
    world = obj.matrix_world
    # data' = world^-1 @ R @ world  (rotate in world space, keep object
    # transform untouched)
    transform = world.inverted_safe() @ Matrix.Rotation(math.pi, 4, 'Z') @ world
    obj.data.transform(transform)


def clear_pose(armature_obj):
    """Reset all pose bones of the armature to their rest transforms."""
    for pb in armature_obj.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
        if pb.rotation_mode == 'QUATERNION':
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        else:
            pb.rotation_euler = (0.0, 0.0, 0.0)


def bake_pose_and_reset(obj, keep_shape_key=True):
    """Bake the current armature deformation of obj into the mesh vertices
    and reset the armature pose to rest.

    This is the scripted equivalent of the manual workflow "pose the
    armature to A-pose, then apply the Armature modifier": the mesh keeps
    the baked shape while the armature returns to its default pose.
    """
    n = bake_pose_into_mesh(obj, keep_shape_key=keep_shape_key)
    if n is None:
        return None
    arm = _bound_armature(obj)
    if arm is not None:
        clear_pose(arm)
    return n


def format_report(obj_name, arm_name, renamed, merged, skipped):
    lines = []
    lines.append("=== VRM→PMX mapping report ===")
    lines.append("mesh: %s    armature: %s" % (obj_name, arm_name))
    lines.append("renamed: %d   merged: %d   skipped: %d"
                 % (len(renamed), len(merged), len(skipped)))
    lines.append("")
    if renamed:
        lines.append("-- renamed --")
        for a, b in renamed:
            lines.append("  %s  ->  %s" % (a, b))
    if merged:
        lines.append("-- merged --")
        for a, b in merged:
            lines.append("  %s  ->  %s" % (a, b))
    if skipped:
        lines.append("-- skipped --")
        for name, why in skipped:
            lines.append("  %s   (%s)" % (name, why))
    return lines


def write_text_block(name, text):
    if name in bpy.data.texts:
        t = bpy.data.texts[name]
        t.clear()
    else:
        t = bpy.data.texts.new(name)
    t.write(text)


# ---------------------------------------------------------------------------
# Add-on UI
# ---------------------------------------------------------------------------

class VRM2PMX_Properties(bpy.types.PropertyGroup):
    source: bpy.props.PointerProperty(
        name="VRM Mesh",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
        description="Mesh rigged to the VRM skeleton (J_Bip_* vertex groups)")
    target_armature: bpy.props.PointerProperty(
        name="PMX Armature",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
        description="Armature with PMX Japanese bone names")
    duplicate_mesh: bpy.props.BoolProperty(
        name="Duplicate Mesh",
        default=True,
        description="Work on a copy (\"<name>_PMX\"); the original stays untouched")
    parent_mesh: bpy.props.BoolProperty(
        name="Parent to Armature",
        default=True,
        description="Parent the mesh object to the PMX armature (keeps world transform)")
    include_secondary: bpy.props.BoolProperty(
        name="Include J_Sec (skirt/sleeve) bones",
        default=False,
        description="Also map J_Sec_* groups onto PMX 装飾_* bones by name suffix")
    align_rest_first: bpy.props.BoolProperty(
        name="Align Rest Pose First (T→A)",
        default=False,
        description=("Before mapping: rotate the source rig's arm bones by "
                     "'Arm Angle' around their local X, bake the deformed "
                     "shape into the mesh and apply the pose as the "
                     "armature's rest pose"))
    pose_angle: bpy.props.FloatProperty(
        name="Arm Angle (radians)",
        default=-0.3,
        unit='ROTATION',
        description=("Rotation in RADIANS around each arm bone's local X "
                     "(-0.3 rad ≈ -17° ≈ VRM T-pose → PMX A-pose)"))
    pose_bones: bpy.props.StringProperty(
        name="Arm Bones",
        default="J_Bip_L_UpperArm,J_Bip_R_UpperArm",
        description="Comma-separated arm bones rotated around their local X")
    flip_facing: bpy.props.BoolProperty(
        name="Flip Mesh Facing (180° around Z)",
        default=False,
        description=("Only if the mapped mesh faces backward: bakes a 180° "
                     "rotation around Z into the mesh data (object transform "
                     "stays untouched)"))
    match_hair: bpy.props.BoolProperty(
        name="Match Hair by Position",
        default=True,
        description=("Map J_Sec_Hair* groups onto 髪_* bones by bone head "
                     "proximity (PMX hair chains have no name-based rule)"))
    match_tolerance: bpy.props.FloatProperty(
        name="Match Tolerance",
        default=0.05,
        min=0.0,
        subtype='DISTANCE',
        description="Max distance (m) between source and target bone heads "
                    "for position matching")
    weight_bones: bpy.props.StringProperty(
        name="Bones",
        default="",
        description=("Comma-separated bones to auto-weight; empty = every "
                     "deform bone missing a vertex group on the mesh"))


def _get_props(context):
    return context.scene.vrm2pmx


class VRM2PMX_OT_apply(bpy.types.Operator):
    bl_idname = "rig.vrm_to_pmx_apply"
    bl_label = "Apply VRM→PMX Mapping"
    bl_description = ("Remap the VRM mesh's vertex groups to PMX bone names "
                     "and attach the mesh to the PMX armature")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        p = _get_props(context)
        return bool(p.source and p.target_armature
                    and p.source.type == 'MESH'
                    and p.target_armature.type == 'ARMATURE')

    def execute(self, context):
        p = _get_props(context)
        src, arm = p.source, p.target_armature

        if p.align_rest_first:
            applied = align_mesh_to_pose(
                src, _split_bone_list(p.pose_bones), p.pose_angle,
                apply_as_rest=True)
            if applied:
                self.report(
                    {'INFO'}, "Aligned rest pose: %s" % ", ".join(applied))
            else:
                self.report(
                    {'WARNING'},
                    "Rest pose alignment skipped (no bound armature or "
                    "none of the arm bones found)")

        if p.duplicate_mesh:
            # Blender >= 4.1 owns vertex groups on the Object, not the Mesh,
            # so copy the object (carries groups) and give it its own mesh.
            obj = src.copy()
            obj.data = src.data.copy()
            obj.name = src.name + "_PMX"
            for coll in src.users_collection:
                coll.objects.link(obj)
            context.view_layer.objects.active = obj
        else:
            obj = src

        if p.flip_facing:
            flip_facing(obj)

        mapping, skipped = build_mapping(
            [g.name for g in obj.vertex_groups], arm, p.include_secondary,
            source_armature=_bound_armature(obj),
            match_hair_by_position=p.match_hair,
            match_tolerance=p.match_tolerance)
        renamed, merged = apply_mapping_to_object(
            obj, arm, mapping, parent=p.parent_mesh)

        text = "\n".join(format_report(obj.name, arm.name, renamed, merged, skipped))
        print(text)
        write_text_block("vrm2pmx_report", text)

        self.report(
            {'INFO'},
            "Mapped %d groups (%d renamed, %d merged), %d skipped — see console / vrm2pmx_report"
            % (len(renamed) + len(merged), len(renamed), len(merged), len(skipped)))
        return {'FINISHED'}


class VRM2PMX_OT_report(bpy.types.Operator):
    bl_idname = "rig.vrm_to_pmx_report"
    bl_label = "Preview Mapping"
    bl_description = ("Print the proposed mapping and the skipped groups "
                     "without modifying anything")
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        p = _get_props(context)
        return bool(p.source and p.target_armature
                    and p.source.type == 'MESH'
                    and p.target_armature.type == 'ARMATURE')

    def execute(self, context):
        p = _get_props(context)
        src, arm = p.source, p.target_armature

        mapping, skipped = build_mapping(
            [g.name for g in src.vertex_groups], arm, p.include_secondary,
            source_armature=_bound_armature(src),
            match_hair_by_position=p.match_hair,
            match_tolerance=p.match_tolerance)

        lines = [
            "=== VRM→PMX preview ===",
            "mesh: %s    armature: %s" % (src.name, arm.name),
            "groups: %d   mapped: %d   skipped: %d"
            % (len(src.vertex_groups), len(mapping), len(skipped)),
            "",
        ]
        for name, target in sorted(mapping.items()):
            lines.append("  %s  ->  %s" % (name, target))
        if skipped:
            lines.append("")
            lines.append("-- skipped --")
            for name, why in skipped:
                lines.append("  %s   (%s)" % (name, why))

        text = "\n".join(lines)
        print(text)
        write_text_block("vrm2pmx_preview", text)

        self.report(
            {'INFO'},
            "Mapped %d / %d groups — see console / vrm2pmx_preview"
            % (len(mapping), len(src.vertex_groups)))
        return {'FINISHED'}


class VRM2PMX_OT_align_pose(bpy.types.Operator):
    bl_idname = "rig.vrm_to_pmx_align_pose"
    bl_label = "Align Source Rig to A-pose"
    bl_description = ("Rotate the arm bones by 'Arm Angle' around their local "
                     "X, bake the deformed shape into the source mesh and "
                     "apply the pose as the armature's rest pose")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        p = _get_props(context)
        return bool(p.source and p.source.type == 'MESH')

    def execute(self, context):
        p = _get_props(context)
        applied = align_mesh_to_pose(
            p.source, _split_bone_list(p.pose_bones), p.pose_angle,
            apply_as_rest=True)
        if applied is None:
            self.report(
                {'WARNING'},
                "No armature found — the mesh is not bound to one and no "
                "armature in the scene contains the listed bones (see "
                "console)")
            return {'CANCELLED'}
        if not applied:
            self.report(
                {'WARNING'}, "None of the bones '%s' found" % p.pose_bones)
            return {'CANCELLED'}
        self.report(
            {'INFO'},
            "Aligned %d bones to A-pose and baked the mesh: %s"
            % (len(applied), ", ".join(applied)))
        return {'FINISHED'}


class VRM2PMX_OT_autoweight(bpy.types.Operator):
    bl_idname = "rig.vrm_to_pmx_autoweight"
    bl_label = "Auto-Weight New Bones"
    bl_description = ("Create vertex groups with Blender's automatic weights "
                     "for the listed bones (or every deform bone missing a "
                     "group), without touching existing groups")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        p = _get_props(context)
        return bool(p.source and p.source.type == 'MESH'
                    and p.target_armature
                    and p.target_armature.type == 'ARMATURE')

    def execute(self, context):
        p = _get_props(context)
        src, arm = p.source, p.target_armature
        if _bound_armature(src) != arm:
            self.report(
                {'WARNING'}, "Mesh is not deformed by the selected armature")
            return {'CANCELLED'}

        names = _split_bone_list(p.weight_bones)
        if not names:
            names = missing_group_bones(src, arm)
        if not names:
            self.report({'INFO'}, "No deform bones missing a vertex group")
            return {'CANCELLED'}

        done = auto_weight_bones(src, arm, names)
        self.report(
            {'INFO'},
            "Auto-weighted %d bones: %s" % (len(done), ", ".join(done)))
        return {'FINISHED'}


class VRM2PMX_OT_bake_pose(bpy.types.Operator):
    bl_idname = "rig.vrm_to_pmx_bake_pose"
    bl_label = "Bake Current Pose"
    bl_description = ("Bake the current deformation of the source mesh's "
                     "armature into the vertex positions and reset the pose "
                     "(scripted 'apply Armature modifier'); TPose shape key "
                     "kept as backup")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        p = _get_props(context)
        return bool(p.source and p.source.type == 'MESH')

    def execute(self, context):
        p = _get_props(context)
        n = bake_pose_and_reset(p.source, keep_shape_key=True)
        if n is None:
            self.report({'WARNING'}, "Source mesh is not bound to an armature")
            return {'CANCELLED'}
        self.report(
            {'INFO'}, "Baked %d vertices, pose reset to rest" % n)
        return {'FINISHED'}


class VRM2PMX_PT_panel(bpy.types.Panel):
    bl_label = "VRM → PMX Mapper"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VRM→PMX"

    def draw(self, context):
        p = _get_props(context)
        layout = self.layout

        layout.prop(p, "source")
        layout.prop(p, "target_armature")
        layout.prop(p, "duplicate_mesh")
        layout.prop(p, "parent_mesh")
        layout.prop(p, "include_secondary")
        layout.prop(p, "flip_facing")
        layout.prop(p, "match_hair")
        if p.match_hair:
            layout.prop(p, "match_tolerance")

        box = layout.box()
        box.label(text="Auto-Weight New Bones", icon='MOD_VERTEX_WEIGHT')
        box.prop(p, "weight_bones")
        box.operator(VRM2PMX_OT_autoweight.bl_idname, icon='MOD_VERTEX_WEIGHT')

        box = layout.box()
        box.label(text="Rest Pose Alignment (T → A)", icon='POSE_HLT')
        box.prop(p, "pose_angle")
        box.prop(p, "pose_bones")
        row = box.row(align=True)
        row.operator(VRM2PMX_OT_align_pose.bl_idname, icon='POSE_HLT')
        row.operator(VRM2PMX_OT_bake_pose.bl_idname, icon='MOD_ARMATURE')
        box.label(text="Or pose the armature by hand, then", icon='INFO')
        box.label(text="press 'Bake Current Pose'.")
        layout.prop(p, "align_rest_first")

        layout.separator()
        row = layout.row(align=True)
        row.operator(VRM2PMX_OT_report.bl_idname, icon='CONSOLE')
        layout.operator(VRM2PMX_OT_apply.bl_idname, icon='ARMATURE_DATA')

        box = layout.box()
        box.label(text="Align the mesh to the armature's", icon='INFO')
        box.label(text="position/scale before applying.")
        box.label(text="Report goes to the console and the")
        box.label(text="text blocks 'vrm2pmx_preview' / 'vrm2pmx_report'.")


CLASSES = (
    VRM2PMX_Properties,
    VRM2PMX_OT_apply,
    VRM2PMX_OT_report,
    VRM2PMX_OT_align_pose,
    VRM2PMX_OT_bake_pose,
    VRM2PMX_OT_autoweight,
    VRM2PMX_PT_panel,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.vrm2pmx = bpy.props.PointerProperty(type=VRM2PMX_Properties)


def unregister():
    del bpy.types.Scene.vrm2pmx
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
