# VRM → PMX Bone Mapper (Blender 4.5 add-on)

> Looking for the polished overview with demo GIFs?
> See the root **[README.md](../README.md)**.

Retargets a mesh rigged to a VRM skeleton (`J_Bip_*` naming) onto a PMX
armature (MMD Japanese bone names). The mesh's vertex groups are
renamed/merged to the PMX bone names and the mesh is attached to the PMX
armature via an Armature modifier. Secondary (J_Sec) hair bones are
ignored, as requested.

## Files

- `vrm_to_pmx_mapper/__init__.py` — the add-on (installable).
- `quick_map.py` — runnable inside Blender without installing the add-on.
- `tests/test_headless.py` — headless self-test:
  `blender -b --factory-startup -P tests/test_headless.py`

## Install

Edit → Preferences → Add-ons → Install… and select
`vrm_to_pmx_mapper/__init__.py` (or zip the folder). Enable
**VRM to PMX Bone Mapper**. A panel **VRM→PMX** appears in the 3D
Viewport sidebar.

## Usage

1. Import both models (VRM mesh + skeleton, PMX mesh + skeleton).
2. Align the VRM mesh to the PMX armature (same position/scale).
3. Sidebar → **VRM→PMX**: pick **VRM Mesh** and **PMX Armature**.
4. Fix the rest-pose mismatch (see below): either press **Align Source
   Rig to A-pose**, or enable **Align Rest Pose First** so the apply
   operator does it automatically. **Flip Mesh Facing** is off by
   default — enable it only if the mapped mesh ends up facing backward.
5. Click **Preview Mapping** to check the report (console + text block
   `vrm2pmx_preview`), then **Apply VRM→PMX Mapping**.

**Duplicate Mesh** is on by default, so the original is kept and a
`<name>_PMX` object is produced.

## Rest pose alignment (T-pose → A-pose)

VRM models rest in T-pose, PMX models in A-pose. The panel's **Rest
Pose Alignment** box converts the source mesh: it rotates the arm bones
(`J_Bip_L_UpperArm`, `J_Bip_R_UpperArm` by default) by **Arm Angle**
(−0.3 rad ≈ T→A) around their local X, bakes the deformed shape into
the mesh, and applies the pose as the armature's new rest pose. The
**Arm Angle** field is in **radians** (typing `0.3` means 0.3 rad ≈
17°). Every rotated bone and the baked vertex count are printed to the
console.

Blender 4.5's *Apply Pose as Rest Pose* does **not** update bound
meshes (verified empirically): normalizing the skeleton in Pose Mode
alone leaves the mesh authored in T-pose, so it snaps back and
detaches from the new A-pose bones. The add-on therefore bakes the
deformed shape into the vertices **before** normalizing the skeleton
(pose → bake → apply as rest pose). The original T-pose is kept as a
relative shape key **TPose**. For the reverse direction (PMX →
T-pose), set **Arm Bones** to `腕.L,腕.R` and **Arm Angle** to `+0.3`.

Alternatively, do it by hand: pose the VRM armature to A-pose in Pose
Mode, then press **Bake Current Pose** — it bakes the deformation into
the mesh and resets the pose (the scripted equivalent of applying the
Armature modifier) — then apply the mapping as usual.

## Facing direction

VRM avatars face +Z in Blender; MMD/PMX models face the opposite
direction. If the mapped mesh ends up facing backward (nose out the
back) while the spine looks fine, enable **Flip Mesh Facing** — it
bakes a 180° rotation around the world Z axis into the mesh data, so
the object transform stays untouched and no manual Ctrl+A (Apply
Rotation) is needed.

## Hair (J_Sec_Hair*) — matched by position

There is no name-based rule for hair: PMX hair bones
(`髪_01-01 … 髪_22-04`) are re-split chains of the VRM strands
(`J_Sec_Hair1..4_01..22`), so any mapping by suffix number is wrong
(which is why strands 2/3/4 fail). With **Match Hair by Position** the
add-on maps each `J_Sec_Hair*` group to the `髪_*` bone whose head is
nearest to the VRM bone's head (both rigs come from the same source, so
positions coincide). Requirements: both armatures at the same
location/scale; tolerance is **Match Tolerance** (default 5 cm).
Ambiguous coincident candidates (e.g. chain roots) are skipped and
listed in the report.

## Auto-weighting newly added bones

