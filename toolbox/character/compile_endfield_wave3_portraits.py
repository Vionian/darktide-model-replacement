"""Compile approved source cutouts and mirror only portrait artifacts."""
from pathlib import Path
import hashlib
import json
import shutil
import compile_screenshot_portraits as compiler
from endfield_wave3 import PROFILES
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tools/model-work/endfield_batch'

def main():
    units = {key: hashlib.sha256((ROOT/'Custom'/key/(key+'.unit')).read_bytes()).hexdigest()
             for key in PROFILES}
    compiler.SOURCE = OUT / 'wave3_portraits'
    compiler.main()
    for key in PROFILES:
        folder = ROOT/'Custom'/key
        candidate = OUT/key/'Custom'/key
        build = json.loads((folder/'build.json').read_text(encoding='utf-8'))
        name = f'content/mods/{key}/{key}_portrait'
        portrait_artifacts = [a for a in build['artifacts'] if a['resource']['name']==name]
        assert len(portrait_artifacts)==2, key
        assert units[key]==hashlib.sha256((folder/(key+'.unit')).read_bytes()).hexdigest()
        for artifact in portrait_artifacts:
            relative = Path(artifact['path'])
            target = candidate/relative
            assert target.resolve().is_relative_to(candidate.resolve())
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(folder/relative,target)
        for filename in ('build.json','compile_manifest.json'):
            shutil.copy2(folder/filename,candidate/filename)
    print('WAVE3_PORTRAITS_MIRRORED_UNIT_HASHES_UNCHANGED',units)

if __name__=='__main__':
    main()
