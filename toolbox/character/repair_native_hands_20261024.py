"""Rebuild already recovered costumes; no deployment or gameplay claim."""
from pathlib import Path
import concurrent.futures, datetime, hashlib, json, shutil, subprocess, sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'skins_20261023'
REPAIR=HERE/'hand_repair_20261024'
BLENDER='<BLENDER_EXE>'
LEGACY={'si_lolita','si_short_skirt','si_ink_mist'}
PIPELINE=('build_new_skin.py','build_roshia_native.py','endfield_profiles.py',
    'endfield_mmr_hands.py','roshia_proportion_rig.py','si_costume_materials.py',
    'endfield_hand_detail.py','costume_native_arm_fit.py','costume_geometry_audit.py',
    'adapt_skins.py','costume_hand_weights.py','costume_cuff_fit.py','costume_original_hand_weights.py',
    'costume_arm_heat_weights.py','roshia_shoulder_fit.py','costume_anatomical_domains.py')
def fingerprints():return {p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in PIPELINE}
def build(tag):
    legacy=tag in LEGACY
    folder=REPAIR/tag if legacy else OUT/tag
    folder.mkdir(parents=True,exist_ok=True)
    if legacy:
        args=['build_one_endfield_candidate.py',tag,'--output',str(folder/'Custom')]
    else:
        args=['build_new_skin.py',tag]
    log=folder/'native_repair_build.log'
    start=datetime.datetime.now().isoformat()
    pipeline=fingerprints()
    legacy_source={'si_lolita':HERE/'si_costumes/si_lolita/si_lolita.blend',
                   'si_short_skirt':HERE/'si_costumes/si_short_skirt/si_short_skirt.blend',
                   'si_ink_mist':HERE/'si_ink_mist/si_ink_mist.blend'}
    source_file=(OUT/tag/(tag+'.blend')) if not legacy else legacy_source[tag]
    source_sha=hashlib.sha256(source_file.read_bytes()).hexdigest() if source_file else None
    print('BUILD_START',tag,start,flush=True)
    with log.open('w',encoding='utf8') as stream:
        r=subprocess.run([BLENDER,'-b','--threads','4','--python-exit-code','1','--python',str(HERE/args[0]),'--',*args[1:]],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    value=log.read_text(encoding='utf8',errors='replace')
    ok=r.returncode==0 and 'ROSHIA_BUILD' in value and 'Traceback' not in value
    if legacy and ok:
        for suffix in ('proportion_bones.json','proportion_bones.lua','jiggle_bones.json'):
            src=folder/'Custom'/('roshia_'+suffix)
            if src.exists():shutil.copy2(src,folder/'Custom'/(tag+'_'+suffix))
    unchanged=pipeline==fingerprints() and hashlib.sha256(source_file.read_bytes()).hexdigest()==source_sha
    row=dict(tag=tag,folder=str(folder),started_at=start,finished_at=datetime.datetime.now().isoformat(),ok=ok,log=str(log),
        pipeline_sha256=pipeline,pipeline_unchanged_during_build=unchanged,
        source_blend_sha256=source_sha,gameplay_verified=False)
    (folder/'native_repair_status.json').write_text(json.dumps(row,indent=2),encoding='utf8')
    print('BUILD_DONE' if ok else 'BUILD_FAILED',tag,flush=True)
    return row
if __name__=='__main__':
    REPAIR.mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(build,sys.argv[1:]))
    (REPAIR/'build_results.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    if not all(r['ok'] for r in rows):sys.exit(1)