If you add new bones to the PMX armature later, the mesh has no vertex
groups for them. **Auto-Weight New Bones** creates the groups with
Blender's built-in automatic weights for the listed bones — leave
**Bones** empty to auto-detect every deform bone that has no group on
the mesh. Existing groups and weights are untouched: in weight-paint
mode `paint.weight_from_bones` only processes *selected* pose bones
(verified against the 4.5 source), so the operator temporarily selects
just the target bones, runs, and restores the selection.

## Developing without reinstalling

You do **not** need to zip and reinstall on every change:

- Install the add-on **from a directory** once, then edit the files and
  use **F3 → "Reload Scripts"** (or `bpy.ops.script.reload()`) —
  Blender re-runs the add-on from disk.
  To keep the source in your project *and* installed, junction the
  folder into the addons directory:
  `mklink /J "%APPDATA%\Blender Foundation\Blender\4.5\scripts\addons\vrm_to_pmx_mapper" "C:\path\to\bone\vrm_to_pmx_mapper"`
- Fastest loop, no install at all: run `quick_map.py` from the Text
  Editor (edit → Run Script). Prints go straight to your debug console.
- Live editing from VS Code: the **Blender Development** extension
  connects VS Code to a running Blender and executes scripts directly
  in it — no zip/import cycle (check its notes for 4.5 support).

## Mapping table (defaults)

| VRM (source) | PMX (target) |
|---|---|
| `J_Bip_C_Hips` | `腰` |
| `J_Bip_C_Spine` | `上半身` |
| `J_Bip_C_Chest` | `上半身2` |
| `J_Bip_C_UpperChest` | `上半身3` |
| `J_Bip_C_Neck` / `J_Bip_C_Head` | `首` / `頭` |
| `J_Bip_{L,R}_Shoulder` | `肩.{L,R}` |
| `J_Bip_{L,R}_UpperArm` | `腕.{L,R}` |
| `J_Bip_{L,R}_LowerArm` | `ひじ.{L,R}` |
| `J_Bip_{L,R}_Hand` | `手首.{L,R}` |
| `J_Bip_{L,R}_Thumb1/2/3` | `親指０/１/２.{L,R}` |
| `J_Bip_{L,R}_Index1/2/3` | `人指１/２/３.{L,R}` |
| `J_Bip_{L,R}_Middle1/2/3` | `中指１/２/３.{L,R}` |
| `J_Bip_{L,R}_Ring1/2/3` | `薬指１/２/３.{L,R}` |
| `J_Bip_{L,R}_Little1/2/3` | `小指１/２/３.{L,R}` |
| `J_Bip_{L,R}_UpperLeg` | `足.{L,R}` |
| `J_Bip_{L,R}_LowerLeg` | `ひざ.{L,R}` |
| `J_Bip_{L,R}_Foot` | `足首.{L,R}` |
| `J_Bip_{L,R}_ToeBase` | `つま先.{L,R}` |
| `J_Adj_{L,R}_FaceEye` | `目.{L,R}` |
| `J_Sec_{L,R}_Bust1/2` | `胸.{L,R}` / `胸先.{L,R}` |
| `J_Sec_*` (opt-in) | `装飾_*-*_…` by name-suffix match |
| `J_Sec_Hair*` (opt-in) | `髪_*` by bone-head proximity |

VRM 1.x humanoid names (`hips`, `leftUpperArm`, …) are also accepted.
Customize anything via the `OVERRIDES` dict at the top of the add-on.

## Caveats

- **Rest pose must match.** Renaming groups only redirects skinning.
  Use the built-in **Rest Pose Alignment** step (or align manually);
  also match position and scale between the mesh and the armature.
- **Twist bones** (`腕捩`, `手捩`) and **IK/dummy/shadow bones** receive
  no weights from a VRM mesh — minor forearm twist loss is expected.
- **Pelvis**: default `J_Bip_C_Hips → 腰`. If your PMX model skins the
  pelvis on `下半身` instead, add
  `OVERRIDES = {"J_Bip_C_Hips": "下半身"}`.
- **Hair** (`J_Sec_Hair*`) has no name-based rule (see above) — use
  **Match Hair by Position**. Skirt/sleeve bones *do* embed the VRM
  names (`装飾_*_Sec_L_CoatSkirtBack_01` etc.), so they map cleanly when
  "Include J_Sec" is enabled.
- The report is printed to the console (Blender's debug terminal shows
  it) and saved as the text block `vrm2pmx_report` / `vrm2pmx_preview`.
