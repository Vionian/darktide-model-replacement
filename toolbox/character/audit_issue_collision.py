"""Measure final skirt helper endpoints against the production thigh capsules.

This checks the offline Lua pose exports, not mesh/cloth collision or gameplay.
"""
from pathlib import Path
import datetime, json, sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'python-deps'))
from lupa import LuaRuntime

def main():
    lua = LuaRuntime(unpack_returned_tuples=True)
    runtime = ROOT / 'scripts/mods/EndministratorReplacement/endministrator_f_jiggle.lua'
    rows = []
    for suffix in ('', '_v2', '_v3', '_v4'):
        tag = 'endministrator_devil' + suffix
        folder = HERE / 'skins_20261023' / tag
        rig = json.loads((folder / 'Custom' / (tag + '_jiggle_bones.json')).read_text())
        config = lua.execute((folder / 'Custom' / (tag + '_jiggle_bones.lua')).read_text())
        colliders = [[config.colliders[i][k] for k in (1, 2, 3)]
                     for i in range(1, len(config.colliders) + 1)]
        audit = json.loads((folder / 'contact_runtime_audit.json').read_text())
        assert len(audit['body']['synthetic_cases']) == 23, tag
        assert (folder / 'contact_runtime_audit.json').stat().st_mtime >= runtime.stat().st_mtime, tag
        worst = dict(penetration_m=0, pose=None, bone=None, collider=None)
        samples = 0
        poses = list(folder.glob('body_*_pose.json'))
        for pose in poses:
            assert pose.stat().st_mtime >= runtime.stat().st_mtime, ('Stale collision pose', pose)
            data = json.loads(pose.read_text())
            names, worlds = data['names'], np.asarray(data['worlds'])
            for bone in rig['runtime_bones']:
                if not bone.get('collision'): continue
                matrix = worlds[names[bone['node']]]
                point = matrix[:3, 3] + matrix[:3, 2] * bone['length']
                for first, last, radius in colliders:
                    a, z = [worlds[names[n], :3, 3] for n in (first, last)]
                    axis = z - a
                    fraction = np.clip((point - a) @ axis / (axis @ axis), 0, 1)
                    penetration = max(0., float(radius - np.linalg.norm(point - a - fraction * axis)))
                    samples += 1
                    if penetration > worst['penetration_m']:
                        worst = dict(penetration_m=penetration, pose=pose.name,
                                     bone=bone['source_bone'], collider=first)
        # Sub-millimetre numerical convergence; never accept the prior 13 mm failure.
        assert worst['penetration_m'] < .00025, (tag, worst)
        rows.append(dict(profile=tag, poses=len(poses), endpoint_capsule_samples=samples,
                         collision_bones=sum(bool(b.get('collision')) for b in rig['runtime_bones']),
                         worst=worst))
    result = dict(checked_at=datetime.datetime.now().isoformat(), passed=True,
                  scope='helper endpoints in synthetic poses; not mesh collision or gameplay',
                  max_penetration_m=max(row['worst']['penetration_m'] for row in rows), rows=rows)
    target = HERE / 'issue_fixes_20261023/devil_collision_audit.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print('SKIRT_COLLISION_AUDIT', json.dumps(result, ensure_ascii=False))

if __name__ == '__main__': main()
