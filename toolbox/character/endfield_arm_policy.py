"""Third-person FK policy; segment lengths must come from the active source rig."""
import math

SOURCE_LENGTH_PROFILES = frozenset({
    'aitela', 'chenqianyu', 'endministrator_f', 'laiwanting',
    'laiwanting_simple', 'liino', 'lizhiyan', 'mifu', 'perlica',
    'roshia', 'saixi', 'si', 'tangtang', 'yvonne', 'zhuangfangyi',
})


def apply_source_lengths(body, sides, source_sha256):
    assert not body.get('first_person') and not body.get('native_hand_contract')
    bones = {bone['name']: bone for bone in body['bones']}
    supports = {s['driver_arm']: s for s in body['shoulder_supports']}
    for side in ('left', 'right'):
        shoulder, arm, elbow, wrist = [bones['j_' + side + suffix]
                                       for suffix in ('shoulder', 'arm', 'forearm', 'hand')]
        support = supports[arm['name']]
        shoulder['offset'] = support['clavicle_offset'][:]
        arm['offset'] = support['arm_offset'][:]
        for bone, key in ((elbow, 'upper_arm'), (wrist, 'forearm')):
            source_length = sides[side][key]
            assert .05 < source_length < .6, (side, key, source_length)
            old = math.sqrt(sum(v * v for v in bone['offset']))
            assert old > 1e-8
            # Restore a quarter of the source/native length gap, capped at 8%.
            length = min(source_length * 1.08, source_length + max(0, old-source_length) * .25)
            bone['offset'] = [v * length / old for v in bone['offset']]
        support['follow_arm'] = arm['name']
    for bone in body['bones']:
        if bone['name'].startswith(('j_left', 'j_right')) and any(
                word in bone['name'] for word in ('shoulder', 'arm', 'hand')):
            bone['native_position_driver'] = False
    body['arm_pose_policy'] = 'source_lengths_relaxed_native_rotations'
    body['arm_relax'] = dict(native_root_blend=.20, max_root_shift=.025,
                             native_wrist_blend=.25, minimum_relaxed_bend_degrees=12,
                             source_to_native_length_gap_fraction=.25, maximum_segment_stretch=1.08)
    body['arm_measurement_source_sha256'] = source_sha256


def apply_builder_source(builder, body, root_map):
    """Read current source bones, never reuse stale lengths from a prior build."""
    profile = getattr(builder, 'COSTUME_PROFILE', None) or getattr(builder, 'MODEL_PROFILE', 'roshia')
    if body['first_person'] or profile not in SOURCE_LENGTH_PROFILES:
        return
    import hashlib
    from pathlib import Path
    arm = builder.bpy.data.objects[builder.ARMATURE_OBJECT_NAME]
    sides = {}
    for side, suffix in (('left', '.L'), ('right', '.R')):
        candidates = [builder.side_bone_candidates('腕', suffix),
                      builder.side_bone_candidates('ひじ', suffix) +
                      ('肘' + suffix, '左肘' if side == 'left' else '右肘'),
                      builder.side_bone_candidates('手首', suffix)]
        joints = [builder.find_source_bone(arm, names) for names in candidates]
        assert all(joints), (profile, side, candidates)
        points = [builder.source_head_in_target(arm, joint, root_map) for joint in joints]
        sides[side] = dict(upper_arm=(points[1] - points[0]).length,
                           forearm=(points[2] - points[1]).length)
    source_hash = hashlib.sha256(Path(builder.SOURCE_BLEND).read_bytes()).hexdigest()
    apply_source_lengths(body, sides, source_hash)
