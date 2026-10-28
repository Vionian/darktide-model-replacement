from pathlib import Path
import sys, types, json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / '武器模型/怪物猎人赫拉芬格'
TOOL = ROOT / 'tools/Mod3-MHW-Importer'
pkg = types.ModuleType('mhw'); pkg.__path__ = [str(TOOL)]; sys.modules['mhw'] = pkg
for name in ('common', 'mod3', 'boundingbox', 'mrl3'):
    sub = types.ModuleType('mhw.' + name); sub.__path__ = [str(TOOL / name)]; sys.modules['mhw.' + name] = sub
sys.path.insert(0, str(TOOL / 'common'))
from mhw.mod3.Mod3 import Mod3
from mhw.common.FileLike import FileLike

model = Mod3()
model.marshall(FileLike((SRC / 'wp/two/two029/mod/two029.mod3').read_bytes()))
print('HEADER', model.Header.sceneProperties())
parts = model.prepareMeshparts(0)
summary = []
for i, part in enumerate(parts):
    v = np.asarray(part['vertices'])
    f = np.asarray(part['faces'])
    summary.append({'index': i, 'vertices': len(v), 'triangles': len(f),
                    'bounds': [v.min(axis=0).tolist(), v.max(axis=0).tolist()],
                    'properties': part['properties'], 'weight_groups': list(part['weightGroups'])})
    np.savez(ROOT / f'build/source_mesh_{i}.npz', vertices=v, faces=f,
             normals=part['normals'], tangents=part['tangents'], uvs=part['uvs'])
(ROOT / 'build/source_mesh_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
